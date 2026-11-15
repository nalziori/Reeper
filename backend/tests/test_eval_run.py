import importlib.util
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
