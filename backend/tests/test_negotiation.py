from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.main import app


api = TestClient(app)
TODAY = str(date(2026, 11, 14))
CONTRACT = {"gym_name": "가상피트니스", "total_paid": 600000,
            "start_date": "2026-11-05", "end_date": "2027-02-02"}


def open_case(**limits):
    return api.post("/api/cases", json={"contract": CONTRACT, "today": TODAY, **limits})


def step(case, **event):
    response = api.post("/api/cases/step", json={"case": case, "today": TODAY, "event": event})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("limits", [
    {"target": -1, "floor": 0}, {"target": 0, "floor": -1},
    {"target": 200000, "floor": 300000}, {"floor": 600000},
])
def test_rejects_invalid_negotiation_limits(limits):
    assert open_case(**limits).status_code == 422


def test_omitted_limits_use_calculated_refund():
    case = open_case().json()["case"]
    assert case["target"] == case["floor"] == case["refund"]["refund"]


@pytest.mark.parametrize("offered, action, warn", [
    (400000, "confirm_agreement", False), (300000, "counter", False),
    (299999, "counter", True), (0, "counter", True),
])
def test_offer_at_negotiation_boundaries(offered, action, warn):
    case = open_case(target=400000, floor=300000).json()["case"]
    case = step(case, type="notice_sent", channel="sms")["case"]
    result = step(case, type="reply_received", reply_type="low_offer", amount=offered)
    assert result["case"]["offered"] == offered
    assert (result["action"]["type"], result["action"]["warn"]) == (action, warn)


def test_explicit_zero_offer_is_preserved_but_zero_agreement_rejected(monkeypatch):
    monkeypatch.setattr(agent, "read_reply", lambda _: ("low_offer", 200000, False))
    case = open_case(target=0, floor=0).json()["case"]
    assert case["target"] == case["floor"] == 0
    case = step(case, type="notice_sent", channel="sms")["case"]
    case = step(case, type="reply_received", text="제시액 입력", amount=0)["case"]
    assert case["offered"] == 0
    # 합의 금액은 0원보다 커야 한다 (engine.validate_transition)
    response = api.post("/api/cases/step", json={
        "case": case, "today": TODAY, "event": {"type": "agreement_recorded", "amount": 0}})
    assert response.status_code == 409
