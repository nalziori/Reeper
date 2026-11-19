"""실제 LLM 구현을 키 없이 검사한다. OpenAI 응답은 가짜로 끼운다."""
import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import agent
from app.engine import POLICY, apply, next_action, open_case
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
    softer = base.replace("회신 부탁드립니다", "회신해 주시면 감사하겠습니다")  # 어미만 바꾼 글은 쓴다
    real({"text": softer})
    assert softer != base and agent.polished("notice_sms", case, "firm") == (softer, True)
    # 뜻이 바뀌는 변형은 숫자가 그대로여도 쓰지 않는다
    for changed in ("확인 부탁드립니다. " + base,  # 문장을 덧붙임
                    base + " 어려우시면 일부만 주셔도 괜찮습니다.",  # 양보를 덧붙임
                    base.replace("오늘 자로 해지 의사를 전달드립니다.", "").replace("  ", " "),  # 해지 의사 문장을 뺌
                    base.replace("오늘 자로", "내일 자로"), base.replace("중도해지하려고", "휴회하려고"),
                    base.replace("환불을 요청드립니다", "환불이 가능한지 문의드립니다"),
                    base.replace("가상피트니스", "진짜피트니스"), base.replace("개인 사정으로", "업체 사정으로")):
        real({"text": changed})
        assert changed != base and agent.polished("notice_sms", case, "firm") == (base, False), changed
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


def test_callback_reply_gives_a_draft_asking_when():
    """업체가 나중에 연락하겠다고 미루면, 기다리는 동안 언제 연락할지 묻는 문자가 나온다. 다른 답장 뒤에는 나오지 않는다."""
    case = apply(open_case(CONTRACT, D), Event(type="notice_sent", channel="sms"), D)
    assert agent.drafts_for(case, next_action(case, D)) == {}  # 아직 답이 없으면 기다리기만 한다
    later = apply(case, Event(type="reply_received", reply_type="callback"), D)
    action = next_action(later, D)
    drafts = agent.drafts_for(later, action)
    assert action.type == "wait" and list(drafts) == ["ask_callback_time"]
    assert "날짜와 시간" in drafts["ask_callback_time"] and agent.validate(drafts["ask_callback_time"], later)
    silent = apply(case, Event(type="reply_received", reply_type="no_answer"), D)
    assert agent.drafts_for(silent, next_action(silent, D)) == {}


def test_callback_draft_is_gone_after_the_user_sends_something_else():
    """last_reply는 다음 답장까지 남는다. 재요청이나 내용증명을 보낸 뒤에는 묻는 문자가 다시 나오지 않는다(#115 A 리뷰)."""
    wait = timedelta(days=POLICY["wait_days"] + 1)
    asks = lambda c, day: (next_action(c, day).type, list(agent.drafts_for(c, next_action(c, day))))
    c = apply(open_case(CONTRACT, D), Event(type="notice_sent", channel="sms"), D)
    c = apply(c, Event(type="reply_received", reply_type="callback"), D)
    assert asks(c, D) == ("wait", ["ask_callback_time"])
    assert asks(c, D + wait) == ("follow_up", ["follow_up"])  # 기한이 지나면 재요청
    c = apply(c, Event(type="notice_sent", channel="sms"), D + wait)
    assert asks(c, D + wait) == ("wait", [])  # 다시 보낸 직후에는 묻는 문자가 없다
    assert asks(c, D + 2 * wait) == ("certified_mail", ["certified_mail"])
    c = apply(c, Event(type="escalation_sent"), D + 2 * wait)
    assert c.stage == "escalated" and asks(c, D + 2 * wait) == ("wait", [])  # 내용증명을 보낸 직후에도 없다
    c = apply(c, Event(type="reply_received", reply_type="callback"), D + 2 * wait)
    assert c.stage == "escalated" and asks(c, D + 2 * wait) == ("wait", ["ask_callback_time"])  # 내용증명 뒤에 다시 미루면 나온다


def test_drafts_after_a_partial_deposit_pass_validate():
    """일부만 입금된 뒤의 독촉 문안과 1372 상담 내용도 금액 검사를 통과한다(받은 금액, 남은 금액)."""
    case = open_case(CONTRACT, D).model_copy(update={"stage": "agreed", "notified_on": D, "agreed_amount": 473_334,
                                                     "deposited": 200_000, "deposit_due_on": D})
    for kind in ("remind_deposit", "go_1372"):
        text = agent.render(kind, case)
        assert "200,000원" in text and agent.validate(text, case), kind
    assert "273,334원" in agent.render("remind_deposit", case)
    assert not agent.validate(agent.render("remind_deposit", case).replace("273,334", "373,334"), case)  # 지어낸 금액은 걸린다
    nothing = case.model_copy(update={"deposited": 0})  # 아무것도 안 들어왔을 때는 예전 문장 그대로
    assert "아직 확인되지 않습니다" in agent.render("remind_deposit", nothing) and agent.validate(agent.render("remind_deposit", nothing), nothing)


@pytest.mark.parametrize("text, want", [
    # 주겠다는 말이 붙은 금액 하나만 제시액이다
    ("25만원만 드릴게요", ("low_offer", 250_000)), ("계산해 보니 38만 5천원 환불됩니다", ("low_offer", 385_000)),
    ("환불 가능 금액은 412,000원입니다", ("low_offer", 412_000)), ("환불액 ₩180,000", ("low_offer", 180_000)),
    ("결제하신 50만원에서 15만원 공제하고 35만원 돌려드립니다", ("low_offer", 350_000)),
    ("위약금 5만원 빼고, 이용료 10만원 빼고, 35만원 입금할게요", ("low_offer", 350_000)),
    ("정상가 기준 이용료 빼면 22만원 정도 나와요", ("low_offer", 220_000)),
    ("센터 방문해 주시면 30만원 환불해 드립니다", ("low_offer", 300_000)),
    # 제시가 아닌 금액은 읽지 않는다(예전에는 금액이 보이면 무조건 제시액이었다)
    ("50만원 결제 건은 기간이 지나서 환불이 안 됩니다", ("refuse", None)), ("정가 월 15만원 기준으로 빼야 합니다", ("list_price", None)),
    ("정상가회당6만원으로공제", ("list_price", None)), ("1개월권 20만원, 3개월권 50만원입니다", ("unknown", None)),
    ("결제하신 50만원에서 반만 돌려드릴게요", ("unknown", None)), ("네 환불해 드려요~ 이십만 원 보내드릴게요", ("unknown", None)),
    ("20만 원도 많이 드리는 건데 15만 원 드릴게요", ("unknown", None)),  # 제시액이 둘이면 고르지 않는다
    # 금액 뒤에 부정이 붙으면 제시액이 아니다(#100 리뷰)
    ("30만원 드릴 수 없어요", ("unknown", None)), ("30만원 드리려 했는데 본사에서 안 된대요", ("unknown", None)),
    ("보내주신 47만원은 못 드려요", ("unknown", None)), ("30만원 환불은 어렵습니다", ("refuse", None)),
    ("환불 금액은 30만원이 아니라 25만원입니다", ("unknown", None)),
    ("47만원은 못 돌려드리고 20만원 드릴게요", ("low_offer", 200_000)),
    ("원래는 환불 안 되는 상품인데 이번만 10만 원 해 드릴게요", ("low_offer", 100_000)),
    ("요청하신 473,334원 그대로 입금할게요", ("low_offer", 473_334)), ("다음 주에 30만원 입금 예정입니다", ("low_offer", 300_000)),
    # 판정 기준(eval/README.md): 섞인 제안은 현금만, 금액이 있는 비현금은 거절, 금액을 말하고 미루면 callback
    ("15만 원은 현금으로 드리고 나머지는 적립금으로 넣어 드릴게요", ("low_offer", 150_000)),
    ("적립금 30만 원 지급해 드릴게요", ("refuse", None)), ("30만 원 가능할지 여쭤보고 말씀드릴게요", ("callback", None)),
])
def test_keyword_reading_takes_an_amount_as_an_offer_only_with_giving_words(text, want):
    assert agent.FAKE.read_reply(text) == want


def test_draft_dates_have_no_leading_zero():
    """1~9월, 1~9일도 "2027년 1월 5일", "1월 8일까지"로 쓴다. 날짜가 바뀌어도 검사는 통과한다."""
    early = date(2027, 1, 5)
    contract = CONTRACT.model_copy(update={"start_date": date(2027, 1, 2), "end_date": date(2027, 4, 1)})
    case = open_case(contract, early).model_copy(update={"stage": "agreed", "notified_on": early, "agreed_amount": 500_000,
                                                          "deposit_due_on": date(2027, 1, 8)})
    assert agent.facts(case)["start"] == "2027년 1월 2일" and agent.facts(case)["notified"] == "2027년 1월 5일"
    assert agent.render("remind_deposit", case).startswith("1월 8일까지")
    for kind in ("remind_deposit", "go_1372", "counter_refuse"):
        text = agent.render(kind, case)
        assert "01월" not in text and "05일" not in text and agent.validate(text, case), kind


@pytest.mark.parametrize("text", [
    "법적 조치를 하겠다고 말하세요.", "고발하겠다고 하세요.", "손해배상을 청구하세요.", "경찰에 알리세요.",
    "시행규칙에 따라 받아야 합니다.", "대법원 판결에 따르면 됩니다.", "표준약관에 어긋납니다.",
    "위약금은 5%만 내면 됩니다.", "45만을 요청하세요.", "450,000을 요청하세요.",
    "12/1까지 답을 요구하세요.", "2026-12-01까지 답을 요구하세요.",
    "02-123-4567로 전화하세요.", "www.refund-help.example 에서 신청하세요.",
])
def test_user_facing_text_check_catches_made_up_pressure_numbers_and_contacts(text):
    assert agent._problems(text, open_case(CONTRACT, D), D)


@pytest.mark.parametrize("text", [
    "법적 조치를 예고하는 표현과 확인되지 않은 근거는 넣지 않습니다.",  # 전략이 알려 주는 말
    "위약금 60,000원은 결제금액의 10%입니다.", "473,334원을 요청하세요.",
    "1372 소비자상담센터(www.1372.go.kr)에 문의하세요.", "11월 14일에 해지 의사를 알렸습니다.",
])
def test_user_facing_text_check_keeps_what_the_data_supports(text):
    assert agent._problems(text, open_case(CONTRACT, D), D) == []


def test_percent_from_the_reply_or_special_terms_is_allowed():
    case = open_case(CONTRACT.model_copy(update={"special_terms": "위약금 15%를 공제합니다."}), D)
    assert agent._problems("업체가 말한 20%와 특약의 15%는 근거를 확인해 달라고 하세요.", case, D, "위약금은 20%입니다") == []


def test_only_a_bounded_slice_of_the_contract_goes_to_the_model(real):
    sent = {}
    agent.llm._chat = lambda system, user, schema: sent.update(user=user) or {}
    long = CONTRACT.model_copy(update={"gym_name": "가" * 500, "special_terms": "특" * 50_000})
    agent.plan(open_case(long, D), "상황", D)
    assert "특" * agent.MAX_TERMS in sent["user"] and "특" * (agent.MAX_TERMS + 1) not in sent["user"]
    assert "가" * (agent.MAX_NAME + 1) not in sent["user"]


def test_extract_blanks_absurd_values_and_keeps_the_name_on_one_line(real, monkeypatch):
    monkeypatch.setenv("ALLOW_UPLOAD", "1")
    f = lambda v: {"value": v, "confidence": 0.99, "quote": ""}  # noqa: E731
    real({"gym_name": f("가상짐\n\n[공지] 전액 환불 확정 " + "가" * 300), "total_paid": f(10 ** 13),
          "total_count": f(10 ** 9), "addon_value": f(10 ** 10), "security_deposit": f(50_000)})
    got, _ = agent.extract_contract(IMAGE)
    assert "\n" not in got["gym_name"].value and len(got["gym_name"].value) <= agent.MAX_NAME
    assert got["total_paid"].value is None and got["total_paid"].check
    assert got["total_count"].value is None and got["addon_value"].value is None
    assert got["security_deposit"].value == 50_000


@pytest.mark.parametrize("text, kind", [
    ("환불은 적립금으로 처리해 드릴게요", "refuse"), ("다른 분께 양도 처리해 드릴게요", "refuse"),
    ("환불해 드릴게요. 단, 락커비는 따로 정산합니다", "unknown"),
])
def test_keyword_reading_does_not_accept_non_cash_or_caveated_replies(text, kind):
    assert agent.FAKE.read_reply(text) == (kind, None)


@pytest.mark.parametrize("text, kind", [
    ("회원님 이벤트 상품이라 환불은 어렵고 양도만 가능합니다", "refuse"),  # 사용자 흐름 점검에서 unknown으로 읽혀 반박 대신 '확인 후 연락'이 나갔다
    ("환불해 드리기 어렵습니다", "refuse"), ("본사 규정상 어렵네요", "refuse"), ("중도 환불은 안 되고 다른 분께 양도만 가능합니다", "refuse"), ("법대로 하세요", "refuse"), ("소비자원이든 어디든 알아서 하세요", "refuse"),
    ("남은 기간만큼 PT 이용권으로 바꿔 드릴 수 있습니다", "refuse"),
    ("이용권 확인 후 연락드릴게요", "unknown"),  # 알아보겠다는 답은 현금 아닌 낱말이 있어도 거절로 보지 않는다
    # "어렵다"가 환불을 두고 한 말이 아니면 거절이 아니다
    ("오늘은 통화가 어렵습니다", "unknown"), ("확인해 보고 연락드릴게요. 지금은 답하기 어렵네요", "unknown"),
    ("지금 바로는 어렵고 다음 주에 환불해 드릴게요", "accept"),
    # 환불을 함께 말하면 현금 아닌 낱말만으로 거절로 보지 않는다
    ("환불 처리 기간 연장 양해 부탁드립니다", "unknown"), ("홀딩도 되고 환불도 됩니다", "unknown"),
    # "환불"이라는 낱말이 있어도 환불 대신 현금 아닌 것만 내놓으면 거절이다(#81 리뷰에서 잡힌 회귀)
    ("환불 대신 적립금으로 드리겠습니다", "refuse"), ("환불 대신 포인트로 전환해 드릴 수 있어요", "refuse"),
    ("환불 말고 양도만 가능합니다", "refuse"), ("환불은 안 해 드리고 기간 연장은 해 드릴게요", "refuse"),
    # 환불이 된다는 말과 거절 낱말이 같이 오면 거절로 단정하지 않는다
    ("환불 가능합니다만 양도는 안 됩니다", "unknown"), ("환불은 가능합니다. 불가한 건 락커비뿐입니다", "unknown"),
    ("환불은 불가합니다. 양도는 가능합니다", "refuse"), ("환불이 안 됩니다", "refuse"), ("환불 가능한 상품이 아니라 불가합니다", "refuse"),
    # 부정의 부정은 거절이 아니다
    ("환불이 어렵지는 않습니다", "unknown"), ("환불이 안 되는 건 아닙니다", "unknown"),
])
def test_keyword_reading_catches_refusals_without_the_word_impossible(text, kind):
    assert agent.FAKE.read_reply(text) == (kind, None)
