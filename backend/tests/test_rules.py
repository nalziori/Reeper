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
    # 다퉈질 때의 금액은 계산 분기가 채우기 전까지 비어 있다
    assert calculate(c, date(2026, 2, 1)).disputed_refund is None and calculate(b, date(2026, 2, 1)).disputed_refund is None
