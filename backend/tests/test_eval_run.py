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
    s = run.score_photos(rows, tmp_path)
    assert s["n"] == 2 and s["all_ok"] == 2
    assert run.norm("special_terms", "해당 없음") == "" and run.norm("gym_name", "가상짐 한빛점") == "가상짐한빛점"
