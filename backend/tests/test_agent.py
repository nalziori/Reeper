"""실제 LLM 구현을 키 없이 검사한다. OpenAI 응답은 가짜로 끼운다."""
import json
from datetime import date

import httpx
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
IMAGE = "data:image/png;base64,AAAA"


@pytest.fixture
def real(monkeypatch):
    """OpenAILLM을 끼우고, _chat이 돌려줄 값을 정하는 함수를 준다."""
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


def reply(text):
    case = open_case(CONTRACT, D).model_dump(mode="json")
    sent = api.post("/api/cases/step", json={"case": case, "today": str(D),
                                             "event": {"type": "notice_sent", "channel": "sms"}}).json()
    return api.post("/api/cases/step", json={"case": sent["case"], "today": str(D),
                                             "event": {"type": "reply_received", "text": text}}).json()


def test_llm_cannot_accept_a_low_offer_by_itself(real):
    real({"reply_type": "accept", "amount": 200_000})  # LLM이 수용이라고 해도
    res = reply("이십만원 환불해 드릴게요")
    assert res["case"]["stage"] == "negotiating" and res["action"]["warn"]  # 서버가 수용선과 비교한다
    assert not res["llm_fallback"]


def test_llm_reads_what_keywords_miss(real):
    real({"reply_type": "refuse", "amount": None})
    res = reply("60만원 결제하셨지만 이벤트 상품이라 어렵습니다")  # 키워드 판단은 60만원을 제시액으로 본다
    assert res["case"]["offered"] is None and "counter_refuse" in res["drafts"]


def test_failure_falls_back_to_keywords(real):
    real(httpx.ConnectError("down"))
    res = reply("20만원만 드릴게요")
    assert res["llm_fallback"] and res["case"]["offered"] == 200_000


def test_daily_limit_stops_real_calls(real, monkeypatch):
    monkeypatch.setattr(agent, "DAILY_LIMIT", 0)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("상한을 넘었는데 호출했다"))
    assert agent.read_reply("방문하셔야 합니다") == ("visit", None, True)
    assert api.get("/api/health").json()["calls_left"] == 0


def test_chat_sends_strict_schema_and_counts_tokens(real, monkeypatch):
    seen = {}

    def post(url, **kw):
        seen.update(kw["json"], auth=kw["headers"]["Authorization"])
        body = {"choices": [{"message": {"content": json.dumps({"reply_type": "visit", "amount": None})}}],
                "usage": {"total_tokens": 42}}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    assert agent.read_reply("오셔야 해요") == ("visit", None, False)
    assert seen["model"] == "test-model" and seen["auth"] == "Bearer test-key"
    assert seen["response_format"]["json_schema"]["strict"]
    assert agent.OpenAILLM.usage["calls"] == 1 and agent.OpenAILLM.usage["tokens"] == 42


def test_polish_keeps_only_text_with_the_same_numbers(real):
    case = open_case(CONTRACT, D)
    base = agent.render("notice_sms", case)
    body = {"case": case.model_dump(mode="json"), "kind": "notice_sms", "tone": "firm"}

    real({"text": base.replace("473,334", "500,000")})  # 금액을 바꿨다
    assert api.post("/api/drafts/polish", json=body).json() == {"text": base, "polished": False}
    real({"text": base + "\n민법 제999조에 따라 소송하겠습니다."})  # 없는 조문을 더했다
    assert not api.post("/api/drafts/polish", json=body).json()["polished"]
    real({"text": "확인 부탁드립니다. " + base})
    assert api.post("/api/drafts/polish", json=body).json()["polished"]
    real(RuntimeError("down"))
    assert api.post("/api/drafts/polish", json=body).json() == {"text": base, "polished": False}
    assert api.post("/api/drafts/polish", json={**body, "kind": "nope"}).status_code == 422


def test_extract_is_off_by_default_and_never_invents_values(real, monkeypatch):
    assert api.post("/api/contracts/extract", json={"image": IMAGE}).status_code == 403
    monkeypatch.setenv("ALLOW_UPLOAD", "1")
    assert api.post("/api/contracts/extract", json={"image": "http://x/a.png"}).status_code == 422

    real({"gym_name": {"value": "가상피트니스", "confidence": 0.95, "quote": "가상피트니스"},
          "total_paid": {"value": 600000, "confidence": 0.6, "quote": "결제 600,000"},
          "start_date": {"value": "2026년 11월", "confidence": 0.9, "quote": ""},
          "end_date": {"value": None, "confidence": 0.9, "quote": ""},
          "special_terms": {"value": "", "confidence": 1, "quote": ""}})
    f = api.post("/api/contracts/extract", json={"image": IMAGE}).json()["fields"]
    assert f["gym_name"] == {"value": "가상피트니스", "confidence": 0.95, "quote": "가상피트니스", "check": False}
    assert f["total_paid"]["value"] == 600000 and f["total_paid"]["check"]  # 확신도가 낮으면 확인받는다
    for name in ("start_date", "end_date", "special_terms"):  # 형식이 틀리거나 없는 값은 비운다
        assert f[name]["value"] is None and f[name]["check"]

    real(RuntimeError("down"))
    res = api.post("/api/contracts/extract", json={"image": IMAGE}).json()
    assert res["llm_fallback"] and all(v["value"] is None for v in res["fields"].values())
