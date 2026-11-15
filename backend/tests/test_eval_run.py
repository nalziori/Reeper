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
