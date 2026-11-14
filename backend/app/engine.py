"""사건 단계 전이. 순수 함수이며 저장하지 않는다. 클라이언트가 사건을 보관하고 판단은 여기서 한다."""
from datetime import date, timedelta

from .models import Action, Case, Contract, Event, Record
from .rules import POLICY, calculate


def open_case(contract: Contract, today: date, target: int | None = None, floor: int | None = None) -> Case:
    refund = calculate(contract, today)
    return Case(
        contract=contract,
        refund=refund,
        target=target if target is not None else refund.refund,
        floor=floor if floor is not None else refund.refund,
    )


def apply(case: Case, event: Event, today: date) -> Case:
    c = case.model_copy(deep=True)

    def log(text: str = "") -> None:
        c.timeline.append(Record(on=today, type=event.type, text=text))

    if event.type == "notice_sent":
        if c.notified_on is None:  # 첫 통지일이 도달일이고, 환불액은 이 날짜로 고정된다
            c.notified_on = today
            c.refund = calculate(c.contract, today)
        c.attempts += 1
        c.stage = "waiting"
        c.deadline_on = today + timedelta(days=POLICY["wait_days"])
        log("전화로 말함" if event.channel == "call" else "문자로 보냄")

    elif event.type == "reply_received":
        c.last_reply, c.offered = event.reply_type, event.amount
        log(event.text or event.reply_type or "")
        if event.reply_type in ("no_answer", "callback"):
            c.stage = "waiting"
        elif event.reply_type == "accept":
            _agree(c, event.amount or c.refund.refund, today)
        else:
            c.stage = "negotiating"

    elif event.type == "agreement_recorded":
        _agree(c, event.amount or c.refund.refund, today)
        log(f"{c.agreed_amount:,}원에 합의")

    elif event.type == "deposit_confirmed":
        c.stage = "closed"
        log("입금 확인")

    elif event.type == "escalation_sent":
        c.stage = "escalated"
        c.deadline_on = today + timedelta(days=POLICY["wait_days"])
        log("내용증명 발송")

    elif event.type == "handoff_done":
        c.stage = "handed_off"
        log("1372 소비자상담센터에 접수")

    elif event.type == "time_passed":
        log()

    return c


def _agree(c: Case, amount: int, today: date) -> None:
    c.stage = "agreed"
    c.agreed_amount = amount
    c.deposit_due_on = today + timedelta(days=POLICY["deposit_days"])


def next_action(case: Case, today: date) -> Action:
    c = case
    if c.stage == "ready":
        return Action(type="send_notice", reason="해지 의사를 알려야 환불액이 더 줄지 않는다")
    if c.stage == "waiting":
        if today <= c.deadline_on:
            return Action(type="wait", reason=f"{c.deadline_on:%m월 %d일}까지 답을 기다린다")
        if c.attempts <= POLICY["max_follow_ups"]:
            return Action(type="follow_up", reason="답변 기한이 지났다")
        return Action(type="certified_mail", reason="재요청에도 답이 없다")
    if c.stage == "negotiating":
        if c.last_reply == "low_offer" and c.offered is not None:
            if c.offered >= c.target:
                return Action(type="confirm_agreement", reason="제시액이 목표 금액 이상이다")
            if c.offered < c.floor:
                return Action(type="counter", reason="제시액이 최저 수용선보다 적다", warn=True)
            return Action(type="counter", reason="수용선은 넘지만 목표 금액보다 적다. 받아들일지 정한다")
        return Action(type="counter", reason="근거를 들어 다시 요청한다")
    if c.stage == "escalated":
        if today <= c.deadline_on:
            return Action(type="wait", reason=f"{c.deadline_on:%m월 %d일}까지 답을 기다린다")
        return Action(type="go_1372", reason="내용증명에도 답이 없다")
    if c.stage == "agreed":
        if today <= c.deposit_due_on:
            return Action(type="wait", reason=f"{c.deposit_due_on:%m월 %d일}까지 입금을 기다린다")
        return Action(type="remind_deposit", reason="입금 기한이 지났다")
    if c.stage == "handed_off":
        return Action(type="go_1372", reason="1372 상담 결과를 기다린다")
    return Action(type="close", reason="환불금을 받았다")
