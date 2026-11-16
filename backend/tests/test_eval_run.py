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
