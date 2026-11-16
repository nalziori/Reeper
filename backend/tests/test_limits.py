"""본문 크기 제한. 가짜 LLM으로 키 없이 돈다."""
from fastapi.testclient import TestClient

from app import main
from app.main import app

api = TestClient(app)
SMALL = {"contract": {"gym_name": "가상피트니스", "total_paid": 600_000,
                      "start_date": "2026-11-05", "end_date": "2027-02-02"}, "today": "2026-11-14"}


def test_small_request_passes():
    assert api.post("/api/refund-preview", json=SMALL).status_code == 200


def test_declared_content_length_over_limit_is_413():
    r = api.post("/api/refund-preview", content=b"{}",
                 headers={"content-type": "application/json", "content-length": str(main.MAX_BODY_BYTES + 1)})
    assert r.status_code == 413


def test_actual_oversize_body_is_413():
    r = api.post("/api/refund-preview", content=b" " * (main.MAX_BODY_BYTES + 1),
                 headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_streamed_body_without_length_is_413():
    chunks = (b"x" * 65_536 for _ in range(main.MAX_BODY_BYTES // 65_536 + 2))  # Content-Length 없는 스트리밍
    r = api.post("/api/refund-preview", content=chunks, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_get_is_unaffected():
    r = api.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True
