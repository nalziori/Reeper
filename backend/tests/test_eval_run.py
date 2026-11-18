import importlib.util
import json
from pathlib import Path

from typing import get_args

import pytest

from app import agent
from app.models import ReplyType

RUN = Path(__file__).resolve().parents[2] / "eval" / "run.py"
spec = importlib.util.spec_from_file_location("eval_run", RUN)
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def test_labels_use_known_reply_types():
    rows = run.load()
    assert len({r["id"] for r in rows}) == len(rows)
    assert {r["reply_type"] for r in rows} <= set(get_args(ReplyType))
    assert all((r["amount"] is not None) == (r["reply_type"] == "low_offer") for r in rows)


def test_hard_reply_labels():
    rows = run.load([run.ROOT / "hard_replies_c.jsonl"])
    types = set(get_args(ReplyType))
    assert [r["id"] for r in rows] == [f"h{i:03d}" for i in range(1, len(rows) + 1)] and len(rows) == 100
    assert {r["reply_type"] for r in rows} <= types
    assert all((r["amount"] is not None) == (r["reply_type"] == "low_offer") for r in rows)
    for r in rows:  # 허용 유형은 정답과 다르고, 정답을 하나로 정하기 어려운 이유를 note에 적는다
        assert set(r.get("also", [])) <= types - {r["reply_type"]} and r["note"], r["id"]
        # 제시액은 정답이 low_offer일 때만 채점하므로, low_offer와 다른 유형을 서로 허용하면 금액이 채점에서 빠진다
        assert "low_offer" not in r.get("also", []) and not (r["reply_type"] == "low_offer" and r.get("also")), r["id"]


def test_also_counts_as_correct(monkeypatch):
    monkeypatch.setattr(agent, "read_reply", lambda text: ("accept", None, False))
    rows = [{"id": "x1", "text": "-", "reply_type": "unknown", "amount": None, "also": ["accept"]},
            {"id": "x2", "text": "-", "reply_type": "unknown", "amount": None}]
    s = run.score(rows)
    assert s["type_acc"] == 0.5 and [m["id"] for m in s["misses"]] == ["x2"]


def test_score_runs_on_the_fake_llm(monkeypatch):
    monkeypatch.setattr(agent, "llm", agent.FAKE)
    s = run.score(run.load())
    assert s["n"] > 0 and s["fallbacks"] == 0 and 0 <= s["type_acc"] <= 1
    assert len(s["misses"]) >= s["n"] - round(s["type_acc"] * s["n"])


def test_photo_scoring_normalizes_no_terms(monkeypatch, tmp_path):
    from app.models import Extracted
    rows = [r for r in run.load([RUN.parent / "contracts.jsonl"]) if r.get("photo_layout")]
    assert len(rows) == 12
    for r in rows[:2]:
        (tmp_path / f"{r['id']}.jpg").write_bytes(b"x")

    def fake_extract(url):
        r = rows[0] if not fake_extract.n else rows[1]
        fake_extract.n += 1
        c = {**r["contract"], "special_terms": r["contract"]["special_terms"] or "별도의 특약 사항은 없다"}
        return {f: Extracted(value=c[f], confidence=1.0, quote="", check=False) for f in agent.FIELDS}, False
    fake_extract.n = 0
    monkeypatch.setattr(agent, "extract_contract", fake_extract)
    s = run.score_photos(rows[:2], tmp_path)
    assert s["n"] == 2 and s["all_ok"] == 2
    assert run.norm("special_terms", "해당 없음") == "" and run.norm("gym_name", "가상짐 한빛점") == "가상짐한빛점"


def test_unread_special_terms_are_not_counted_as_no_terms(monkeypatch, tmp_path):
    from app.models import Extracted
    rows = [r for r in run.load([RUN.parent / "contracts.jsonl"]) if r.get("photo_layout")]
    for r in rows:
        (tmp_path / f"{r['id']}.jpg").write_bytes(b"x")
    it = iter(rows)

    def fake_extract(url):
        c = {**next(it)["contract"], "special_terms": None}
        return {f: Extracted(value=c[f], confidence=0.0 if c[f] is None else 1.0, quote="",
                             check=c[f] is None) for f in agent.FIELDS}, False
    monkeypatch.setattr(agent, "extract_contract", fake_extract)
    s = run.score_photos(rows, tmp_path)
    assert s["fields"]["special_terms"] == 0 and s["all_ok"] == 0


def test_photo_none_requires_special_terms_quote(monkeypatch, tmp_path):
    from app.models import Extracted
    row = next(r for r in run.load([RUN.parent / "contracts.jsonl"])
               if r.get("photo_layout") and not r["contract"]["special_terms"])
    (tmp_path / f"{row['id']}.jpg").write_bytes(b"x")
    for quote in ["없음", "특약사항 없음", "", "   "]:
        extracted = {f: Extracted(value=None, confidence=1.0, quote=quote, check=False)
                     for f in agent.FIELDS}
        monkeypatch.setattr(agent, "extract_contract", lambda url: (extracted, False))
        result = run.score_photos([row], tmp_path)
        assert result["fields"]["special_terms"] == int(bool(quote.strip()))
        assert all(n == 0 for f, n in result["fields"].items() if f != "special_terms")
        assert result["all_ok"] == 0


def test_photo_quote_must_say_no_terms(monkeypatch, tmp_path):
    from app.models import Extracted
    row = next(r for r in run.load([RUN.parent / "contracts.jsonl"])
               if r.get("photo_layout") and not r["contract"]["special_terms"])
    (tmp_path / f"{row['id']}.jpg").write_bytes(b"x")
    for quote, want in [("특약사항", 0), ("비고(특약)", 0), ("특약사항 해당 없음", 1),
                        ("제5조(특약) 별도의 특약 사항은 없다.", 1), ("비고(특약) 없음", 1),
                        ("특약사항: 읽을 수 없음", 0), ("특약사항: 확인할 수 없음", 0),
                        ("평가용 가상 계약서 · 실제 업체·인물과 관계없음 · k01", 0)]:
        extracted = {f: Extracted(value=None, confidence=0.0, quote=quote, check=True) for f in agent.FIELDS}
        monkeypatch.setattr(agent, "extract_contract", lambda url: (extracted, False))
        assert run.score_photos([row], tmp_path)["fields"]["special_terms"] == want, quote


def test_missing_photo_stops_before_any_call(monkeypatch, tmp_path):
    rows = [r for r in run.load([RUN.parent / "contracts.jsonl"]) if r.get("photo_layout")]
    (tmp_path / f"{rows[0]['id']}.jpg").write_bytes(b"x")
    calls = []
    monkeypatch.setattr(agent, "extract_contract", lambda url: calls.append(url))
    with pytest.raises(FileNotFoundError):
        run.score_photos(rows, tmp_path)
    assert calls == []


def test_no_terms_allows_trailing_period_and_label_in_value():
    assert run._quote_says_no_terms("특약사항: 없음.")
    assert run.norm("special_terms", "없음.") == ""
    assert run.norm("special_terms", "특약: 없음") == ""
    assert run.norm("special_terms", "특약: 환불 불가") != ""


def test_plan_score_runs_on_the_fake_llm(monkeypatch):
    monkeypatch.setattr(agent, "llm", agent.FAKE)
    rows = run.load([RUN.parent / "situations_b.jsonl"])
    s = run.score_plans(rows)
    assert s["n"] == len(s["situations"]) == 10
    assert s["must_n"] == 11
    assert s["must_hit"] == 0 and s["must_recall"] == 0
    assert s["forbid_hits"] == s["out_of_table"] == 0
    assert s["empty"] == 10
    assert all(r["rule_ids"] == [] for r in s["situations"])
    assert next(r for r in s["situations"] if r["id"] == "s08")["must_hit"] is None


def test_plan_labels_use_known_rules():
    rows = run.load([RUN.parent / "situations_b.jsonl"])
    rules = json.loads((RUN.parents[1] / "data" / "rules.json").read_text(encoding="utf-8"))
    for r in rows:
        assert set(r["must_grounds"]) <= rules.keys(), r["id"]
        assert set(r["forbid_grounds"]) <= rules.keys(), r["id"]


def test_plan_offline_lists_situations_without_scoring(monkeypatch, capsys):
    monkeypatch.setattr(run.sys.stdout, "reconfigure", lambda **kwargs: None, raising=False)
    monkeypatch.setattr(agent, "llm", agent.FAKE)
    def unexpected_score(rows):
        raise AssertionError("offline must not score")
    monkeypatch.setattr(run, "score_plans", unexpected_score)
    run.main(["--plans"])
    output = capsys.readouterr().out
    assert "FakeLLM" in output and "N/A" in output and "0%" not in output
    assert all(r["id"] in output for r in run.load([RUN.parent / "situations_b.jsonl"]))


def test_business_content_check(monkeypatch):
    rows = run.load([RUN.parent / "situations_b.jsonl"])
    row = next(r for r in rows if r["cause"] == "business")
    strategy = {"grounds": [{"rule_id": rid} for rid in row["must_grounds"]],
                "summary": "위약금은 그대로입니다", "cautions": ["1372 상담"], "questions": []}
    monkeypatch.setattr(agent, "plan", lambda *args: strategy)
    for phrase in ["위약금은 그대로입니다", "위약금이 그대로입니다", "위약금은 공제됩니다"]:
        strategy["summary"] = phrase
        result = run.score_plans([row])
        assert result["must_recall"] == 1
        assert result["situations"][0]["content_ok"] is False
        assert result["business_content_failures"] == 1
    strategy["summary"] = "업체 귀책 확인 필요"
    assert run.score_plans([row])["situations"][0]["content_ok"] is True
    strategy["cautions"] = []
    assert run.score_plans([row])["situations"][0]["content_ok"] is False
    strategy["questions"] = ["계약 때 약속했나요? "]
    assert run.score_plans([{**row, "cause": "업체 귀책"}])["situations"][0]["content_ok"] is True
    strategy["cautions"] = ["위약금은 그대로입니다"]
    assert run.score_plans([row])["situations"][0]["content_ok"] is False
    assert run.score_plans([{**row, "cause": "consumer"}])["situations"][0]["content_ok"] is None


def test_business_check_covers_every_advice_field_and_relevant_questions(monkeypatch):
    row = next(r for r in run.load([RUN.parent / "situations_b.jsonl"]) if r["cause"] == "business")
    base = {"grounds": [{"rule_id": rid, "why": "근거"} for rid in row["must_grounds"]],
            "summary": "업체 사정인지 확인하세요", "cautions": [], "contract_points": [], "objections": [],
            "questions": ["계약할 때 그 수업을 약속받았나요?"]}

    def ok(**change):
        monkeypatch.setattr(agent, "plan", lambda *args: {**base, **change})
        return run.score_plans([row])["situations"][0]["content_ok"]

    assert ok() is True
    assert ok(questions=["운동은 얼마나 하셨나요?"]) is False  # 업체 사정과 상관없는 질문
    assert ok(grounds=[{"rule_id": "R31", "why": "위약금은 그대로입니다"}]) is False
    assert ok(contract_points=[{"quote": "특약", "how_to_handle": "위약금이 그대로 공제됩니다"}]) is False
    assert ok(objections=[{"objection": "위약금은 그대로입니다", "response": "업체 사정이면 다를 수 있다"}]) is True
    assert ok(objections=[{"objection": "환불 불가", "response": "위약금은 공제됩니다"}]) is False


def test_penalty_check_reads_sentences_and_fault_questions():
    assert run._penalty_stays("트레이너가 퇴사했어도 위약금도 그대로 공제됩니다.")
    assert run._penalty_stays("위약금은 그대로입니다")
    assert not run._penalty_stays("위약금은 그대로 공제된다고 단정할 수 없습니다. 업체 귀책 여부부터 확인해 주세요.")
    assert not run._penalty_stays("업체 사정이라면 위약금이 빠지지 않을 수 있어요.")
    assert not run.FAULT_QUESTION.search("센터에 몇 번 방문하셨나요?")
    assert not run.FAULT_QUESTION.search("이전에 환불을 요청하셨나요?")
    assert run.FAULT_QUESTION.search("담당 트레이너가 퇴사한 뒤 업체가 대체 강사를 안내했나요?")
    assert run.FAULT_QUESTION.search("계약할 때 그 수업을 약속받았나요?")


def test_penalty_check_hedge_must_be_a_phrase():
    # A 리뷰 반례: 단어 하나(않·면제·확인)로 유보 판정하면 확실한 단정을 놓친다
    assert run._penalty_stays("위약금은 면제되지 않고 그대로 공제됩니다.")
    assert run._penalty_stays("위약금은 그대로 공제되니 영수증을 확인해 두세요.")
    assert run._penalty_stays("위약금이 공제됩니다.업체 사정이면 다를 수 있어요.")
    assert run._penalty_stays("위약금은 당연히 내야 합니다.")


def test_fault_question_needs_class_or_center_context():
    assert not run.FAULT_QUESTION.search("결제 수단을 변경하셨나요?")
    assert not run.FAULT_QUESTION.search("다른 지점으로 옮기실 계획인가요?")
    assert run.FAULT_QUESTION.search("수업 시간이 변경된 걸 언제 알게 되셨나요?")
    assert run.FAULT_QUESTION.search("센터가 다른 곳으로 이전했나요?")


def test_penalty_check_reads_negation_after_the_claim():
    # council 반례: 맞는 조언은 단정이 아니다
    assert not run._penalty_stays("위약금은 그대로 공제되지 않습니다.")
    assert not run._penalty_stays("위약금을 내야 하는 건 아닙니다.")
    assert not run._penalty_stays("위약금은 그대로 낼 필요가 없어요.")
    # 부정이 단정보다 앞에 있으면 여전히 단정이다
    assert run._penalty_stays("위약금은 면제되지 않고 그대로 공제됩니다.")
    assert run._penalty_stays("위약금은 업체 사정과 무관하게 그대로 공제됩니다.")
    assert run._penalty_stays("위약금은 그대로 공제되며 환불은 없습니다.")


def test_fault_question_reads_business_side_change():
    assert run._fault_question("담당 강사가 그만뒀나요?")
    assert run._fault_question("수업 시간을 업체가 바꿨나요?")
    assert not run._fault_question("시간 변경을 요청하신 적이 있나요?")
    assert not run._fault_question("헬스장을 옮기셨나요?")


def test_plan_score_sums_dropped(monkeypatch):
    rows = run.load([RUN.parent / "situations_b.jsonl"])[:2]
    monkeypatch.setattr(agent, "plan", lambda *args: {"summary": "요약", "grounds": [], "contract_points": [],
                                                      "objections": [], "cautions": [], "questions": [],
                                                      "dropped": 3, "fallback": False})
    s = run.score_plans(rows)
    assert [r["dropped"] for r in s["situations"]] == [3, 3] and s["dropped"] == 6


def test_photos_and_plans_cannot_run_together(monkeypatch):
    calls = []
    monkeypatch.setattr(run, "score_photos", lambda *a: calls.append("photos"))
    monkeypatch.setattr(run, "score_plans", lambda *a: calls.append("plans"))
    with pytest.raises(SystemExit, match="따로"):
        run.main(["--photos", "--plans", "--live"])
    assert calls == []


def test_risk_levels_follow_the_plan():
    """C1: 수용 아닌 accept·틀린 금액·제시 아닌 금액은 위험, unknown은 안전, 나머지는 중간."""
    offer = {"reply_type": "low_offer", "amount": 200000}
    refuse = {"reply_type": "refuse", "amount": None}
    assert run.risk(refuse, "accept", None) == "high"
    assert run.risk(offer, "accept", None) == "high"
    assert run.risk(offer, "low_offer", 300000) == "high"
    assert run.risk(refuse, "low_offer", 200000) == "high"
    assert run.risk(refuse, "unknown", None) == "safe"
    assert run.risk({"reply_type": "accept", "amount": None}, "unknown", None) == "safe"
    assert run.risk(refuse, "list_price", None) == "mid"
    assert run.risk(offer, "visit", None) == "mid"  # 금액을 못 읽음: 사용자가 넣는다
    assert run.risk({"reply_type": "callback", "amount": None, "also": ["accept"]}, "accept", None) != "high"


def test_score_reports_risk_and_interval(monkeypatch):
    answers = {"a": ("accept", None, False), "b": ("unknown", None, False), "c": ("refuse", None, False)}
    monkeypatch.setattr(agent, "read_reply", lambda text: answers[text])
    rows = [{"id": "x1", "text": "a", "reply_type": "refuse", "amount": None},
            {"id": "x2", "text": "b", "reply_type": "visit", "amount": None},
            {"id": "x3", "text": "c", "reply_type": "refuse", "amount": None}]
    s = run.score(rows)
    assert s["risk"] == {"high": 1, "mid": 0, "safe": 1}
    assert s["safe_share"] == 0.5 and abs(s["high_rate"] - 1 / 3) < 1e-9
    assert s["confusion"] == {"refuse->accept": 1, "visit->unknown": 1}  # 맞은 건은 세지 않는다
    lo, hi = s["type_ci"]
    assert lo < 1 / 3 < hi
    assert run.wilson(0, 0) == (0.0, 0.0)
    lo, hi = run.wilson(98, 100)
    assert 0.92 < lo < 0.94 and 0.99 < hi < 1.0  # #97 계획의 "약 93~99.5%"


def test_amount_on_a_non_offer_and_also_and_perfect(monkeypatch):
    """A 리뷰(#102): 유형이 맞아도 제시가 아닌 답에 금액이 붙으면 위험 오답, also로 맞은 건은 오답·혼동에 없음, 만점이면 safe_share 없음."""
    answers = {"r": ("refuse", 200000, False), "m": ("callback", None, False)}
    monkeypatch.setattr(agent, "read_reply", lambda text: answers[text])
    s = run.score([{"id": "x1", "text": "r", "reply_type": "refuse", "amount": None},
                   {"id": "x2", "text": "m", "reply_type": "list_price", "amount": None, "also": ["callback"]}])
    assert [m["id"] for m in s["misses"]] == ["x1"] and s["misses"][0]["risk"] == "high"
    assert s["confusion"] == {"refuse->refuse": 1}
    perfect = run.score([{"id": "x2", "text": "m", "reply_type": "list_price", "amount": None, "also": ["callback"]}])
    assert perfect["misses"] == [] and perfect["safe_share"] is None and perfect["confusion"] == {}
