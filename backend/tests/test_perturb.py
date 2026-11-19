import importlib.util
from pathlib import Path
from typing import get_args

from app import agent
from app.models import ReplyType

PERTURB = Path(__file__).resolve().parents[2] / "eval" / "perturb.py"
spec = importlib.util.spec_from_file_location("eval_perturb", PERTURB)
perturb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perturb)


def row(id_, text, kind, amount=None):
    return {"id": id_, "text": text, "reply_type": kind, "amount": amount}


def test_every_rule_has_a_kind_and_one_line():
    assert {k for k, _ in perturb.RULES.values()} == {"불변", "방향"}
    for _, line in perturb.RULES.values():
        assert line.endswith("다.") and "\n" not in line


def test_amount_words():
    assert perturb.hangul(400000) == "사십만 원"
    assert perturb.hangul(285000) == "이십팔만 오천 원"
    assert perturb.hangul(473334) == "사십칠만 삼천삼백삼십사 원"
    assert perturb.hangul(10000) == "만 원"
    assert perturb.man(400000) == "40만원"
    assert perturb.man(285000) == "28만 5천원"
    assert perturb.man(473334) == "47만 3,334원"
    assert perturb.comma(450000) == "450,000원"


def found(text, n):
    return [(text[s:e], style) for s, e, style in perturb.find(text, n)]


def test_find_the_offer_and_not_a_bigger_number():
    assert found("결제하신 60만원에서 20만원 공제하고 40만원 돌려드립니다.", 400000) == [("40만원", "man")]
    assert found("₩450,000 환불 가능합니다.", 450000) == [("₩450,000", "comma")]
    assert found("삼십만 원도 많이 드리는 건데, 이십오만 원 선에서", 250000) == [("이십오만 원", "hangul")]
    assert found("이용일수 계산해서 28만 5천원 환불", 285000) == [("28만 5천원", "man")]
    assert found("이용료 38만원, 위약금 9만원", 380000) == [("38만원", "man")]  # 뒤 쉼표는 문장 부호
    assert found("공제,38만원 남습니다", 380000) == [("38만원", "man")]  # 앞 쉼표도 문장 부호 (Codex 교차 검증)
    assert found("₩450,000", 450) == [] and found("450,000원", 450) == []
    assert found("총 140만원입니다", 400000) == []
    assert found("사백사십만 원", 400000) == [] and found("사백 사십만 원", 400000) == []
    assert found("정가 400,000원이고 40만원을 환불", 400000) == [("400,000원", "comma"), ("40만원", "man")]


def test_amount_rules_touch_only_the_offer_position():
    """Codex 교차 검증: 문자열 전체 치환이 140만원 속 40만원을 바꾸던 것, 같은 값이 두 곳이면 제시액을 못 정하던 것."""
    r = row("x", "총 140만원 중 환불은 40만원입니다.", "low_offer", 400000)
    texts = {v["text"] for v in perturb.variants(r) if v["rule"].startswith("amount")}
    assert texts == {"총 140만원 중 환불은 400,000원입니다.", "총 140만원 중 환불은 사십만 원입니다."}  # 다른 금액이 있어 줄이기 없음
    twice = row("y", "정가 400,000원이고 40만원을 환불해 드립니다.", "low_offer", 400000)
    assert not {v["rule"] for v in perturb.variants(twice)} & {"amount_format", "amount_change"}


def test_invariant_variants_keep_the_answer():
    r = row("b03", "확인해 보니 환불 가능 금액은 412,000원입니다.", "low_offer", 412000)
    out = {v["rule"]: v for v in perturb.variants(r)}
    assert out["nospace"]["text"] == "확인해보니환불가능금액은412,000원입니다."
    for v in out.values():
        if perturb.RULES[v["rule"]][0] == "불변":
            assert (v["reply_type"], v["amount"]) == ("low_offer", 412000)
        assert v["src"] == "b03" and v["note"] == perturb.RULES[v["rule"]][1]
    assert out["banmal"]["text"] == "확인해 보니 환불 가능 금액은 412,000원이야."


def test_banmal_and_abbrev_examples():
    assert perturb.banmal("말씀하신 금액으로 환불 처리해 드리겠습니다. 계좌번호 남겨주세요.") == \
        "말한 금액으로 환불 처리해 줄게. 계좌번호 남겨줘."
    assert perturb.banmal("그걸로 처리해 드릴게요.") == "그걸로 처리해 줄게."
    # A 리뷰(#106): 연락드리다는 하다로, 높임 남은 곳과 저희도 낮춘다
    assert perturb.banmal("복귀하시면 연락드릴게요.") == "복귀하면 연락할게."
    assert perturb.banmal("확인해 보고 연락드리겠습니다.") == "확인해 보고 연락할게."
    assert perturb.banmal("불만 있으시면 소비자원에 신고하세요.") == "불만 있으면 소비자원에 신고해."
    assert perturb.banmal("법대로 하세요. 저희는 더 드릴 말씀 없습니다.") == "법대로 해. 우리는 더 할 말 없어."
    assert perturb.banmal("현금으로는 못 돌려드리고 바꿔 드릴 수 있습니다.") == "현금으로는 못 돌려주고 바꿔 줄 수 있어."
    assert perturb.banmal("위약금은 저희 규정상 20%입니다.") == "위약금은 우리 규정상 20%야."
    assert perturb.abbrev("네 회원님, 말씀하신 대로") == "ㅇㅇ 회원님, 말씀하신 대로"
    assert perturb.abbrev("환불이 안 됩니다.") == "환불이 ㄴㄴ."
    assert perturb.abbrev("그런 건 전화로 얘기하시죠.") is None


def test_call_memos_get_no_speech_style_variants():
    memo = row("b09", "세 번 걸었는데 계속 통화 중이고 안 받음", "no_answer")
    rules = {v["rule"] for v in perturb.variants(memo)}
    assert "nospace" in rules
    assert not rules & {"greet", "excuse", "banmal", "abbrev", "laugh", "emoji"}


def test_amount_change_moves_only_the_offer():
    one = {v["id"]: v for v in perturb.variants(row("c06", "센터 방문해 주시면 40만원 환불해 드립니다.", "low_offer", 400000))}
    ch = one["c06~amount_change"]
    assert ch["text"] == "센터 방문해 주시면 35만원 환불해 드립니다."
    assert (ch["reply_type"], ch["amount"]) == ("low_offer", 350000)
    tight = {v["id"]: v for v in perturb.variants(row("b04", "삼십만원까지는 맞춰 드릴 수 있어요.", "low_offer", 300000))}
    assert tight["b04~amount_change"]["text"] == "이십오만원까지는 맞춰 드릴 수 있어요."  # 원문처럼 붙여 쓴다 (A 리뷰 #106)
    assert perturb.same_spacing("사십만 원", "삼십오만 원") == "삼십오만 원"
    assert perturb.same_spacing("28만 5천원", "23만 5천원") == "23만 5천원"
    assert perturb.same_spacing("28만5천 원", "23만 5천원") == "23만5천 원"  # 수 안과 원 앞을 따로 (Codex 교차 검증)
    assert perturb.same_spacing("이십팔만오천 원", "이십삼만 오천 원") == "이십삼만오천 원"
    assert perturb.same_spacing("412,000원", "362,000원") == "362,000원"
    won = {v["id"]: v for v in perturb.variants(row("v04", "₩450,000 환불 가능합니다.", "low_offer", 450000))}
    assert won["v04~amount_change"]["text"] == "₩400,000 환불 가능합니다."
    r = row("c03", "결제하신 60만원에서 20만원 공제하고 40만원 돌려드립니다.", "low_offer", 400000)
    out = {v["id"]: v for v in perturb.variants(r)}
    assert "c03~amount_change" not in out  # 계산식(60-20=40)이 틀어진다 (Codex 교차 검증)
    fmt = {v["text"] for v in out.values() if v["rule"] == "amount_format"}
    assert fmt == {"결제하신 60만원에서 20만원 공제하고 400,000원 돌려드립니다.",
                   "결제하신 60만원에서 20만원 공제하고 사십만 원 돌려드립니다."}


def test_no_amount_rules_without_an_offer_amount():
    zero = perturb.variants(row("c08", "계산해 보니 환불 가능 금액은 0원입니다.", "low_offer", 0))
    assert "amount_change" not in {v["rule"] for v in zero}
    u03 = perturb.variants(row("u03", "총 90만원 결제 중 이용료 38만원, 위약금 9만원 제하고 43만원 입금 예정입니다.",
                               "low_offer", 430000))
    assert "amount_change" not in {v["rule"] for v in u03}  # 줄인 금액 38만원이 이미 문장에 있다
    refuse = perturb.variants(row("b06", "60만원 결제 건은 이미 한 달이 지나서 환불이 안 됩니다.", "refuse"))
    assert not {v["rule"] for v in refuse} & {"amount_format", "amount_change"}


def test_generated_file_is_current_and_valid():
    rows = perturb.generate(perturb.sources())
    assert len(perturb.sources()) == 64
    assert perturb.OUT.read_text(encoding="utf-8") == perturb.dump(rows), "python eval/perturb.py로 다시 만든다"
    assert len({r["id"] for r in rows}) == len(rows)
    assert {r["reply_type"] for r in rows} <= set(get_args(ReplyType))
    assert all(r["text"] != perturb.SRC[r["src"]]["text"] for r in rows)


def test_report_counts_broken_and_changed(monkeypatch):
    answers = {"a": ("refuse", None, False), "a ㅋㅋ": ("refuse", None, False),
               "a 😊": ("unknown", None, False), "b": ("visit", None, False), "b ㅋㅋ": ("visit", None, False),
               "b 😊": ("refuse", None, False)}
    calls = []
    monkeypatch.setattr(agent, "read_reply", lambda t: calls.append(t) or answers[t])
    src = [row("s1", "a", "refuse"), row("s2", "b", "refuse")]
    var = [dict(row(f"{r['id']}~{rule}", r["text"] + suf, "refuse"), src=r["id"], rule=rule, note="")
           for r in src for rule, suf in (("laugh", " ㅋㅋ"), ("emoji", " 😊"))]
    rep = perturb.report(src, var)
    assert rep["laugh"]["broken"] == 0 and rep["laugh"]["changed"] == 0
    assert rep["emoji"]["broken"] == 1 and rep["emoji"]["fixed"] == 1 and rep["emoji"]["changed"] == 2
    assert rep["emoji"]["score"]["risk"] == {"high": 0, "mid": 0, "safe": 1}
    assert len(calls) == len(set(calls)) == 6  # 같은 문장은 한 번만 읽는다


def test_cli_prints_interval_without_touching_the_real_file(monkeypatch, tmp_path, capsys):
    """출력 줄마다 95% 구간이 나온다(A 리뷰 #106 3번). 실제 perturbed_c.jsonl 대신 임시 파일에 쓴다."""
    monkeypatch.setattr(perturb, "OUT", tmp_path / "p.jsonl")
    monkeypatch.setattr(agent, "llm", agent.llm)  # main이 FAKE로 바꾼 것을 테스트 뒤 되돌린다
    perturb.main([])
    lines = [l for l in capsys.readouterr().out.splitlines() if l.startswith(tuple(perturb.RULES))]
    assert len(lines) == len(perturb.RULES) and all("(95% " in l for l in lines)
    assert (tmp_path / "p.jsonl").read_text(encoding="utf-8") == perturb.OUT.read_text(encoding="utf-8")
