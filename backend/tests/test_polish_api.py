"""POST /api/drafts/polish: 말투만 다듬고, 금액·조문이 달라지면 원래 양식을 돌려준다. 키 없이 돈다."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.engine import open_case
from app.main import app
from app.models import Contract

api = TestClient(app)
CONTRACT = Contract(gym_name="가상피트니스", total_paid=600_000,
                    start_date=date(2026, 11, 5), end_date=date(2027, 2, 2))
D = date(2026, 11, 14)


def case_json():
    return open_case(CONTRACT, D).model_dump(mode="json")


def polish(case, kind="notice_sms", tone="polite"):
    return api.post("/api/drafts/polish", json={"case": case, "kind": kind, "tone": tone})


@pytest.fixture
def real(monkeypatch):
    """OpenAILLM을 끼우고 _chat이 돌려줄 값을 정한다."""
    llm = agent.OpenAILLM("test-key", "test-model")
    monkeypatch.setattr(agent, "llm", llm)
    monkeypatch.setattr(agent.OpenAILLM, "usage", {"day": None, "calls": 0, "tokens": 0})

    def answer(value):
        def chat(*_):
            if isinstance(value, Exception):
                raise value
            return value
        monkeypatch.setattr(llm, "_chat", chat)
    return answer


def test_fake_llm_returns_the_fixed_template_unpolished():
    case = case_json()
    res = polish(case)
    assert res.status_code == 200
    base = agent.render("notice_sms", open_case(CONTRACT, D))
    assert res.json() == {"text": base, "polished": False}


def test_real_llm_polish_is_used_only_when_numbers_stay(real):
    case = case_json()
    base = agent.render("notice_sms", open_case(CONTRACT, D))
    real({"text": "번거로우시겠지만 확인 부탁드립니다. " + base})
    assert polish(case, tone="firm").json() == {"text": "번거로우시겠지만 확인 부탁드립니다. " + base, "polished": True}
    real({"text": base.replace("473,334", "500,000")})  # 금액을 바꾸면 쓰지 않는다
    assert polish(case).json() == {"text": base, "polished": False}
    real(RuntimeError("down"))  # 호출이 실패해도 원래 양식으로 계속 간다
    assert polish(case).json() == {"text": base, "polished": False}


def test_polish_does_not_change_the_case(real):
    case = case_json()
    real({"text": "확인 부탁드립니다. " + agent.render("notice_sms", open_case(CONTRACT, D))})
    assert set(polish(case).json()) == {"text", "polished"}  # 사건을 돌려주지 않는다


@pytest.mark.parametrize("kind, tone, status", [
    ("no_such_template", "polite", 404),
    ("call_card", "polite", 422),  # 통화 준비 카드는 보내는 문장이 아니다
    ("notice_sms", "angry", 422),
])
def test_polish_rejects_bad_requests(kind, tone, status):
    assert polish(case_json(), kind, tone).status_code == status
