"""엔진 단계 전이 경계 테스트. 가짜 LLM으로 키 없이 돈다."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Contract
from app.rules import POLICY, calculate

api = TestClient(app)
CONTRACT = Contract(gym_name="가상피트니스", total_paid=600_000,
                    start_date=date(2026, 11, 5), end_date=date(2027, 2, 2))
D = date(2026, 11, 14)
WAIT = POLICY["wait_days"]


class Flow:
    def __init__(self, target=None, floor=None):
        self.today = D
        body = {"contract": CONTRACT.model_dump(mode="json"), "today": str(D)}
        body.update({k: v for k, v in (("target", target), ("floor", floor)) if v is not None})
        self.res = api.post("/api/cases", json=body).json()

    def raw(self, days=0, **event):
        return api.post("/api/cases/step", json={"case": self.res["case"], "event": event,
                                                 "today": str(self.today + timedelta(days=days))})

    def step(self, days=0, **event):
        r = self.raw(days, **event)
        assert r.status_code == 200, r.text
        self.today += timedelta(days=days)
        self.res = r.json()
        return self.res["action"]["type"]

    @property
    def stage(self):
        return self.res["case"]["stage"]

    @property
    def warn(self):
        return self.res["action"]["warn"]


def negotiating(target, floor):
    f = Flow(target, floor)
    f.step(type="notice_sent", channel="sms")
    return f


def test_reply_deadline_boundaries_through_escalation():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    assert f.step(days=WAIT, type="time_passed") == "wait"  # 기한 당일
    assert f.step(days=1, type="time_passed") == "follow_up"
    assert f.step(type="notice_sent", channel="sms") == "wait"  # 재요청
    assert f.step(days=WAIT, type="time_passed") == "wait"
    assert f.step(days=1, type="time_passed") == "certified_mail"
    assert f.step(type="escalation_sent") == "wait" and f.stage == "escalated"
    assert f.step(days=WAIT, type="time_passed") == "wait"
    assert f.step(days=1, type="time_passed") == "go_1372"


def test_deposit_deadline_boundaries():
    f = Flow()  # D는 토요일
    f.step(type="notice_sent", channel="sms")
    f.step(type="reply_received", text="네 알겠습니다")
    assert f.stage == "agreed"
    due = date.fromisoformat(f.res["case"]["deposit_due_on"])
    assert due == date(2026, 11, 18)  # 월·화·수, 3영업일
    assert f.step(days=(due - f.today).days, type="time_passed") == "wait"  # 기한 당일은 기다린다
    assert f.step(days=1, type="time_passed") == "remind_deposit"
    assert f.step(type="deposit_confirmed") == "close" and f.stage == "closed"


def test_offer_boundaries_against_floor_and_target():
    f = negotiating(450_000, 400_000)
    assert f.step(type="reply_received", reply_type="low_offer", amount=400_000) == "counter" and not f.warn
    assert f.step(type="reply_received", reply_type="low_offer", amount=399_999) == "counter" and f.warn
    assert f.step(type="reply_received", reply_type="low_offer", amount=450_000) == "confirm_agreement"


def test_button_accept_with_amount_is_a_low_offer():
    f = negotiating(450_000, 400_000)
    assert f.step(type="reply_received", reply_type="accept", amount=399_999) == "counter"
    assert f.stage == "negotiating" and f.warn and f.res["case"]["agreed_amount"] is None
    assert f.res["case"]["last_reply"] == "low_offer" and f.res["case"]["offered"] == 399_999
    assert f.step(type="reply_received", reply_type="accept", amount=450_000) == "confirm_agreement"
    assert f.stage == "negotiating" and f.res["case"]["agreed_amount"] is None
    assert f.step(type="reply_received", reply_type="accept", amount=500_000) == "confirm_agreement"


def test_button_accept_without_amount_agrees_at_legal_refund():
    f = negotiating(450_000, 400_000)
    f.step(type="reply_received", reply_type="accept")
    assert f.stage == "agreed" and f.res["case"]["agreed_amount"] == 473_334


def test_accept_with_zero_amount_rejected():
    f = negotiating(450_000, 400_000)
    assert f.raw(type="reply_received", reply_type="accept", amount=0).status_code == 409


def test_handed_off_agreement_needs_positive_amount():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    f.step(days=WAIT + 1, type="time_passed")
    f.step(type="notice_sent", channel="sms")
    f.step(days=WAIT + 1, type="time_passed")
    f.step(type="escalation_sent")
    f.step(days=WAIT + 1, type="time_passed")
    f.step(type="handoff_done")
    assert f.stage == "handed_off"
    for body in ({}, {"amount": 0}, {"amount": -1}):
        assert f.raw(type="agreement_recorded", **body).status_code == 409
    f.step(type="agreement_recorded", amount=300_000)
    assert f.stage == "agreed"
    f.step(type="deposit_confirmed")
    assert f.stage == "closed"


def test_negotiating_agreement_rejects_nonpositive_but_allows_none():
    f = negotiating(450_000, 400_000)
    f.step(type="reply_received", reply_type="refuse")
    for amount in (0, -5):
        assert f.raw(type="agreement_recorded", amount=amount).status_code == 409
    f.step(type="agreement_recorded")  # amount 없음: 법정 환불액
    assert f.stage == "agreed" and f.res["case"]["agreed_amount"] == 473_334


def test_closed_rejects_everything_but_time_passed():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    f.step(type="reply_received", text="네 알겠습니다")
    f.step(type="deposit_confirmed")
    assert f.stage == "closed"
    events = [{"type": "notice_sent", "channel": "sms"}, {"type": "call_attempted"},
              {"type": "reply_received", "reply_type": "accept"}, {"type": "reply_received", "text": "안녕"},
              {"type": "counter_sent"}, {"type": "agreement_recorded", "amount": 1000},
              {"type": "deposit_confirmed"}, {"type": "escalation_sent"}, {"type": "handoff_done"}]
    for e in events:
        assert f.raw(**e).status_code == 409, e
    assert f.step(type="time_passed") == "close"


@pytest.mark.parametrize("event", [
    {"type": "reply_received", "reply_type": "low_offer", "amount": -1},
    {"type": "agreement_recorded", "amount": -1},
    {"type": "time_passed", "amount": -1},
])
def test_negative_amount_rejected(event):
    f = negotiating(450_000, 400_000)
    assert f.raw(**event).status_code == 409


@pytest.mark.parametrize("agreed_on, due", [
    (date(2026, 11, 16), date(2026, 11, 19)),  # 월 → 목
    (date(2026, 11, 18), date(2026, 11, 23)),  # 수 → 다음 월(주말 뺌)
    (date(2026, 11, 20), date(2026, 11, 25)),  # 금 → 다음 수
    (date(2026, 11, 22), date(2026, 11, 25)),  # 일 → 수
])
def test_deposit_due_counts_business_days(agreed_on, due):
    from app.engine import add_business_days
    assert POLICY["deposit_days"] == 3
    assert add_business_days(agreed_on, 3) == due


def agreed():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    f.step(type="reply_received", reply_type="accept")
    assert f.stage == "agreed"
    return f


def test_partial_deposit_keeps_tracking_until_the_rest_arrives():
    f = agreed()
    total = f.res["case"]["agreed_amount"]
    assert f.step(type="deposit_confirmed", amount=200_000) == "wait" and f.stage == "agreed"
    assert f.res["case"]["deposited"] == 200_000 and f"남은 {total - 200_000:,}원" in f.res["action"]["reason"]
    assert f.step(type="deposit_confirmed", amount=total - 200_000) == "close" and f.stage == "closed"


def test_deposit_without_amount_still_closes_and_bad_amounts_are_rejected():
    f = agreed()
    assert f.raw(type="deposit_confirmed", amount=0).status_code == 409
    assert f.raw(type="deposit_confirmed", amount=-1).status_code == 409
    assert f.step(type="deposit_confirmed") == "close" and f.res["case"]["deposited"] == f.res["case"]["agreed_amount"]


def test_unpaid_deposit_reminds_then_goes_to_1372():
    f = agreed()
    f.step(type="deposit_confirmed", amount=100_000)
    due = date.fromisoformat(f.res["case"]["deposit_due_on"])
    assert f.step(days=(due - f.today).days, type="time_passed") == "wait"
    assert f.raw(type="handoff_done").status_code == 409  # 기한 전에는 1372로 못 간다
    assert f.step(days=1, type="time_passed") == "remind_deposit"
    remind = f.res["drafts"]["remind_deposit"]
    assert "100,000원만 들어왔습니다" in remind and "남은" in remind
    assert f.raw(type="handoff_done").status_code == 409  # 독촉 기간에도 아직이다
    assert f.step(days=WAIT - 1, type="time_passed") == "remind_deposit"  # 기한 + wait_days: 독촉 기간 마지막 날
    assert f.step(days=1, type="time_passed") == "go_1372"
    assert "입금 기한이 지나도록 100,000원만 받음" in f.res["drafts"]["go_1372"]
    # 그대로 옮겨 쓰는 요청 금액은 못 받은 합의 금액이다(계산액대로 합의해 참고 금액은 붙지 않는다)
    assert "- 요청 금액: 373,334원 (합의한 금액 473,334원 중 100,000원만 받음)" in f.res["drafts"]["go_1372"]
    f.step(type="handoff_done")
    assert f.stage == "handed_off"
    assert "입금 기한이 지나도록 100,000원만 받음" in f.res["drafts"]["go_1372"]  # 접수 뒤에도 합의·입금 경과가 남는다
    assert "- 요청 금액: 373,334원 (합의한 금액 473,334원 중 100,000원만 받음)" in f.res["drafts"]["go_1372"]
    f.step(type="agreement_recorded", amount=373_334)
    assert f.stage == "agreed" and f.res["case"]["deposited"] == 0  # 1372 뒤 합의 금액을 새로 받는다
    assert f.step(type="deposit_confirmed", amount=373_334) == "close"


def test_remind_text_without_any_deposit_is_unchanged():
    f = agreed()
    due = date.fromisoformat(f.res["case"]["deposit_due_on"])
    f.step(days=(due - f.today).days + 1, type="time_passed")
    assert "아직 확인되지 않습니다. 입금 일정을 회신 부탁드립니다." in f.res["drafts"]["remind_deposit"]


def refusing():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    assert f.step(type="reply_received", reply_type="refuse") == "counter"
    return f


def test_repeated_refusal_moves_to_certified_mail_then_1372():
    f = refusing()
    f.step(type="counter_sent")
    assert f.step(type="reply_received", reply_type="refuse") == "counter"  # 반박 1번: 아직 다시 반박
    f.step(type="counter_sent")
    assert f.step(type="reply_received", reply_type="list_price") == "certified_mail"  # 반박 2번 뒤 거절
    assert "certified_mail" in f.res["drafts"]
    assert f.step(type="escalation_sent") == "wait" and f.stage == "escalated"
    assert f.step(type="reply_received", reply_type="refuse") == "go_1372"  # 내용증명 뒤에도 거절
    assert f.stage == "negotiating" and "go_1372" in f.res["drafts"]
    f.step(type="handoff_done")
    assert f.stage == "handed_off"


def test_repeated_refusal_forbidden_moves():
    f = refusing()
    assert f.raw(type="escalation_sent").status_code == 409  # 반박 전에는 내용증명으로 못 간다
    assert f.raw(type="handoff_done").status_code == 409
    f.step(type="counter_sent")
    f.step(type="reply_received", reply_type="refuse")
    f.step(type="counter_sent")
    f.step(type="reply_received", reply_type="refuse")
    assert f.raw(type="counter_sent").status_code == 409  # 정한 횟수를 넘으면 반박을 되풀이하지 않는다
    assert f.raw(type="handoff_done").status_code == 409  # 내용증명 전에는 1372로 못 간다


def test_low_offer_after_max_counters_still_warns_and_good_offer_can_be_confirmed():
    f = refusing()
    for _ in range(POLICY["max_counters"]):
        f.step(type="counter_sent")
        f.step(type="reply_received", reply_type="refuse")
    floor = f.res["case"]["floor"]
    assert f.step(type="reply_received", reply_type="low_offer", amount=floor - 1) == "certified_mail" and f.warn
    target = f.res["case"]["target"]
    assert f.step(type="reply_received", reply_type="low_offer", amount=target) == "confirm_agreement"


def test_guidance_is_polite_and_dates_have_no_leading_zero():
    """다음 행동의 reason은 화면 맨 위 안내로 그대로 보인다. 다른 화면 문구와 같이 해요체로 쓰고, 날짜에 0을 붙이지 않는다."""
    from app.engine import next_action
    from app.models import Case
    seen = []
    f = Flow()
    seen.append(f.res["action"]["reason"])
    f.step(type="notice_sent", channel="sms")
    seen.append(f.res["action"]["reason"])
    for days in (WAIT + 1, 0):
        f.step(days=days, type="time_passed")
        seen.append(f.res["action"]["reason"])
    f.step(type="reply_received", reply_type="refuse")
    seen.append(f.res["action"]["reason"])
    f.step(type="reply_received", reply_type="low_offer", amount=100_000)
    seen.append(f.res["action"]["reason"])
    assert all(not r.endswith("다") for r in seen), seen
    waiting = Case.model_validate(Flow().res["case"]).model_copy(
        update={"stage": "waiting", "deadline_on": date(2027, 1, 5), "notified_on": D})
    assert next_action(waiting, date(2027, 1, 2)).reason.startswith("1월 5일까지")


def test_old_month_case_cannot_send_first_notice():
    """옛 규칙의 월 단위 사건(unit_label "개월")은 첫 통지를 거절한다. 희망 금액·하한선이 옛 금액에 남기 때문이다(#137)."""
    body = {"contract": CONTRACT.model_copy(update={"unit": "month", "total_count": 3}).model_dump(mode="json"),
            "today": str(D)}
    new = api.post("/api/cases", json=body).json()["case"]
    assert new["refund"]["unit_label"] == "일"
    notice = {"type": "notice_sent", "channel": "sms"}
    assert api.post("/api/cases/step", json={"case": new, "event": notice, "today": str(D)}).status_code == 200
    old = new | {"refund": new["refund"] | {"unit_label": "개월"}}
    r = api.post("/api/cases/step", json={"case": old, "event": notice, "today": str(D)})
    assert r.status_code == 409 and "새로고침" in r.json()["detail"]
    # 화면에서 새 예상 환불액으로 바꾸면(rebase) 기록과 사용자가 정한 하한선을 그대로 둔 채 통지할 수 있다
    old = old | {"floor": 275_000, "target": 300_000,
                 "timeline": [{"on": str(D), "type": "call_attempted", "text": "안 받음"}]}
    preview = api.post("/api/refund-preview", json={"contract": body["contract"], "today": str(D)}).json()
    r = api.post("/api/cases/step", json={"case": old | {"refund": preview}, "event": notice, "today": str(D)})
    assert r.status_code == 200
    kept = r.json()["case"]
    assert (kept["floor"], kept["target"], kept["timeline"][0]["type"]) == (275_000, 300_000, "call_attempted")


# ---- 알리기 전에 날짜가 지났을 때(2026-11-22 시나리오 점검) ----------------------------------------
# 환불액은 첫 통지일로 고정되지만 그 전에는 하루씩 줄어든다. 열 때의 금액으로 문안을 보여 주면 며칠 뒤 보내는 문자가
# 더 많은 금액을 "오늘 자로" 요청하고, 보낸 뒤에는 정한 적 없는 하한선이 옛 금액으로 남아 맞는 제시에도 경고가 뜬다.

def test_waiting_to_notify_reprices_the_amount_and_the_draft_to_today():
    f = Flow()
    opened = f.res["case"]["refund"]["refund"]
    assert f.step(days=0, type="time_passed") == "send_notice" and f.res["case"]["refund"]["refund"] == opened  # 같은 날은 그대로
    f.step(days=4, type="time_passed")
    case = f.res["case"]
    assert case["refund"]["refund"] == calculate(CONTRACT, D + timedelta(days=4)).refund < opened and case["stage"] == "ready"
    assert f"{case['refund']['refund']:,}원" in f.res["drafts"]["notice_sms"] and f"{opened:,}원" not in f.res["drafts"]["notice_sms"]
    # 정하지 않은 희망 금액·하한선은 새 금액을 따라간다
    assert case["target"] == case["floor"] == case["refund"]["refund"]
    assert case["notified_on"] is None and case["timeline"] == []  # 통지로 보지 않는다


def test_a_correct_offer_after_a_late_notice_is_not_below_the_floor():
    f = Flow()
    f.step(days=4, type="time_passed")
    f.step(type="notice_sent", channel="sms")
    refund = f.res["case"]["refund"]["refund"]
    assert f.res["case"]["floor"] == refund
    f.step(days=1, type="reply_received", reply_type="low_offer", amount=refund)
    assert f.res["action"]["type"] == "confirm_agreement" and not f.warn  # 맞는 금액이다
    # 통지 때 처음 다시 계산돼도 같다(앱을 열지 않고 며칠 뒤 바로 보낸 경우)
    g = Flow()
    g.step(days=4, type="notice_sent", channel="sms")
    assert g.res["case"]["floor"] == g.res["case"]["target"] == g.res["case"]["refund"]["refund"]


def test_limits_the_user_set_do_not_move_when_the_amount_does():
    f = Flow(target=460_000 + 10_000, floor=440_000)
    f.step(days=4, type="time_passed")
    case = f.res["case"]
    assert (case["target"], case["floor"]) == (470_000, 440_000)  # 정한 값은 그대로
    only_floor = Flow(floor=440_000)  # 희망 금액만 기본이면 새 금액을 따라가고, 하한선은 희망 금액을 넘지 않는다
    only_floor.step(days=4, type="time_passed")
    c = only_floor.res["case"]
    assert c["target"] == c["refund"]["refund"] and c["floor"] == min(440_000, c["target"])


def test_amounts_after_the_first_notice_stay_fixed_when_time_passes():
    f = Flow()
    f.step(type="notice_sent", channel="sms")
    fixed = f.res["case"]["refund"]["refund"]
    f.step(days=WAIT + 1, type="time_passed")
    f.step(days=1, type="time_passed")
    assert f.res["case"]["refund"]["refund"] == fixed  # 통지 뒤에는 날짜가 지나도 바뀌지 않는다
    after_call = Flow()
    after_call.step(type="call_attempted")  # 연결되지 않은 통화는 도달이 아니다. 아직 알리기 전이다
    after_call.step(days=4, type="time_passed")
    assert after_call.res["case"]["refund"]["refund"] < fixed and after_call.stage == "ready"
