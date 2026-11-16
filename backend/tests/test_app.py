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
    assert f.step(days=POLICY["deposit_days"], type="time_passed") == "wait"
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
                       ("본사 규정상 어렵네요", "counter_unknown")):
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
