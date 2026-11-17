"""엔진 단계 전이 경계 테스트. 가짜 LLM으로 키 없이 돈다."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Contract
from app.rules import POLICY

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
