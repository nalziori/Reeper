from datetime import date

from fastapi.testclient import TestClient

from app import agent
from app.main import app

api = TestClient(app)
TODAY = str(date(2026, 11, 14))
CONTRACT = {"gym_name": "가상피트니스", "total_paid": 600000, "start_date": "2026-11-05",
            "end_date": "2027-02-02", "special_terms": "이벤트 상품은 환불이 불가합니다."}
SITUATION = "다음 달에 이사 가서 더 못 다녀요."
EMPTY = {"summary": "", "grounds": [], "contract_points": [], "objections": [], "cautions": [], "questions": [],
         "fallback": False}


def opened() -> dict:
    return api.post("/api/cases", json={"contract": CONTRACT, "today": TODAY}).json()["case"]


def ask(case: dict, situation: str = SITUATION):
    return api.post("/api/cases/strategy", json={"case": case, "situation": situation, "today": TODAY})


def test_strategy_rides_on_the_case_and_grounds_carry_verified(monkeypatch):
    plan = {**EMPTY, "summary": "환불을 요청하세요.", "grounds": [{"rule_id": "R31", "why": "기간 중 해지"}],
            "cautions": ["전액은 어려워요."], "dropped": 2}
    monkeypatch.setattr(agent, "plan", lambda case, situation, today: plan)
    before = opened()
    res = ask(before).json()
    case = res["case"]
    assert not res["llm_fallback"] and case["situation"] == SITUATION
    assert case["strategy"]["grounds"] == [{"rule_id": "R31", "why": "기간 중 해지", "verified": True}]
    assert case["strategy"]["cautions"] == ["전액은 어려워요."] and "dropped" not in case["strategy"]
    # 단계, 금액, 타임라인은 그대로다
    assert {k: v for k, v in case.items() if k not in ("situation", "strategy")} == \
           {k: v for k, v in before.items() if k not in ("situation", "strategy")}
    # 전략은 다음 단계에서도 사건에 남는다
    step = api.post("/api/cases/step", json={"case": case, "today": TODAY,
                                             "event": {"type": "notice_sent", "channel": "sms"}}).json()
    assert step["case"]["strategy"] == case["strategy"] and step["case"]["situation"] == SITUATION


def test_no_strategy_without_a_real_llm_or_on_failure(monkeypatch):
    res = ask(opened()).json()  # 가짜 LLM
    assert res["case"]["strategy"] is None and not res["llm_fallback"] and res["case"]["situation"] == SITUATION
    monkeypatch.setattr(agent, "plan", lambda *_: {**EMPTY, "fallback": True})
    res = ask(opened()).json()
    assert res["case"]["strategy"] is None and res["llm_fallback"]


def test_rejects_a_situation_that_is_too_long():
    assert ask(opened(), "가" * (agent.MAX_SITUATION + 1)).status_code == 422
    assert ask(opened(), "가" * agent.MAX_SITUATION).status_code == 200
