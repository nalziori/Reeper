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
