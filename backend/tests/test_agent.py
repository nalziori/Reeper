"""실제 LLM 구현을 키 없이 검사한다. OpenAI 응답은 가짜로 끼운다."""
import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import agent
from app.engine import POLICY, apply, next_action, open_case
from app.main import app
from app.models import Case, Contract, Event

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


def test_penalty_draft_survives_a_reply_recorded_right_after():
    """비율을 주장한 답 바로 뒤에 다른 답이 기록돼도(유형이 그대로 unknown이면) 비율 주장에 답하는 문안을 준다.

    기록에는 답장 유형이 없다. 협상 중 미루는 답을 기록만 하는 경우(#126)에도 last_reply는 그대로다."""
    case = apply(open_case(CONTRACT, D), Event(type="notice_sent", channel="sms"), D)
    case = apply(case, Event(type="reply_received", reply_type="unknown", text="위약금은 저희 규정상 20%입니다"), D)
    case = apply(case, Event(type="reply_received", reply_type="unknown", text="본사에 확인해 보고 연락드릴게요"), D)
    assert list(agent.drafts_for(case, next_action(case, D))) == ["counter_penalty"]
    # 반박을 보낸 뒤에 온 답은 새로 본다. 지난 비율 주장을 끌고 오지 않는다
    case = apply(case, Event(type="counter_sent"), D)
    case = apply(case, Event(type="reply_received", reply_type="unknown", text="본사 규정상 어렵네요"), D)
    assert list(agent.drafts_for(case, next_action(case, D))) == ["counter_unknown"]


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


def test_polish_keeps_the_account_slot_as_written(real):
    """화면이 계좌 자리 글자를 찾아 계좌로 바꾼다. 다듬은 글이 그 글자를 바꾸거나 빼면 원래 양식을 쓴다."""
    case = open_case(CONTRACT, D).model_copy(update={"offered": 460_000, "agreed_amount": 460_000})
    # 화면이 찾는 글자와 서버가 지키는 글자가 같아야 한다. 한쪽만 바뀌면 여기서 걸린다
    screen = (Path(__file__).parents[2] / "frontend" / "src" / "account.ts").read_text(encoding="utf-8")
    assert f"ACCOUNT_SLOT = '{agent.ACCOUNT_SLOT}'" in screen
    for kind in ("accept_offer", "confirm_agreement"):
        base = agent.render(kind, case)
        assert base.count(agent.ACCOUNT_SLOT) == 1  # 양식의 자리 글자가 바뀌면 여기서 걸린다
        real({"text": base.replace(agent.ACCOUNT_SLOT, "(은행/계좌번호/예금주)")})  # 띄어쓰기만 바꿨다
        assert agent.polished(kind, case, "polite") == (base, False)
        real({"text": base.replace(agent.ACCOUNT_SLOT, "(계좌)")})  # 자리를 줄였다
        assert agent.polished(kind, case, "polite") == (base, False)
        softer = base.replace("부탁드립니다", "부탁드리겠습니다", 1)  # 자리를 그대로 둔 글은 쓴다
        real({"text": softer})
        assert softer != base and agent.polished(kind, case, "polite") == (softer, True)


def test_polish_keeps_only_text_with_the_same_numbers(real):
    case = open_case(CONTRACT, D)
    base = agent.render("notice_sms", case)

    real({"text": base.replace("473,334", "500,000")})  # 금액을 바꿨다
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": base + "\n민법 제999조에 따라 소송하겠습니다."})  # 없는 조문을 더했다
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    real({"text": base + " 답이 없으면 법적 조치를 하겠습니다."})  # 양식에 없던 압박 표현
    assert agent.polished("notice_sms", case, "firm") == (base, False)
    # 첫 통지 문자에는 법 문장이 없다(근거는 업체가 다툴 때의 반박 문자부터 든다). 근거를 빼는 검사는 반박 문자로 본다
    assert "법률" not in base and "고시" not in base
    counter = agent.render("counter_refuse", case)
    real({"text": counter.replace("방문판매 등에 관한 법률 제31조에 따라 ", "")})  # 근거 언급을 뺐다
    assert agent.polished("counter_refuse", case, "firm") == (counter, False)
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


def test_analysis_is_told_when_the_disputed_offer_can_be_taken():
    """업체 사정 사건에서 다툴 때 금액 이상이면 화면에 받기 버튼이 있다(#171). 분석도 같은 조건을 받아 "합의로 읽힐 답 하지 마세요"
    대신 받을지는 소비자가 정한다고 말한다. 조건은 서버가 정하고 모델이 금액을 비교하지 않는다."""
    def after(case, amount):
        case = apply(case, Event(type="notice_sent", channel="sms"), D)
        case = apply(case, Event(type="reply_received", text="위약금 빼고 드릴게요", reply_type="low_offer", amount=amount), D)
        return case, next_action(case, D)
    theirs = fault_case("trainer_change")
    other = apply(theirs, Event(type="notice_sent", channel="sms"), D).refund.disputed_refund
    assert agent._can_take(*after(theirs, other)) and agent._can_take(*after(theirs, other + 1))
    assert not agent._can_take(*after(theirs, other - 1))
    assert not agent._can_take(*after(open_case(CONTRACT, D), 300_000))  # 소비자 사정은 그대로 경고만
    # 다툴 때 금액이 0원인 사건에 0원 제시: 하한선 경고는 뜨지만 0원 합의는 받을 수 없다(#175 C 리뷰)
    # 통지할 때 엔진이 환불액을 다시 계산하므로, 다툴 때 금액은 통지 뒤에 바꾼다
    noticed = apply(theirs, Event(type="notice_sent", channel="sms"), D)
    zero = noticed.model_copy(update={"refund": noticed.refund.model_copy(update={"disputed_refund": 0})})
    case = apply(zero, Event(type="reply_received", text="위약금 빼면 드릴 게 없습니다", reply_type="low_offer", amount=0), D)
    action = next_action(case, D)
    assert case.refund.disputed_refund == 0 and case.offered == 0 and action.warn and not agent._can_take(case, action)


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


def _request_line(case):
    return next(l for l in agent.render("go_1372", case).splitlines() if l.startswith("- 요청 금액"))


def test_go_1372_requests_the_unpaid_agreed_amount():
    """합의 뒤 입금이 안 돼 1372에 갈 때, 그대로 옮겨 쓰는 요청 금액이 계산액이 아니라 못 받은 합의 금액이다.

    계산액(473,334원)을 요청하면 합의(450,000원)보다 더 달라는 글이 되고, 일부를 받았으면 남은 금액도 안 보였다(Codex 교차 검증, #113 C 의견).
    """
    base = open_case(CONTRACT, D).model_copy(update={"notified_on": D, "deposit_due_on": D})
    assert base.refund.refund == 473_334
    none = _request_line(base)  # 합의가 없으면 지금처럼 계산액과 공제 내역
    assert none.startswith("- 요청 금액: 473,334원 (이용분")
    unpaid = base.model_copy(update={"stage": "agreed", "agreed_amount": 450_000, "deposited": 0})
    assert _request_line(unpaid) == "- 요청 금액: 450,000원 (합의한 금액, 아직 입금받지 못함. 참고: 계산한 환불액 473,334원)"
    part = unpaid.model_copy(update={"deposited": 100_000})
    assert _request_line(part) == "- 요청 금액: 350,000원 (합의한 금액 450,000원 중 100,000원만 받음. 참고: 계산한 환불액 473,334원)"
    handed = part.model_copy(update={"stage": "handed_off"})  # 1372에 접수한 뒤에도 같다
    assert _request_line(handed) == _request_line(part)
    same = part.model_copy(update={"agreed_amount": 473_334})  # 계산액대로 합의했으면 참고 금액을 되풀이하지 않는다
    assert _request_line(same) == "- 요청 금액: 373,334원 (합의한 금액 473,334원 중 100,000원만 받음)"
    more = unpaid.model_copy(update={"agreed_amount": 500_000})  # 계산액보다 많이 합의했으면 낮은 계산액을 먼저 꺼내지 않는다(A 리뷰 #116)
    assert _request_line(more) == "- 요청 금액: 500,000원 (합의한 금액, 아직 입금받지 못함)"
    paid = unpaid.model_copy(update={"deposited": 450_000})  # 다 받았으면 못 받은 금액이 없으니 계산액 줄로 둔다
    assert _request_line(paid) == none
    for c in (base, unpaid, part, handed, same, more, paid):
        assert agent.validate(agent.render("go_1372", c), c)


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


def test_the_model_is_given_the_screen_names_for_target_and_floor(real):
    """화면은 희망 금액·하한선(정하지 않았으면 예상 환불액)이라고 부른다. 모델에 옛 이름을 주면 글에 샌다."""
    sent = {}
    agent.llm._chat = lambda system, user, schema: sent.update(user=user, system=system) or {}
    case = apply(open_case(CONTRACT, D), Event(type="notice_sent", channel="sms"), D)
    case = apply(case, Event(type="reply_received", text=REPLY, reply_type="low_offer", amount=200_000), D)
    for c, name in ((case, "예상 환불액"), (case.model_copy(update={"floor": 300_000}), "하한선")):
        agent.analyze_reply(c, REPLY, next_action(c, D), D)
        assert f'"비교 기준 이름": "{name}"' in sent["user"] and "희망 금액" in sent["user"]
        assert "최저 수용선" not in sent["user"] + sent["system"] and "목표 금액" not in sent["user"]
        agent.plan(c, "상황", D)
        assert "최저 수용선" not in sent["user"] + sent["system"] and "목표 금액" not in sent["user"]


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


# ---- 업체 쪽 사정으로 해지하는 사건 ---------------------------------------------------------
def fault_case(kind="closure"):
    return open_case(CONTRACT.model_copy(update={"cancel_reason": "business", "fault_kind": kind}), D)


def test_drafts_can_say_why_and_drop_the_penalty_phrase():
    mine, theirs = open_case(CONTRACT, D), fault_case()
    a, b = agent.render("notice_sms", mine), agent.render("notice_sms", theirs)
    assert "개인 사정으로 회원권" in a and "과 위약금 60,000원" in a and agent.validate(a, mine)
    assert "휴업이나 시설 폐쇄로 계약한 시설을 이용할 수 없게 되어 회원권" in b and "위약금" not in b and agent.validate(b, theirs)
    assert agent.facts(fault_case(None))["why"] == "계약 내용과 다르게 운영되어"
    assert agent.facts(theirs)["penalty_part"] == ""
    assert "과 위약금 0원" in agent.render("notice_sms", open_case(CONTRACT.model_copy(update={"total_paid": 9}), D))

    counter = agent.render("counter_penalty", theirs)
    assert "제4조 제1항" in counter and f"{theirs.refund.refund:,}원" in counter
    assert "개인 사정" not in counter and "10%" not in counter and agent.validate(counter, theirs)


def test_an_offer_that_only_takes_the_penalty_off_gets_the_penalty_answer():
    """업체 쪽 사정 사건에서 "위약금 빼고 ○원"은 금액이 있어 low_offer로 읽힌다. 제시액이 다퉈질 때의 금액과 같으면 위약금 근거로 답한다."""
    def after(case, amount):
        case = apply(case, Event(type="notice_sent", channel="sms"), D)
        case = apply(case, Event(type="reply_received", text="위약금 빼고 넣어 드릴게요", reply_type="low_offer", amount=amount), D)
        return case, agent.drafts_for(case, next_action(case, D))

    theirs = fault_case()
    case, drafts = after(theirs, theirs.refund.disputed_refund)
    assert list(drafts) == ["counter_penalty"] and "제4조 제1항" in drafts["counter_penalty"]
    assert agent.validate(drafts["counter_penalty"], case)
    # 금액이 다르면 공제 항목을 되묻는 문안 그대로다. 소비자 사정 사건은 다퉈질 때의 금액이 없어 달라지지 않는다
    assert list(after(theirs, theirs.refund.disputed_refund - 10_000)[1]) == ["counter_low_offer"]
    assert list(after(open_case(CONTRACT, D), 300_000)[1]) == ["counter_low_offer"]


def test_business_case_never_spends_its_one_counter_on_a_holding_reply():
    """업체 쪽 사정 사건은 반박 한 번 뒤 1372다. "귀책이 없어 위약금을 부담할 수 없다"는 unknown으로 읽히는데,
    그 한 번이 "확인한 뒤 다시 연락드리겠습니다"이면 입장을 말하지 않고 넘어간다(2026-11-22 사용자가 배포에서 겪음).
    위약금·책임을 말한 답은 위약금 근거로, 접수 안내처럼 그런 말이 없는 답은 해지 이유와 금액을 다시 밝히는 문안으로 답한다(#166 A 리뷰)."""
    dispute = "새로운 강사로 변경해 드렸으니 저희 귀책이 없어 위약금을 부담할 수 없습니다."
    notice = "환불 요청은 접수했습니다. 처리 중입니다."
    for text in (dispute, notice):
        assert agent.FAKE.read_reply(text) == ("unknown", None)
    for case, text, want in ((fault_case("trainer_change"), dispute, "counter_penalty"),
                             (fault_case("trainer_change"), notice, "counter_refuse"),
                             (open_case(CONTRACT, D), dispute, "counter_unknown")):
        case = apply(case, Event(type="notice_sent", channel="sms"), D)
        case = apply(case, Event(type="reply_received", text=text, reply_type="unknown"), D)
        drafts = agent.drafts_for(case, next_action(case, D))
        assert list(drafts) == [want] and agent.validate(drafts[want], case)
        if case.contract.cancel_reason == "business":
            assert f"{case.refund.refund:,}원" in drafts[want] and "다시 연락드리겠습니다" not in drafts[want]
        if want == "counter_refuse":
            assert "약속한 강사" in drafts[want] and "위약금" not in drafts[want]


def test_refusal_counter_mentions_the_reason_only_for_business_cases():
    cases = (open_case(CONTRACT, D), fault_case("trainer_change"))
    texts = []
    for case in cases:
        case = apply(case, Event(type="notice_sent", channel="sms"), D)
        case = apply(case, Event(type="reply_received", reply_type="refuse"), D)
        text = agent.drafts_for(case, next_action(case, D))["counter_refuse"]
        assert agent.validate(text, case)
        texts.append(text)

    consumer, business = texts
    reason = "계약할 때 약속한 강사에게 수업을 받을 수 없게 되어"
    assert reason not in consumer and f"{reason} " in business
    assert "개인 사정으로" not in business


def test_reason_reaches_the_call_script_and_other_drafts_only_for_business_cases():
    reason = "휴업이나 시설 폐쇄로 계약한 시설을 이용할 수 없게 되어"
    mine, theirs = open_case(CONTRACT, D), fault_case("closure")
    for kind in ("call_card", "after_call_sms", "certified_mail", "follow_up"):
        a, b = agent.render(kind, mine), agent.render(kind, theirs)
        assert reason not in a and f"{reason} " in b, kind
        assert agent.validate(b, theirs) and "개인 사정으로" not in b, kind


def test_polish_keeps_the_business_reason_or_falls_back_to_the_template(real):
    case = apply(fault_case("closure"), Event(type="notice_sent", channel="sms"), D)
    reason = agent.why(case)
    for kind in ("after_call_sms", "certified_mail", "follow_up", "notice_sms"):  # call_card는 다듬지 않는 양식(NOT_SENT)이다
        base = agent.render(kind, case)
        assert base.count(reason) == 1, kind
        real({"text": base.replace(f"{reason} ", "", 1)})  # 사유만 뺀 글은 쓰지 않는다
        assert agent.polished(kind, case, "polite") == (base, False), kind
        softer = base.replace("부탁드립니다", "부탁드리겠습니다", 1).replace("요청드립니다", "요청드리겠습니다", 1)
        real({"text": softer})  # 사유를 그대로 둔 글은 쓴다
        if softer != base:
            assert agent.polished(kind, case, "polite") == (softer, True), kind


def test_every_template_still_passes_for_a_business_fault_case():
    case = apply(fault_case(), Event(type="notice_sent", channel="sms"), D)
    for kind in agent.TEMPLATES:
        text = agent.render(kind, case)
        assert agent.validate(text, case), kind
        assert "개인 사정으로" not in text and "위약금 0원" not in text, kind


def test_1372_request_line_has_no_penalty_when_none_was_deducted():
    assert "위약금" not in agent.facts(fault_case())["request"]
    assert "위약금 60,000원" in agent.facts(open_case(CONTRACT, D))["request"]


def test_the_model_learns_the_cancel_reason_only_for_business_cases(real):
    sent = {}
    agent.llm._chat = lambda system, user, schema: sent.update(user=user) or {}
    agent.plan(open_case(CONTRACT, D), "상황", D)
    assert "해지 이유" not in sent["user"]  # 소비자 사정 사건의 자료는 그대로다
    agent.plan(fault_case(), "상황", D)
    told = json.loads(sent["user"])["해지 이유"]
    # 업체가 다퉈 소비자 사정으로 계산될 때의 금액은 rules.py가 사건에 적어 둔 값이다(Refund.disputed_refund)
    assert told == {"소비자가 고른 것": "업체 쪽 사정", "유형": "휴업·폐업이나 시설 일부 폐쇄",
                    "업체가 다퉈 소비자 사정으로 계산될 때의 환불액": open_case(CONTRACT, D).refund.refund}
    case = fault_case()
    other = open_case(CONTRACT, D).refund.refund
    later = D + timedelta(days=3)
    assert open_case(CONTRACT, later).refund.refund != other
    agent.plan(case, "상황", later)
    assert json.loads(sent["user"])["해지 이유"]["업체가 다퉈 소비자 사정으로 계산될 때의 환불액"] == other
    wrong_date_amount = open_case(CONTRACT, later).refund.refund
    assert agent._problems(f"업체가 다투면 {wrong_date_amount:,}원이 될 수 있어요.", case, later)

    legacy = case.model_dump(mode="json")
    del legacy["refund"]["disputed_refund"]
    assert agent._if_disputed(Case.model_validate(legacy)) is None


def test_advice_may_quote_the_amount_if_the_fault_is_disputed():
    case, other = fault_case(), open_case(CONTRACT, D).refund.refund
    assert agent._problems(f"업체가 다투면 {other:,}원이 될 수 있어요.", case, D) == []
    assert agent._problems(f"업체가 다투면 {other:,}원이 될 수 있어요.", open_case(CONTRACT, D), D) == []  # 같은 금액
    assert agent._problems("업체가 다투면 400,000원이 될 수 있어요.", case, D)


def test_every_fault_kind_has_a_reason_phrase():
    # 유형이 늘면 사유 구절도 같이 있어야 한다(data/why.json). 구절에는 금액·조문·단정하는 말이 없다
    from typing import get_args
    from app.models import FaultKind
    assert set(agent.WHY) - {"_about"} == set(get_args(FaultKind)) | {"consumer"}
    for kind in get_args(FaultKind):
        phrase = agent.facts(fault_case(kind))["why"]
        assert phrase == agent.WHY[kind] and not agent._problems(phrase, fault_case(kind), D)
        assert not any(w in phrase for w in ("귀책", "잘못", "위반"))
