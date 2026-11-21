"""C 트랙 계산 규칙 테스트. 기준: docs/환불_규칙.md 결정표.

공통 예: 60만 원, 위약금 10% = 6만 원.
"""
from datetime import date

import pytest

from app.models import Contract
from app.rules import calculate


def contract(**kw):
    base = dict(total_paid=600_000, start_date=date(2026, 1, 1), end_date=date(2026, 3, 31))  # 90일
    return Contract(**(base | kw))


def test_day_unit_is_default():
    r = calculate(contract(), date(2026, 1, 10))  # 10일째, 당일 포함
    assert (r.used_amount, r.penalty, r.refund) == (66_666, 60_000, 473_334)


def test_month_unit_prorates_by_days():
    # 월 단위 계약도 개월이 아니라 날짜로 일할한다. 결과가 일 단위와 같다.
    c = contract(unit="month", total_count=3)
    assert calculate(c, date(2026, 1, 31)).refund == 333_334  # 90일 중 31일
    assert calculate(c, date(2026, 2, 1)).refund == 326_667  # 2월에 들어서도 하루치만 더 빠진다
    assert calculate(c, date(2026, 2, 1)) == calculate(contract(), date(2026, 2, 1))


def test_month_unit_start_day_is_one_day():
    # 개시 당일 해지는 한 달치가 아니라 하루치만 이용분이다(366일 중 1일).
    c = contract(total_paid=240_000, start_date=date(2026, 11, 20), end_date=date(2027, 11, 20), unit="month")
    r = calculate(c, date(2026, 11, 20))
    assert (r.used_days, r.total_days, r.used_amount, r.penalty, r.refund) == (1, 366, 655, 24_000, 215_345)


def test_count_unit_uses_used_count():
    c = contract(unit="count", total_count=20, used_count=5)
    r = calculate(c, date(2026, 1, 10))
    assert (r.used_amount, r.refund) == (150_000, 390_000)


def test_count_unit_needs_counts():
    with pytest.raises(ValueError):
        calculate(contract(unit="count"), date(2026, 1, 10))


def test_addon_deducted_only_when_value_written():
    assert calculate(contract(addon_value=30_000), date(2026, 1, 10)).refund == 443_334
    assert calculate(contract(), date(2026, 1, 10)).refund == 473_334


def test_security_deposit_returned_in_full():
    assert calculate(contract(security_deposit=50_000), date(2026, 1, 10)).refund == 523_334
    # 기간을 다 써도 보증금은 돌려받는다
    assert calculate(contract(security_deposit=50_000), date(2026, 3, 31)).refund == 50_000


def test_per_day_loss_is_tomorrow_difference():
    assert calculate(contract(), date(2026, 1, 10)).per_day_loss == 6_667  # 473,334 − 466,667
    assert calculate(contract(unit="month", total_count=3), date(2026, 1, 10)).per_day_loss == 6_667
    assert calculate(contract(unit="month", total_count=3), date(2026, 1, 31)).per_day_loss == 6_667
    assert calculate(contract(unit="count", total_count=20, used_count=5), date(2026, 1, 10)).per_day_loss == 0


def test_month_from_jan_31_start():
    # 월말 시작이어도 날짜로 센다. 1/31~2/28은 29일
    c = contract(start_date=date(2026, 1, 31), end_date=date(2026, 4, 30), unit="month", total_count=3)
    assert calculate(c, date(2026, 2, 28)).used_days == 29
    assert calculate(c, date(2026, 3, 1)).used_days == 30


def test_unit_label():
    assert calculate(contract(unit="count", total_count=20, used_count=5), date(2026, 1, 10)).unit_label == "회"
    assert calculate(contract(unit="month", total_count=3), date(2026, 1, 10)).unit_label == "일"


def test_cancel_reason_defaults_to_consumer_and_old_cases_still_load():
    # 저장된 옛 사건에는 이 값이 없다. 없으면 소비자 사정이고 계산은 그대로다
    c = Contract(total_paid=600_000, start_date=date(2026, 1, 1), end_date=date(2026, 6, 30))
    assert (c.cancel_reason, c.fault_kind) == ("consumer", None)
    b = c.model_copy(update={"cancel_reason": "business", "fault_kind": "closure"})
    assert Contract.model_validate(b.model_dump(mode="json")) == b
    # 다퉈질 때의 금액은 업체 잘못일 때만 채운다. 같은 날짜의 소비자 사정 환불액이다
    assert calculate(c, date(2026, 2, 1)).disputed_refund is None
    assert calculate(b, date(2026, 2, 1)).disputed_refund == calculate(c, date(2026, 2, 1)).refund


# 업체 잘못: 위약금은 사업자의 귀책사유 없이 해지된 경우에만 청구할 수 있다(고시 제4조 제1항, G4).
# 정답은 손으로 셌다. docs/환불_규칙.md "업체 잘못일 때의 계산 근거"
def test_business_fault_has_no_penalty_and_keeps_the_disputed_amount():
    r = calculate(contract(cancel_reason="business", fault_kind="trainer_change"), date(2026, 1, 10))
    assert (r.used_amount, r.penalty, r.refund) == (66_666, 0, 533_334)
    assert r.disputed_refund == 473_334  # 업체가 다투면 소비자 사정 계산(위약금 6만 원 공제)
    assert r.refs == ["G5", "G4", "R31", "R32"]
    assert r.per_day_loss == 533_334 - 526_667  # 하루 늦으면 이용분만 늘어난다


def test_consumer_reason_is_unchanged_and_has_no_disputed_amount():
    r = calculate(contract(), date(2026, 1, 10))
    assert (r.penalty, r.refund, r.disputed_refund) == (60_000, 473_334, None)
    assert r.refs == ["G5", "G10", "R31", "R32"]
    # fault_kind만 있고 해지 이유가 소비자 사정이면 계산은 그대로다
    assert calculate(contract(fault_kind="closure"), date(2026, 1, 10)) == r


def test_business_fault_keeps_addon_and_deposit_rules():
    r = calculate(contract(cancel_reason="business", addon_value=50_000, security_deposit=30_000), date(2026, 1, 10))
    assert (r.penalty, r.refund, r.disputed_refund) == (0, 513_334, 453_334)


def test_business_fault_by_count():
    c = contract(cancel_reason="business", unit="count", total_paid=500_000, total_count=10, used_count=3)
    r = calculate(c, date(2026, 1, 10))
    assert (r.used_amount, r.penalty, r.refund, r.disputed_refund) == (150_000, 0, 350_000, 300_000)


def test_business_fault_disputed_amount_never_exceeds_refund():
    # 다 쓴 계약은 두 금액이 모두 보증금뿐이라 같다.
    r = calculate(contract(cancel_reason="business", security_deposit=10_000), date(2026, 3, 31))
    assert (r.refund, r.disputed_refund) == (10_000, 10_000)
    for d in (date(2026, 1, 1), date(2026, 2, 15), date(2026, 3, 30)):
        r = calculate(contract(cancel_reason="business"), d)
        assert 0 <= r.disputed_refund <= r.refund
