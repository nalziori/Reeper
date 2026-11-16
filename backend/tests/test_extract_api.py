"""POST /api/contracts/extract: 계약서 사진에서 값을 읽는다. 키 없이 돈다."""
import base64

import pytest
from fastapi.testclient import TestClient

from app import agent, main
from app.main import app

api = TestClient(app)
IMAGE = "data:image/jpeg;base64," + base64.b64encode(b"not really a photo").decode()
READ = {
    "gym_name": {"value": "가상피트니스", "confidence": 0.95, "quote": "상호 가상피트니스"},
    "total_paid": {"value": 600000, "confidence": 0.9, "quote": "결제금액 600,000원"},
    "start_date": {"value": "2026-11-05", "confidence": 0.9, "quote": "2026.11.05"},
    "end_date": {"value": "2027-02-02", "confidence": 0.5, "quote": "2027.02.02"},
    "special_terms": {"value": None, "confidence": 0.9, "quote": "특약사항 없음"},
}


@pytest.fixture
def on(monkeypatch):
    """사진 읽기를 켜고 OpenAILLM을 끼운다. _chat이 돌려줄 값을 정한다."""
    llm = agent.OpenAILLM("test-key", "test-model")
    monkeypatch.setattr(agent, "llm", llm)
    monkeypatch.setattr(agent.OpenAILLM, "usage", {"day": None, "calls": 0, "tokens": 0})
    monkeypatch.setenv("ALLOW_UPLOAD", "1")

    def answer(value):
        def chat(*_):
            if isinstance(value, Exception):
                raise value
            return value
        monkeypatch.setattr(llm, "_chat", chat)
    return answer


def extract(image=IMAGE):
    return api.post("/api/contracts/extract", json={"image": image})


def test_off_by_default_and_without_a_real_llm(monkeypatch):
    assert extract().status_code == 403  # 가짜 LLM
    monkeypatch.setattr(agent, "llm", agent.OpenAILLM("test-key", "test-model"))
    assert extract().status_code == 403  # 실제 LLM이어도 ALLOW_UPLOAD가 없으면 꺼짐
    assert api.get("/api/health").json()["upload"] is False


def test_reads_five_fields_and_marks_what_to_check(on):
    on(READ)
    res = extract().json()
    f = res["fields"]
    assert not res["llm_fallback"] and set(f) == set(agent.FIELDS)
    assert f["total_paid"] == {"value": 600000, "confidence": 0.9, "quote": "결제금액 600,000원", "check": False}
    assert f["end_date"]["check"]  # 확신도가 낮으면 사람이 확인한다
    assert f["special_terms"]["value"] is None and f["special_terms"]["check"]  # 못 읽은 값은 만들지 않는다
    assert set(res) == {"fields", "llm_fallback"}  # 사건을 만들지 않는다


def test_failure_returns_empty_fields_with_fallback(on):
    on(RuntimeError("down"))
    res = extract().json()
    assert res["llm_fallback"] and all(v["value"] is None and v["check"] for v in res["fields"].values())


def test_rejects_what_is_not_an_image(on):
    on(READ)
    assert extract("data:text/plain;base64,aGk=").status_code == 422
    assert extract("그냥 글").status_code == 422


def test_only_this_path_takes_a_photo_sized_body(on):
    on(READ)
    photo = "data:image/jpeg;base64," + "A" * (main.MAX_BODY_BYTES * 2)  # 다른 경로의 상한보다 크다
    assert extract(photo).status_code == 200
    assert api.post("/api/refund-preview", json={"image": photo}).status_code == 413
    too_big = "data:image/jpeg;base64," + "A" * (agent.MAX_IMAGE + 2048)
    assert extract(too_big).status_code == 413
