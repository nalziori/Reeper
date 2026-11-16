import importlib.util
import json
from pathlib import Path

from typing import get_args

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


def test_score_runs_on_the_fake_llm(monkeypatch):
    monkeypatch.setattr(agent, "llm", agent.FAKE)
    s = run.score(run.load())
    assert s["n"] > 0 and s["fallbacks"] == 0 and 0 <= s["type_acc"] <= 1
    assert len(s["misses"]) >= s["n"] - round(s["type_acc"] * s["n"])


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
