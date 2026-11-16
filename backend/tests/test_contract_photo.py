"""POST /api/contracts/extract: 사진 읽기는 꺼져 있으면 403, 켜져 있으면 값과 확인 여부를 돌려준다. 키 없이 돈다."""
import pytest
from fastapi.testclient import TestClient

from app import agent, main
from app.main import app

api = TestClient(app)
IMAGE = "data:image/png;base64,AAAA"
READ = {
    "gym_name": {"value": "가상피트니스", "confidence": 0.95, "quote": "상호: 가상피트니스"},
    "total_paid": {"value": 600000, "confidence": 0.9, "quote": "결제금액 600,000원"},
    "start_date": {"value": "2026-11-05", "confidence": 0.5, "quote": "2026.11.5"},
    "end_date": {"value": "2027-02-02", "confidence": 0.9, "quote": "2027.2.2"},
    "special_terms": {"value": None, "confidence": 0.0, "quote": ""},
}


def extract(image=IMAGE):
    return api.post("/api/contracts/extract", json={"image": image})


@pytest.fixture
def real(monkeypatch):
    """사진 읽기를 켜고 OpenAILLM을 끼운다. _chat이 돌려줄 값을 정하는 함수를 준다."""
    monkeypatch.setenv("ALLOW_UPLOAD", "1")
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


def test_upload_is_off_by_default():
    res = extract()
    assert res.status_code == 403 and "직접 입력" in res.json()["detail"]


def test_reads_fields_and_marks_low_confidence_for_checking(real):
    real(READ)
    res = extract()
    assert res.status_code == 200
    body = res.json()
    assert body["llm_fallback"] is False
    f = body["fields"]
    assert f["gym_name"]["value"] == "가상피트니스" and f["gym_name"]["check"] is False
    assert f["total_paid"]["value"] == 600000
    assert f["start_date"]["check"] is True  # 확신도 0.5는 사람이 확인한다
    assert f["special_terms"]["value"] is None and f["special_terms"]["check"] is True


def test_llm_failure_returns_empty_fields_to_type_in(real):
    real(RuntimeError("down"))
    body = extract().json()
    assert body["llm_fallback"] is True
    assert all(v["value"] is None and v["check"] for v in body["fields"].values())


@pytest.mark.parametrize("image", ["data:image/gif;base64,AAAA", "https://example.com/a.png", ""])
def test_rejects_non_image_input(real, image):
    real(READ)
    assert extract(image).status_code == 422


def test_photo_path_has_its_own_body_limit():
    big = "data:image/jpeg;base64," + "A" * (main.MAX_BODY_BYTES * 2)  # 전역 한도는 넘지만 사진 한도 안이다
    assert extract(big).status_code == 403  # 꺼져 있어서 거절되지만 413은 아니다
    other = api.post("/api/refund-preview", content=b" " * (main.MAX_BODY_BYTES + 1),
                     headers={"content-type": "application/json"})
    assert other.status_code == 413  # 다른 경로의 전역 한도는 그대로다
    too_big = api.post("/api/contracts/extract", content=b"{}",
                       headers={"content-type": "application/json", "content-length": str(main.PHOTO_BODY_BYTES + 1)})
    assert too_big.status_code == 413
