"""UNLOCK_KEY가 있으면 비밀값을 가진 요청만 실제 LLM을 쓴다. 없으면 모두 실제 LLM을 쓴다(예전 동작)."""
import pytest
from fastapi.testclient import TestClient

from app import agent
from app.main import app


@pytest.fixture
def real(monkeypatch):
    """실제 LLM이 있는 것처럼 둔다. OpenAILLM 생성은 네트워크를 쓰지 않는다."""
    monkeypatch.setattr(agent, "llm", agent.OpenAILLM("test-key", "test-model"))


def which(client) -> str:
    return client.get("/api/health").json()["llm"]


def test_locked_by_default_and_unlocked_with_the_secret(real, monkeypatch):
    monkeypatch.setenv("UNLOCK_KEY", "s3cret")
    client = TestClient(app)
    assert which(client) == "FakeLLM"  # 비밀값 없이 들어오면 가짜 LLM

    assert client.get("/unlock/s3cret").status_code == 200  # 리다이렉트를 따라가 앱이 뜬다
    assert which(client) == "OpenAILLM"  # 쿠키가 생긴 뒤에는 실제 LLM

    wrong = TestClient(app)
    assert wrong.get("/unlock/nope").status_code == 200
    assert which(wrong) == "FakeLLM"  # 틀린 값은 쿠키를 심지 않는다


def test_no_unlock_key_means_everyone_uses_the_real_llm(real, monkeypatch):
    monkeypatch.delenv("UNLOCK_KEY", raising=False)
    assert which(TestClient(app)) == "OpenAILLM"


def test_without_a_real_key_it_stays_fake(monkeypatch):
    monkeypatch.setenv("UNLOCK_KEY", "s3cret")  # 실제 키가 없으면 비밀값이 있어도 가짜 LLM뿐이다
    client = TestClient(app)
    client.get("/unlock/s3cret")
    assert which(client) == "FakeLLM"
