"""C 트랙 조정례 데이터(data/mediation_cases.json) 형식과 산식 확인. 금액은 원문에 적힌 값이고 rules.py가 만들지 않는다."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CASES = json.loads((DATA / "mediation_cases.json").read_text(encoding="utf-8"))
RULES = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))
SOURCES = ("https://www.ccn.go.kr/", "https://www.consumer.go.kr/")


def test_case_fields_and_sources():
    ids = [c["id"] for c in CASES["cases"]]
    assert len(ids) == len(set(ids))
    for c in CASES["cases"]:
        assert c["url"].startswith(SOURCES), c["id"]
        assert c["business_fault"] in {"recognized", "consumer", "not_determined", "not_stated"}, c["id"]
        assert set(c["rule_ids"]) <= set(RULES), c["id"]  # 근거 표에 있는 조문만
        assert set(c["kinds"]) <= set(CASES["kinds"]), c["id"]
        assert c["money_note"], c["id"]


def test_amounts_add_up():
    # 원문 산식: 결제액 − 공제 + 업체가 더한 돈 = 환급, 계약별 환급의 합 = 결정 금액(끝전 버림이 있으면 그만큼)
    for c in CASES["cases"]:
        if not c["contracts"]:  # 원문에 산식이 없는 건
            assert "원문에 산식 없음" in c["usage_method"], c["id"]
            continue
        for k in c["contracts"]:
            got = k["paid"] - sum(k["deductions"].values()) + sum(k.get("additions", {}).values())
            assert got == k["refund"], c["id"]
        total = sum(k["refund"] for k in c["contracts"])
        if c.get("decided_rounding") == "1,000원 미만 버림":
            total = total // 1000 * 1000
        assert total == c["decided_refund"], c["id"]


def test_derived_amounts_are_labeled():
    # C가 계산해 맞춘 공제액은 화면에서도 C 계산이라고 밝힌다(usage_method)
    for c in CASES["cases"]:
        if any(k.get("derived") for k in c["contracts"]):
            assert "C 계산" in c["usage_method"], c["id"]


def test_penalty_matches_fault():
    # 지금 7건의 일관성 검사다: 소비자 사정으로 본 건만 위약금을 뺐다.
    # 일반 규칙이 아니다. 원문에 맞는 예외 사례가 나오면 데이터가 아니라 이 검사를 고친다
    for c in CASES["cases"]:
        assert c["penalty_deducted"] is (c["business_fault"] == "consumer"), c["id"]


def test_kinds_point_to_cases():
    ids = {c["id"] for c in CASES["cases"]}
    for kind in CASES["kinds"].values():
        assert set(kind["cases"]) <= ids
        assert kind.get("note", "x").strip()  # 안내를 두면 빈 글자가 아니어야 한다
    # 이전 사례는 아직 없어 유형 이름과 사례가 다르다. 화면이 이를 먼저 알린다(#145 B 리뷰)
    assert "시설을 옮긴 사례는 아직" in CASES["kinds"]["relocation"]["note"]


# 2026-11-21 원문과 대조한 값. 합계가 맞게 함께 잘못 옮겨도 여기서 걸린다
CHECKED = {
    "ccn-P000012910": (3_275_216, "2022-11-12", "not_stated", False),
    "ccn-P000012923": (350_028, "2022-05-02", "not_determined", False),
    "c24-11731": (552_000, "2007-05-03", "recognized", False),
    "c24-13984": (114_839, "2024-08-02", "recognized", False),
    "c24-13847": (6_325_000, "2023-01-12", "not_determined", False),
    "c24-13849": (128_700, "2023-05-13", "consumer", True),
    "c24-13884": (386_100, "2023-07-14", "not_stated", False),
}


def test_values_checked_against_source():
    got = {c["id"]: (c["decided_refund"], c["terminated_on"], c["business_fault"], c["penalty_deducted"])
           for c in CASES["cases"]}
    assert got == CHECKED


def test_api_serves_cases():
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).get("/api/mediation-cases")
    assert r.status_code == 200 and r.json() == CASES


def test_fault_kinds_match_the_contract_field():
    # 계약의 fault_kind는 조정례 유형과 같은 이름을 쓴다(화면이 같은 선택지로 사례도 보여 주고 사유 구절도 고른다)
    from typing import get_args
    from app.models import FaultKind
    assert set(get_args(FaultKind)) == set(CASES["kinds"]) | {"other"}
