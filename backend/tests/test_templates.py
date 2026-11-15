"""문안의 금액이 받는 사람이 검산해도 맞는지 본다."""
from datetime import date

import pytest

from app.agent import render, validate
from app.models import Case, Contract
from app.rules import calculate

KINDS = ["notice_sms", "after_call_sms", "call_card", "certified_mail", "counter_list_price", "counter_low_offer", "counter_penalty", "go_1372"]


def case(**kw):
    c = Contract(total_paid=600_000, start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), **kw)
    r = calculate(c, date(2026, 1, 10))
    return Case(contract=c, refund=r, target=r.refund, floor=r.refund, offered=300_000)


@pytest.mark.parametrize("kind", KINDS)
def test_addon_and_deposit_shown(kind):
    k = case(addon_value=30_000, security_deposit=50_000)
    text = render(kind, k)
    assert validate(text, k)
    assert "부가상품 30,000원" in text and "보증금 50,000원" in text
    assert f"{k.refund.refund:,}원" in text  # 600,000 − 66,666 − 60,000 − 30,000 + 50,000 = 493,334


@pytest.mark.parametrize("kind", KINDS)
def test_plain_contract_has_no_extra_lines(kind):
    text = render(kind, case())
    assert "부가상품" not in text and "보증금" not in text
