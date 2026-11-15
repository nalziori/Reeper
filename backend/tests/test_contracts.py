"""가상 계약서 정답 세트(eval/contracts.jsonl)와 rules.calculate가 일치하는지 본다.

정답은 rules.py를 부르지 않고 따로 계산해 적었다. 두 계산이 어긋나면 어느 쪽이 틀렸는지 확인한다.
여기서는 모든 건을 회귀 확인으로 본다. basis가 unverified_month인 건은 해석이 확인되지 않은 값이라
정확도 평가(eval/run.py)에서는 뺀다.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app.models import Contract
from app.rules import calculate

ROWS = [json.loads(l) for l in (Path(__file__).resolve().parents[2] / "eval" / "contracts.jsonl").read_text(encoding="utf-8").splitlines()]


def test_set_size():
    assert 20 <= len(ROWS) <= 30
    assert {r["basis"] for r in ROWS} <= {"kca_case", "decision_table", "unverified_month"}
    assert len({r["id"] for r in ROWS}) == len(ROWS)


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_refund_regression(row):
    r = calculate(Contract(**row["contract"], **row["usage"]), date.fromisoformat(row["notified_on"]))
    got = {k: getattr(r, k) for k in row["expected"]}
    assert got == row["expected"]


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_text_carries_answer_fields(row):
    c, text = row["contract"], row["text"]
    assert c["gym_name"] in text and f"{c['total_paid']:,}원" in text
    if c.get("addon_value"):
        assert f"{c['addon_value']:,}원" in text
