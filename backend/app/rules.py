"""환불 계산과 근거 표. 금액은 여기서만 만든다. LLM은 숫자를 만들지 않는다."""
import json
from datetime import date
from pathlib import Path

from .models import Contract, Refund

DATA = Path(__file__).resolve().parents[2] / "data"
RULES: dict[str, dict] = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))
POLICY: dict[str, int] = json.loads((DATA / "policy.json").read_text(encoding="utf-8"))


def calculate(contract: Contract, notified_on: date) -> Refund:
    """기간제 회원권의 중도해지 환불액.

    임시 계산식이다(docs/환불_규칙.md). 일할 계산 방식과 개시 전 해지는 고시 별표 확인 후 확정한다.
    """
    total_days = (contract.end_date - contract.start_date).days + 1
    if total_days <= 0:
        raise ValueError("종료일이 개시일보다 빠르다")
    # 도달일까지 지난 날은 가지 않았어도 이용한 것으로 본다(고시 제5조 제1항).
    used_days = min(max((notified_on - contract.start_date).days + 1, 0), total_days)
    used_amount = contract.total_paid * used_days // total_days
    penalty = contract.total_paid * POLICY["penalty_percent"] // 100
    return Refund(
        total_days=total_days,
        used_days=used_days,
        used_amount=used_amount,
        penalty=penalty,
        refund=max(contract.total_paid - used_amount - penalty, 0),
        per_day_loss=contract.total_paid // total_days,
        refs=["G5", "G10", "R31", "R32"],
    )
