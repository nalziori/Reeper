"""가짜 LLM으로 키 없이 돈다. 실행: backend 폴더에서 `pytest`."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.agent import TEMPLATES, render, validate
from app.engine import open_case
from app.main import app
from app.models import Contract
from app.rules import POLICY, calculate

api = TestClient(app)
CONTRACT = Contract(gym_name="가상피트니스", total_paid=600_000,
                    start_date=date(2026, 11, 5), end_date=date(2027, 2, 2))
D = date(2026, 11, 14)  # 개시 10일째


def test_refund_shrinks_every_day():
    r = calculate(CONTRACT, D)
    assert (r.total_days, r.used_days, r.used_amount, r.penalty, r.refund) == (90, 10, 66_666, 60_000, 473_334)
    assert calculate(CONTRACT, D + timedelta(days=10)).refund == 406_667  # 열흘 미루면 약 6만 7천 원 감소
    assert calculate(CONTRACT, date(2027, 6, 1)).refund == 0  # 기간이 끝나면 0


def test_all_templates_render_and_pass_validation():
    case = open_case(CONTRACT, D).model_copy(update={"offered": 200_000, "agreed_amount": 473_334,
                                                     "notified_on": D, "deposit_due_on": D})
    for kind in TEMPLATES:
        assert validate(render(kind, case), case), kind


def test_validator_blocks_invented_amounts_and_articles():
    case = open_case(CONTRACT, D)
    assert not validate("500,000원을 환불해 주세요.", case)
    assert not validate("민법 제999조에 따라 요청합니다.", case)


def test_call_card_has_the_five_things_to_say():
    card = render("call_card", open_case(CONTRACT, D))
    for must in ("해지 의사", "날짜", "금액", "입금 계좌", "문자 확인"):
        assert must in card


class Flow:
    """API만으로 사건을 끝까지 몰아 보는 도우미."""

    def __init__(self):
        self.today = D
        self.res = api.post("/api/cases", json={"contract": CONTRACT.model_dump(mode="json"),
                                                "today": str(D)}).json()

    def step(self, days=0, **event):
        self.today += timedelta(days=days)
        self.res = api.post("/api/cases/step", json={"case": self.res["case"], "event": event,
                                                     "today": str(self.today)}).json()
        return self.res["action"]["type"]

    @property
    def stage(self):
        return self.res["case"]["stage"]


def test_happy_path_to_deposit():
    f = Flow()
    assert f.res["action"]["type"] == "send_notice" and "call_card" in f.res["drafts"]
    assert f.step(type="notice_sent", channel="sms") == "wait"
    f.step(type="reply_received", text="네 알겠습니다 환불해 드릴게요")
    assert f.stage == "agreed" and f.res["case"]["agreed_amount"] == 473_334
    due = date.fromisoformat(f.res["case"]["deposit_due_on"])  # 주말을 뺀 3영업일
    assert f.step(days=(due - f.today).days, type="time_passed") == "wait"
    assert f.step(days=1, type="time_passed") == "remind_deposit"  # 입금이 늦으면 독촉
    assert f.step(type="deposit_confirmed") == "close" and f.stage == "closed"


def test_low_offer_warns_then_agreement():
    f = Flow()
    f.step(type="notice_sent", channel="call")
    assert f.step(type="reply_received", text="20만원만 드릴게요") == "counter"
    assert f.res["action"]["warn"] and "200,000원" in f.res["drafts"]["counter_low_offer"]
    assert f.step(type="reply_received", text="48만원 드리겠습니다") == "confirm_agreement"
    f.step(type="agreement_recorded", amount=480_000)
    assert f.stage == "agreed"


def test_objections_get_a_counter():
    for text, kind in (("이벤트 상품은 환불 불가입니다", "counter_refuse"),
                       ("정상가 기준으로 차감합니다", "counter_list_price"),
                       ("방문하셔야 처리됩니다", "counter_visit"),
                       ("그 부분은 좀 애매하네요", "counter_unknown")):
        f = Flow()
        f.step(type="notice_sent", channel="sms")
        assert f.step(type="reply_received", text=text) == "counter"
        assert kind in f.res["drafts"], text


def test_silence_escalates_to_1372():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    assert f.step(days=POLICY["wait_days"], type="time_passed") == "wait"
    assert f.step(days=1, type="time_passed") == "follow_up"
    assert f.step(type="notice_sent", channel="sms") == "wait"
    assert f.step(days=4, type="time_passed") == "certified_mail"
    assert f.step(type="escalation_sent") == "wait"
    assert f.step(type="reply_received", reply_type="callback") == "wait"
    assert f.stage == "escalated"
    assert f.step(days=4, type="time_passed") == "go_1372"
    f.step(type="handoff_done")
    assert f.stage == "handed_off"
    assert f.res["case"]["notified_on"] == str(D)  # 도달일은 첫 통지일로 고정
    assert f.res["case"]["refund"]["refund"] == calculate(CONTRACT, D).refund


@pytest.mark.parametrize("events, invalid", [
    ([], {"type": "deposit_confirmed"}),
    ([], {"type": "reply_received", "text": "환불해 드릴게요"}),
    ([{"type": "notice_sent", "channel": "sms"}], {"type": "notice_sent", "channel": "sms"}),
    ([{"type": "notice_sent", "channel": "sms"}], {"type": "escalation_sent"}),
    ([{"type": "notice_sent", "channel": "sms"}], {"type": "handoff_done"}),
    ([{"type": "notice_sent", "channel": "sms"}], {"type": "agreement_recorded", "amount": 200000}),
    ([{"type": "notice_sent", "channel": "sms"}, {"type": "reply_received", "reply_type": "accept"},
      {"type": "deposit_confirmed"}], {"type": "notice_sent", "channel": "sms"}),
])
def test_rejects_invalid_transition_before_processing_reply(monkeypatch, events, invalid):
    def unexpected_llm_call(_text):
        pytest.fail("허용되지 않는 답장에는 LLM을 호출하지 않는다")

    monkeypatch.setattr(agent, "read_reply", unexpected_llm_call)
    f = Flow()
    for event in events:
        f.step(**event)
    response = api.post("/api/cases/step", json={"case": f.res["case"], "event": invalid, "today": str(D)})
    assert response.status_code == 409
    assert "case" not in response.json()


def test_rejects_event_dated_before_latest_record():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    response = api.post("/api/cases/step", json={
        "case": f.res["case"], "event": {"type": "time_passed"}, "today": str(D - timedelta(days=1)),
    })
    assert response.status_code == 409


def test_samples_and_health():
    health = api.get("/api/health").json()
    assert health["ok"]
    assert health["llm"] == "FakeLLM"
    assert api.get("/api/samples").json()[0]["contract"]["total_paid"] == 600_000


def test_refund_preview_uses_rules_without_generating_drafts(monkeypatch):
    import importlib

    main = importlib.import_module("app.main")
    monkeypatch.setattr(main, "drafts_for", lambda *_: pytest.fail("미리보기에서 문안이나 LLM을 생성하지 않는다"))
    response = api.post("/api/refund-preview", json={
        "contract": CONTRACT.model_dump(mode="json"), "today": str(D),
    })
    assert response.status_code == 200
    assert response.json()["refund"] == calculate(CONTRACT, D).refund
def test_counter_starts_new_wait_without_resetting_notice():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    previous = f.res["case"]
    f.step(days=1, type="reply_received", reply_type="refuse")
    assert f.step(type="counter_sent") == "wait"
    case = f.res["case"]
    assert f.stage == "waiting"
    assert case["notified_on"] == previous["notified_on"]
    assert case["refund"] == previous["refund"]
    assert case["attempts"] == previous["attempts"]
    assert f.step(days=4, type="time_passed") == "follow_up"


def test_counter_after_certified_mail_can_still_reach_1372_and_deposit():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    f.step(days=4, type="notice_sent", channel="sms")
    f.step(days=4, type="escalation_sent")
    f.step(type="reply_received", reply_type="refuse")
    assert f.step(type="counter_sent") == "wait"
    assert f.stage == "escalated"
    assert f.step(days=4, type="time_passed") == "go_1372"
    f.step(type="handoff_done")
    f.step(type="agreement_recorded", amount=300_000)
    assert f.stage == "agreed"
    assert f.res["case"]["agreed_amount"] == 300_000
    assert f.step(type="deposit_confirmed") == "close"


def test_failed_first_call_keeps_case_ready():
    f = Flow()
    assert f.step(type="call_attempted") == "send_notice"
    case = f.res["case"]
    assert case["stage"] == "ready" and case["notified_on"] is None
    assert case["attempts"] == 0
    assert case["timeline"][-1]["type"] == "call_attempted"


def test_restored_waiting_case_uses_existing_certified_mail_record():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    f.step(days=4, type="notice_sent", channel="sms")
    f.step(days=4, type="escalation_sent")
    # 이전 버전에서 내용증명 이후 재연락 약속을 기록하면 waiting으로 저장될 수 있었다.
    f.res["case"]["stage"] = "waiting"
    assert f.step(days=4, type="time_passed") == "go_1372"
    f.step(type="handoff_done")
    assert f.stage == "handed_off"


def test_refreshing_action_does_not_add_a_timeline_entry():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    case = f.res["case"]
    assert f.step(days=4, type="time_passed") == "follow_up"
    assert f.res["case"] == case


def test_read_reply_does_not_touch_the_case_and_step_uses_the_confirmed_type():
    """답장 읽기는 사건 없이 결과만 준다. 단계는 사용자가 확정한 유형으로만 바뀐다."""
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    text = "환불해 드릴게요. 위약금 30% 빼고요"
    read = api.post("/api/replies/read", json={"text": text}).json()
    assert set(read) == {"reply_type", "amount", "llm_fallback"}
    assert f.stage == "waiting"  # 읽기만으로는 아무 일도 없다
    # 사용자가 "수용"이 아니라 "잘 모르겠어요"로 고쳐 확정하면 합의로 가지 않는다
    assert f.step(type="reply_received", text=text, reply_type="unknown") == "counter"
    assert f.stage == "negotiating" and f.res["case"]["agreed_amount"] is None
    assert f.res["case"]["timeline"][-1]["text"] == text  # 원문은 기록에 남는다


def test_read_reply_rejects_empty_text():
    assert api.post("/api/replies/read", json={"text": ""}).status_code == 422


def test_confirmed_step_with_analyze_flag_still_moves_by_the_confirmed_type():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    res = api.post("/api/cases/step", json={"case": f.res["case"], "today": str(f.today), "analyze": True,
                                            "event": {"type": "reply_received", "text": "네 알겠습니다", "reply_type": "accept"}})
    assert res.status_code == 200 and res.json()["case"]["stage"] == "agreed"

def test_late_notice_moves_default_limits_with_the_refund():
    # 사건을 연 날보다 사흘 늦게 통지하면 환불액이 줄어든다. 비워 둔 희망 금액·하한선도 함께 따라간다
    f = Flow()
    assert f.step(days=3, type="notice_sent", channel="sms") == "wait"
    case = f.res["case"]
    late = calculate(CONTRACT, D + timedelta(days=3)).refund
    assert case["refund"]["refund"] == case["target"] == case["floor"] == late < 473_334
    # 경계: 업체가 법정액을 정확히 주면 합의, 1원 적으면 경고
    assert f.step(type="reply_received", reply_type="low_offer", amount=late) == "confirm_agreement"
    assert not f.res["action"]["warn"]
    assert f.step(type="reply_received", reply_type="low_offer", amount=late - 1) == "counter"
    assert f.res["action"]["warn"] and f.res["action"]["reason"] == "제시액이 예상 환불액보다 적어요"


@pytest.mark.parametrize("limits, expected", [
    ({"target": 500_000, "floor": 300_000}, (500_000, 300_000)),  # 직접 정한 값은 그대로
    ({"floor": 470_000}, (470_000, 470_000)),  # 비워 둔 희망 금액이 하한선보다 작아지면 하한선까지 올린다
])
def test_late_notice_keeps_limits_the_user_set(limits, expected):
    res = api.post("/api/cases", json={"contract": CONTRACT.model_dump(mode="json"), "today": str(D), **limits}).json()
    res = api.post("/api/cases/step", json={"case": res["case"], "event": {"type": "notice_sent", "channel": "sms"},
                                            "today": str(D + timedelta(days=3))}).json()
    assert (res["case"]["target"], res["case"]["floor"]) == expected


@pytest.mark.parametrize("reply_type", ["callback", "no_answer"])
def test_putting_off_during_negotiation_keeps_the_counter(reply_type):
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    # 답변 기한이 지난 뒤 거절을 받아 반박할 차례다
    assert f.step(days=POLICY["wait_days"] + 2, type="reply_received", reply_type="refuse") == "counter"
    assert f.step(type="reply_received", reply_type=reply_type) == "counter"
    assert f.stage == "negotiating" and "counter_refuse" in f.res["drafts"]
    assert f.res["case"]["last_reply"] == "refuse" and f.res["case"]["timeline"][-1]["text"] == reply_type
    # 금지된 전이: 협상 중에는 재요청(통지)을 기록할 수 없다. 반박은 그대로 보낼 수 있다
    bad = api.post("/api/cases/step", json={"case": f.res["case"], "event": {"type": "notice_sent", "channel": "sms"},
                                            "today": str(f.today)})
    assert bad.status_code == 409
    assert f.step(type="counter_sent") == "wait" and f.stage == "waiting"


def test_putting_off_keeps_the_low_offer_warning():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    assert f.step(type="reply_received", reply_type="low_offer", amount=100_000) == "counter"
    assert f.step(type="reply_received", reply_type="callback") == "counter"
    assert f.res["action"]["warn"] and f.res["case"]["offered"] == 100_000
