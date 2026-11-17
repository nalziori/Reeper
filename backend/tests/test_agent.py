"""실제 LLM 구현을 키 없이 검사한다. OpenAI 응답은 가짜로 끼운다."""
import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import agent
from app.engine import apply, next_action, open_case
from app.main import app
from app.models import Contract, Event

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
    real({"reply_type": "list_price", "amount": 150_000})  # 월 정상가를 제시액으로 잘못 읽어도 버린다
    res = reply("정상가 월 15만원 기준으로 차감합니다")
    assert res["case"]["offered"] is None and "counter_list_price" in res["drafts"]


def test_zero_won_offer_is_an_offer(real):
    real({"reply_type": "low_offer", "amount": 0})  # 0원 제시는 금액 없음과 다르다
    res = reply("계산해 보니 환불 가능 금액은 0원입니다.")
    assert res["case"]["offered"] == 0 and res["action"]["warn"]
    assert "말씀하신 0원" in res["drafts"]["counter_low_offer"]


def test_penalty_rate_claim_gets_the_penalty_draft(real):
    real({"reply_type": "unknown", "amount": None})  # 금액 없이 위약금 비율만 주장한 답은 맞는 유형이 없다
    res = reply("환불해 드리긴 하는데 위약금은 저희 규정상 20%입니다.")
    assert list(res["drafts"]) == ["counter_penalty"] and "위약금은 60,000원" in res["drafts"]["counter_penalty"]
    res = api.post("/api/cases/step", json={"case": res["case"], "today": str(D + timedelta(days=1)),
                                            "event": {"type": "time_passed"}}).json()
    assert list(res["drafts"]) == ["counter_penalty"]  # 날짜가 지나도 같은 문안이다
    assert list(reply("본사 규정상 어렵네요")["drafts"]) == ["counter_unknown"]  # 다른 unknown은 그대로다


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
    # 붙여 넣다 섞인 줄바꿈·공백·따옴표는 떼고 보낸다
    monkeypatch.setattr(agent, "llm", agent.OpenAILLM(' "test-key"\r\n', " test-model\n"))
    assert agent.read_reply("오셔야 해요") == ("visit", None, False)
    assert seen["model"] == "test-model" and seen["auth"] == "Bearer test-key"


def test_polish_keeps_only_text_with_the_same_numbers(real):
    case = open_case(CONTRACT, D)
    base = agent.render("notice_sms", case)

    real({"text": base.replace("473,334", "500,000")})  # 금액을 바꿨다
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": base + "\n민법 제999조에 따라 소송하겠습니다."})  # 없는 조문을 더했다
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": base + " 답이 없으면 법적 조치를 하겠습니다."})  # 양식에 없던 압박 표현
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": base.replace("방문판매 등에 관한 법률 제31조와 ", "")})  # 근거 언급을 뺐다
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": base + " " + "빠른 처리를 거듭 부탁드립니다. " * 8})  # 문장을 덧붙여 길어졌다
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": "확인 부탁드립니다. " + base})
    assert agent.polished("notice_sms", case, "firm") == ("확인 부탁드립니다. " + base, True)
    real(RuntimeError("down"))
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    # 업체에 보내는 글이 아닌 양식(통화 카드, 1372 상담 신청 내용)은 모델을 부르지 않고 그대로 둔다
    agent.llm.polish = lambda *_: pytest.fail("보내지 않는 양식인데 모델을 불렀다")
    for kind in agent.NOT_SENT:
        assert agent.polished(kind, case, "firm") == (agent.render(kind, case), False)


def test_extract_is_off_by_default_and_never_invents_values(real, monkeypatch):
    with pytest.raises(PermissionError):
        agent.extract_contract(IMAGE)
    monkeypatch.setenv("ALLOW_UPLOAD", "1")
    with pytest.raises(ValueError):
        agent.extract_contract("http://x/a.png")

    real({"gym_name": {"value": "가상피트니스", "confidence": 0.95, "quote": "가상피트니스"},
          "total_paid": {"value": 600000, "confidence": 0.6, "quote": "결제 600,000"},
          "start_date": {"value": "2026년 11월", "confidence": 0.9, "quote": ""},
          "end_date": {"value": None, "confidence": 0.9, "quote": ""},
          "special_terms": {"value": "", "confidence": 1, "quote": ""}})
    f, failed = agent.extract_contract(IMAGE)
    assert not failed and f["gym_name"].model_dump() == {
        "value": "가상피트니스", "confidence": 0.95, "quote": "가상피트니스", "check": False}
    assert f["total_paid"].value == 600000 and f["total_paid"].check  # 확신도가 낮으면 확인받는다
    for name in ("start_date", "end_date", "special_terms"):  # 형식이 틀리거나 없는 값은 비운다
        assert f[name].value is None and f[name].check
    assert all(f[name].value is None for name in agent.MORE_FIELDS)  # 응답에 없는 값도 비운다

    real({"unit": {"value": "count", "confidence": 0.9, "quote": "총 30회"},
          "total_count": {"value": 30, "confidence": 0.9, "quote": "총 30회"},
          "addon_value": {"value": 0, "confidence": 0.9, "quote": ""},
          "security_deposit": {"value": 50000, "confidence": 0.5, "quote": "보증금 50,000원"}})
    f, _ = agent.extract_contract(IMAGE)
    assert (f["unit"].value, f["total_count"].value, f["addon_value"].value) == ("count", 30, None)
    assert f["security_deposit"].value == 50000 and f["security_deposit"].check
    real({"unit": {"value": "week", "confidence": 1, "quote": ""}})  # 정해진 단위가 아니면 비운다
    assert agent.extract_contract(IMAGE)[0]["unit"].value is None

    real(RuntimeError("down"))
    f, failed = agent.extract_contract(IMAGE)
    assert failed and all(v.value is None for v in f.values())


REPLY = "정상가 기준으로 빼면 20만원 정도 나와요. 그걸로 처리해 드릴게요."


def analyze(real, claims, note=""):
    """20만 원을 제시받은 사건에 LLM 분석을 끼워 analyze_reply를 부른다."""
    case = apply(open_case(CONTRACT, D), Event(type="notice_sent", channel="sms"), D)
    case = apply(case, Event(type="reply_received", text=REPLY, reply_type="low_offer", amount=200_000), D)
    real({"claims": claims, "note": note} if not isinstance(claims, Exception) else claims)
    return agent.analyze_reply(case, REPLY, next_action(case, D), D)


def claim(**over):
    return {"quote": "정상가 기준으로 빼면 20만원", "claim": "정상가로 공제해 20만 원을 주겠다", "rule_id": None,
            "advice": "제시액 200,000원은 계산한 473,334원과 차이가 있으니 계산 내역을 다시 요청하세요.", **over}


def test_analysis_keeps_grounded_claims(real):
    out = analyze(real, [claim()], "최저 수용선보다 적은 금액이니 바로 받아들이지 마세요.")
    assert out == {"claims": [claim()], "note": "최저 수용선보다 적은 금액이니 바로 받아들이지 마세요.",
                   "fallback": False}


def test_analysis_drops_what_is_not_in_the_material(real):
    out = analyze(real, [
        claim(quote="환불은 절대 안 됩니다"),  # 답장에 없는 인용
        claim(advice="350,000원까지는 받을 수 있다고 하세요."),  # 지어낸 금액
        claim(advice="민법 제750조를 들어 다시 요청하세요."),  # 법령 이름과 조문
        claim(advice="소비자기본법에 따라 요청하세요."),
        claim(advice="계속거래 위약금 산정기준에 따라 요청하세요."),
        claim(advice="정상가 차감은 무효라고 답하세요."),  # 단정
        claim(advice="12월 25일까지 입금하라고 하세요."),  # 사건에 없는 날짜
    ], "응하지 않으면 소송하겠다고 하세요.")
    assert out == {"claims": [], "note": "", "fallback": False}
    ordinary = claim(advice="계약할 때 가액과 산정기준을 안내받았는지 확인하세요.")  # 법령 이름이 아닌 보통 말
    assert analyze(real, [ordinary])["claims"] == [ordinary]


def test_step_carries_the_analysis_only_for_pasted_replies(real):
    real({"reply_type": "low_offer", "amount": 200_000, "claims": [claim(), claim(quote="없는 말")], "note": ""})
    res = reply(REPLY)
    assert res["analysis"] == {"claims": [claim()], "note": ""} and not res["llm_fallback"]
    assert res["action"]["warn"] and "counter_low_offer" in res["drafts"]  # 단계와 문안은 그대로다

    sent = apply(open_case(CONTRACT, D), Event(type="notice_sent", channel="sms"), D).model_dump(mode="json")
    button = api.post("/api/cases/step", json={"case": sent, "today": str(D), "event": {
        "type": "reply_received", "reply_type": "refuse"}}).json()
    assert button["analysis"] is None  # 버튼으로 고른 답은 LLM을 거치지 않는다

    real(httpx.ConnectError("down"))
    res = reply(REPLY)
    assert res["analysis"] is None and res["llm_fallback"] and res["case"]["offered"] == 200_000


def test_analysis_is_empty_without_a_real_llm_and_flags_failure(real, monkeypatch):
    assert analyze(real, RuntimeError("down")) == {"claims": [], "note": "", "fallback": True}
    monkeypatch.setattr(agent, "llm", agent.FAKE)
    assert analyze(real, [claim()]) == {"claims": [], "note": "", "fallback": False}


SITUATION = "다음 달에 이사 가서 더 못 다녀요. 위약금 없이 60만원 전액 받고 싶어요."
TERMS = "이벤트 상품은 환불이 불가합니다."
NO_PLAN = {"summary": "", "grounds": [], "contract_points": [], "objections": [], "cautions": [], "questions": [],
           "dropped": 0, "fallback": False}


def strategy(real, out):
    """환불 불가 특약이 있는 계약과 전액을 바라는 상황 설명에 LLM 전략을 끼워 plan을 부른다."""
    case = open_case(CONTRACT.model_copy(update={"special_terms": TERMS}), D)
    real(out)
    return agent.plan(case, SITUATION, D)


def good_plan(**over):
    return {"summary": "473,334원 환불을 요청하세요. 결제금액 600,000원에서 이용분 66,666원과 위약금 60,000원을 뺀 금액이에요.",
            "grounds": [{"rule_id": "R31", "why": "환불 불가 특약이 있어도 기간 중 해지를 요청할 수 있어요."}],
            "contract_points": [{"quote": "이벤트 상품은 환불이 불가합니다.", "how_to_handle": "특약만으로 요청을 접지 마세요."}],
            "objections": [{"objection": "이벤트 상품이라 환불이 안 됩니다",
                            "response": "기간 중 해지를 요청할 수 있다는 점을 들어 다시 요청하세요."}],
            "cautions": ["이사 사정만으로 위약금 60,000원이 없어지지는 않아요. 600,000원 전액은 요청하기 어려워요.",
                         "하루 늦게 알리면 6,667원씩 줄어요."],
            "questions": ["사은품이나 운동복을 받은 것이 있나요?"], **over}


def test_plan_keeps_grounded_strategy(real):
    assert strategy(real, good_plan()) == {**good_plan(), "dropped": 0, "fallback": False}


def test_plan_drops_what_is_not_in_the_material(real):
    out = strategy(real, good_plan(
        summary="환불 불가 특약은 무효이니 500,000원을 요청하세요.",  # 단정, 지어낸 금액
        grounds=[{"rule_id": "X99", "why": "표에 없는 근거"},
                 {"rule_id": "R31", "why": "민법 제750조에 따라 요청하세요."}],  # 법령 이름과 조문
        contract_points=[{"quote": "환불은 30일 이내만 가능합니다.", "how_to_handle": "확인하세요."}],  # 특약에 없는 인용
        objections=[{"objection": "환불 불가", "response": "소송하겠다고 하세요."}],
        cautions=["350,000원까지는 받을 수 있어요.", ""],
        questions=["12월 25일에 결제하셨나요?", 3]))  # 사건에 없는 날짜, 글이 아닌 값
    assert out == {**NO_PLAN, "dropped": 9}  # 요약 1, 근거 2, 특약 1, 반론 1, 주의 2, 질문 2


def test_plan_is_empty_without_a_real_llm_and_survives_bad_output(real, monkeypatch):
    assert strategy(real, {"reply_type": "refuse"}) == NO_PLAN  # 형식이 어긋난 응답
    assert strategy(real, RuntimeError("down")) == {**NO_PLAN, "fallback": True}
    monkeypatch.setattr(agent, "llm", agent.FAKE)
    assert strategy(real, good_plan()) == NO_PLAN


@pytest.mark.parametrize("broken", ["down", "limit"])
def test_case_closes_with_templates_when_the_llm_is_down_or_over_the_limit(real, monkeypatch, broken):
    """LLM이 내내 실패하거나 하루 상한을 넘어도, 접수부터 입금 확인까지 고정 양식과 키워드 판단으로 끝난다."""
    if broken == "limit":
        monkeypatch.setattr(agent, "DAILY_LIMIT", 0)
        monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("상한을 넘었는데 호출했다"))
    else:
        real(httpx.ConnectError("down"))

    def step(case, **event):
        res = api.post("/api/cases/step", json={"case": case, "today": str(D), "event": event})
        assert res.status_code == 200
        return res.json()

    case = open_case(CONTRACT, D).model_dump(mode="json")
    plan = api.post("/api/cases/strategy", json={"case": case, "situation": "이사를 가요", "today": str(D)}).json()
    assert plan["llm_fallback"] and plan["case"]["strategy"] is None  # 전략은 비지만 사건은 그대로 간다
    res = step(plan["case"], type="notice_sent", channel="sms")
    tone = api.post("/api/drafts/polish", json={"case": res["case"], "kind": "follow_up", "tone": "polite"}).json()
    assert not tone["polished"] and agent.validate(tone["text"], agent.Case.model_validate(res["case"]))  # 원래 양식 그대로
    res = step(res["case"], type="reply_received", text="20만원만 드릴게요")
    assert res["llm_fallback"] and res["analysis"] is None
    assert res["case"]["stage"] == "negotiating" and res["case"]["offered"] == 200_000 and res["action"]["warn"]
    assert all(agent.validate(text, agent.Case.model_validate(res["case"])) for text in res["drafts"].values())
    res = step(res["case"], type="counter_sent")
    res = step(res["case"], type="reply_received", text="네 알겠습니다 환불해 드릴게요")
    assert res["llm_fallback"] and res["case"]["stage"] == "agreed" and res["case"]["agreed_amount"] == 473_334
    res = step(res["case"], type="deposit_confirmed")
    assert res["case"]["stage"] == "closed" and res["action"]["type"] == "close"


@pytest.mark.parametrize("text, kind", [
    ("네 알겠습니다 환불해 드릴게요", "accept"),
    ("확인했습니다. 요청하신 대로 처리해 드릴게요.", "accept"),
    ("환불해 드릴게요. 위약금 30% 빼고요", "unknown"),  # 조건이 붙었다
    ("환불해 드리긴 하는데 수수료는 제외됩니다", "unknown"),
    ("알겠습니다. 검토 후 처리해 드릴게요", "callback"),  # 미루는 답
    ("알겠습니다. 담당자에게 전달해 드릴게요", "callback"),
])
def test_keyword_reading_does_not_accept_conditional_or_deferred_replies(text, kind):
    assert agent.FAKE.read_reply(text) == (kind, None)


def test_conditional_reply_does_not_agree_when_the_llm_is_down(real):
    real(httpx.ConnectError("down"))  # 실제 LLM이 실패해 키워드 판정으로 넘어간 경우
    res = reply("환불해 드릴게요. 위약금 30% 빼고요")
    assert res["llm_fallback"] and res["case"]["stage"] != "agreed" and res["case"]["agreed_amount"] is None
