"""C 트랙 조정례 데이터(data/mediation_cases.json) 형식과 산식 확인. 금액은 원문에 적힌 값이고 rules.py가 만들지 않는다."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CASES = json.loads((DATA / "mediation_cases.json").read_text(encoding="utf-8"))
RULES = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))


def test_case_fields_and_sources():
    ids = [c["id"] for c in CASES["cases"]]
    assert len(ids) == len(set(ids))
    for c in CASES["cases"]:
        assert c["url"].startswith("https://www.ccn.go.kr/")
        assert c["business_fault"] in {"not_stated", "not_determined"}
        assert set(c["rule_ids"]) <= set(RULES), c["id"]  # 근거 표에 있는 조문만
        assert set(c["kinds"]) <= set(CASES["kinds"]), c["id"]


def test_amounts_add_up():
    # 원문 산식: 결제액 − 공제 = 환급, 계약별 환급의 합 = 결정 금액. 위약금 공제는 없다
    for c in CASES["cases"]:
        assert c["penalty_deducted"] is False
        for k in c["contracts"]:
            assert k["paid"] - sum(k["deductions"].values()) == k["refund"], c["id"]
        assert sum(k["refund"] for k in c["contracts"]) == c["decided_refund"], c["id"]


def test_kinds_point_to_cases():
    ids = {c["id"] for c in CASES["cases"]}
    for kind in CASES["kinds"].values():
        assert set(kind["cases"]) <= ids


# 2026-11-21 원문과 대조한 값. 합계가 맞게 함께 잘못 옮겨도 여기서 걸린다
CHECKED = {
    "ccn-P000012910": (3_275_216, "2022-11-12", "not_stated", False),
    "ccn-P000012923": (350_028, "2022-05-02", "not_determined", False),
}


def test_values_checked_against_source():
    got = {c["id"]: (c["decided_refund"], c["terminated_on"], c["business_fault"], c["penalty_deducted"])
           for c in CASES["cases"]}
    assert got == CHECKED
