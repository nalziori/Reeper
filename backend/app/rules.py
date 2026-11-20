"""환불 계산과 근거 표. 금액은 여기서만 만든다. LLM은 숫자를 만들지 않는다."""
import json
from datetime import date, timedelta
from pathlib import Path

from .models import Contract, Refund

DATA = Path(__file__).resolve().parents[2] / "data"
RULES: dict[str, dict] = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))
POLICY: dict[str, int] = json.loads((DATA / "policy.json").read_text(encoding="utf-8"))


# 월 단위 계약도 날짜로 일할하므로 단위 이름은 "일"이다(docs/환불_규칙.md 결정표 1번).
UNIT_LABEL = {"day": "일", "month": "일", "count": "회"}


def calculate(contract: Contract, notified_on: date) -> Refund:
    """중도해지 환불액. 기준은 docs/환불_규칙.md 결정표.

    환불액 = max(총계약대금 - 이용분 - 부가상품 가액 - 위약금, 0) + 보증금
    per_day_loss는 하루 늦게 도달했을 때 줄어드는 실제 금액이다.
    """
    r = _calculate(contract, notified_on)
    r.per_day_loss = r.refund - _calculate(contract, notified_on + timedelta(days=1)).refund
    return r


def _calculate(contract: Contract, notified_on: date) -> Refund:
    if contract.unit in ("day", "month"):
        # 월 단위 계약도 개월이 아니라 날짜로 일할한다(공정위 의결 제2016-058호, 체육시설업 표준약관).
        total = (contract.end_date - contract.start_date).days + 1
        if total <= 0:
            raise ValueError("종료일이 개시일보다 빠르다")
        # 도달일까지 지난 날은 가지 않았어도 이용한 것으로 본다(고시 제5조 제1항).
        used = (notified_on - contract.start_date).days + 1
    elif contract.total_count is None or contract.used_count is None:
        raise ValueError("회 단위는 총 횟수와 이용 횟수가 필요하다")
    else:
        total, used = contract.total_count, contract.used_count
    used = min(max(used, 0), total)
    used_amount = contract.total_paid * used // total
    penalty = contract.total_paid * POLICY["penalty_percent"] // 100
    left = max(contract.total_paid - used_amount - contract.addon_value - penalty, 0)
    return Refund(
        total_days=total,
        used_days=used,
        used_amount=used_amount,
        penalty=penalty,
        refund=left + contract.security_deposit,
        per_day_loss=0,
        unit_label=UNIT_LABEL[contract.unit],
        addon=contract.addon_value,
        security_deposit=contract.security_deposit,
        refs=["G5", "G10", "R31", "R32"],
    )
