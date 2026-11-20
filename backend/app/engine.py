"""사건 단계 전이. 순수 함수이며 저장하지 않는다. 클라이언트가 사건을 보관하고 판단은 여기서 한다."""
from datetime import date, timedelta

from .models import Action, Case, Contract, Event, Record, Stage
from .rules import POLICY, calculate


class InvalidTransition(ValueError):
    """현재 사건에서 처리할 수 없는 이벤트."""


def validate_transition(case: Case, event: Event, today: date) -> None:
    stage = case.stage
    if event.amount is not None and event.amount < 0:
        raise InvalidTransition("금액은 0원 이상이어야 합니다.")
    if case.timeline and today < case.timeline[-1].on:
        raise InvalidTransition("마지막 기록보다 이른 날짜에는 처리할 수 없습니다.")

    if (stage in ("waiting", "negotiating", "escalated") and case.deadline_on is None
            or stage == "agreed" and case.deposit_due_on is None):
        raise InvalidTransition("사건에 필요한 기한 기록이 없습니다.")

    if event.type == "notice_sent":
        allowed = stage == "ready" or (stage == "waiting" and next_action(case, today).type == "follow_up")
    elif event.type == "call_attempted":
        allowed = stage == "ready"
    elif event.type == "reply_received":
        if event.reply_type == "accept" and event.amount == 0:
            raise InvalidTransition("수용 금액은 0원보다 커야 합니다.")
        allowed = stage in ("waiting", "negotiating", "escalated")
    elif event.type == "counter_sent":
        allowed = stage == "negotiating" and next_action(case, today).type == "counter"
    elif event.type == "agreement_recorded":
        if event.amount is not None and event.amount <= 0:
            raise InvalidTransition("합의 금액은 0원보다 커야 합니다.")
        allowed = stage == "negotiating" or (stage == "handed_off" and event.amount is not None)
    elif event.type == "deposit_confirmed":
        if event.amount is not None and event.amount <= 0:
            raise InvalidTransition("입금 금액은 0원보다 커야 합니다.")
        allowed = stage == "agreed"
    elif event.type == "escalation_sent":
        allowed = stage in ("waiting", "negotiating") and next_action(case, today).type == "certified_mail"
    elif event.type == "handoff_done":
        allowed = stage in ("waiting", "escalated", "negotiating", "agreed") and next_action(case, today).type == "go_1372"
    else:
        allowed = event.type == "time_passed"

    if not allowed:
        raise InvalidTransition("현재 사건 단계에서는 이 작업을 기록할 수 없습니다.")


def open_case(contract: Contract, today: date, target: int | None = None, floor: int | None = None) -> Case:
    refund = calculate(contract, today)
    target = refund.refund if target is None else target
    floor = refund.refund if floor is None else floor
    if target < 0 or floor < 0:
        raise ValueError("희망 금액과 하한선은 0원 이상이어야 합니다.")
    if floor > target:
        raise ValueError("하한선은 희망 금액보다 클 수 없습니다.")
    return Case(contract=contract, refund=refund, target=target, floor=floor)


def apply(case: Case, event: Event, today: date) -> Case:
    validate_transition(case, event, today)
    if event.type == "time_passed":
        return case
    c = case.model_copy(deep=True)
    stage_before = case.stage

    def log(text: str = "") -> None:
        c.timeline.append(Record(on=today, type=event.type, text=text))

    if event.type == "notice_sent":
        if c.notified_on is None:  # 첫 통지일이 도달일이고, 환불액은 이 날짜로 고정된다
            c.notified_on = today
            before = c.refund.refund
            c.refund = calculate(c.contract, today)
            # 비워 둬서 예상 환불액을 그대로 쓰던 희망 금액·하한선은 다시 계산한 금액을 따른다.
            # 그대로 두면 사건을 연 날보다 늦게 통지했을 때 업체가 법정액을 정확히 줘도 하한선 미만 경고가 떴다.
            # 직접 정한 값은 두되, 하한선이 희망 금액보다 커지면 희망 금액을 하한선까지 올린다(open_case의 불변식)
            if c.target == before:
                c.target = c.refund.refund
            if c.floor == before:
                c.floor = c.refund.refund
            c.target = max(c.target, c.floor)
        c.attempts += 1
        c.stage = "waiting"
        c.deadline_on = today + timedelta(days=POLICY["wait_days"])
        log("전화로 말함" if event.channel == "call" else "문자로 보냄")

    elif event.type == "call_attempted":
        log("업체에 전화했으나 연결되지 않음")

    elif event.type == "reply_received":
        reply_type = event.reply_type
        if reply_type == "accept" and event.amount is not None:
            reply_type = "low_offer"  # 금액이 있는 수용은 서버가 목표·수용선과 비교해 정한다
        # 협상 중에 전화를 안 받거나 나중에 연락 준다고 미루면 기록만 한다. 단계·제시액·직전 답을 그대로 둬서
        # 하던 반박을 이어 간다. 예전에는 답장 기다림으로 돌아가 지난 기한 때문에 곧바로 재요청이 떴다
        if stage_before == "negotiating" and reply_type in ("no_answer", "callback"):
            log(event.text or reply_type)
            return c
        c.last_reply, c.offered = reply_type, event.amount
        log(event.text or reply_type or "")
        if event.reply_type in ("no_answer", "callback"):
            c.stage = _response_wait_stage(c)
        elif reply_type == "accept":
            _agree(c, event.amount, today)
        else:
            c.stage = "negotiating"

    elif event.type == "counter_sent":
        c.stage = _response_wait_stage(c)
        c.deadline_on = today + timedelta(days=POLICY["wait_days"])
        log("반박 문안 발송")

    elif event.type == "agreement_recorded":
        _agree(c, event.amount, today)
        log(f"{c.agreed_amount:,}원에 합의")

    elif event.type == "deposit_confirmed":
        # 금액이 없으면 합의 금액 전부가 들어온 것으로 본다(예전 기록과 호환)
        got = c.agreed_amount - c.deposited if event.amount is None else event.amount
        c.deposited += got
        if c.deposited >= c.agreed_amount:
            c.stage = "closed"
            log(f"입금 확인 {got:,}원")
        else:
            log(f"일부 입금 {got:,}원(남은 {c.agreed_amount - c.deposited:,}원)")

    elif event.type == "escalation_sent":
        c.stage = "escalated"
        c.deadline_on = today + timedelta(days=POLICY["wait_days"])
        log("내용증명 발송")

    elif event.type == "handoff_done":
        c.stage = "handed_off"
        log("1372 소비자상담센터에 접수")

    return c


def _response_wait_stage(case: Case) -> Stage:
    if case.stage == "escalated" or any(record.type == "escalation_sent" for record in case.timeline):
        return "escalated"
    return "waiting"


def add_business_days(start: date, days: int) -> date:
    """start 다음 날부터 주말을 빼고 days 영업일째 되는 날. 환급 지연 기준이 3영업일이다(방문판매법 시행규칙 제22조).
    ponytail: 공휴일 목록이 없어 공휴일은 빼지 않는다. 공휴일이 끼면 법정 기준보다 하루 이상 이르다."""
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


def _agree(c: Case, amount: int | None, today: date) -> None:
    c.stage = "agreed"
    c.agreed_amount = c.refund.refund if amount is None else amount
    c.deposited = 0  # 1372 상담 뒤 다시 합의하면 그 금액을 새로 받는다(그 전 입금은 기록에 남는다)
    c.deposit_due_on = add_business_days(today, POLICY["deposit_days"])


def _md(d: date) -> str:
    """화면 안내용 날짜. %m월 %d일은 "01월 05일"처럼 0을 붙여서 쓰지 않는다."""
    return f"{d.month}월 {d.day}일"


# reason은 화면 맨 위 안내로 그대로 보인다. 다른 화면 문구와 같이 해요체로 쓴다
def next_action(case: Case, today: date) -> Action:
    c = case
    if c.stage == "ready":
        return Action(type="send_notice", reason="해지 의사를 알려야 환불액이 더 줄지 않아요")
    if c.stage in ("waiting", "escalated"):
        if today <= c.deadline_on:
            return Action(type="wait", reason=f"{_md(c.deadline_on)}까지 답을 기다려요")
        if _response_wait_stage(c) == "escalated":
            return Action(type="go_1372", reason="내용증명에도 답이 없어요")
        if c.attempts <= POLICY["max_follow_ups"]:
            return Action(type="follow_up", reason="답변 기한이 지났어요")
        return Action(type="certified_mail", reason="재요청에도 답이 없어요")
    if c.stage == "negotiating":
        if c.last_reply == "low_offer" and c.offered is not None and c.offered >= c.target:
            return Action(type="confirm_agreement", reason="제시액이 희망 금액 이상이에요")
        # 반박을 정한 횟수만큼 보냈는데도 받아들이지 않으면 반박을 되풀이하지 않고 내용증명, 그다음 1372로 간다
        counters = sum(r.type == "counter_sent" for r in c.timeline)
        if counters >= POLICY["max_counters"]:
            # 수용선보다 적은 제시액이면 넘어가는 단계에서도 경고는 그대로 띄운다(완료 기준)
            low = c.last_reply == "low_offer" and c.offered is not None and c.offered < c.floor
            if any(r.type == "escalation_sent" for r in c.timeline):
                return Action(type="go_1372", reason="내용증명 뒤에도 받아들이지 않아요", warn=low)
            return Action(type="certified_mail", reason=f"반박을 {counters}번 보냈는데도 받아들이지 않아요", warn=low)
        if c.last_reply == "low_offer" and c.offered is not None:
            if c.offered < c.floor:
                # 하한선을 따로 정하지 않았으면 예상 환불액이 기준이다. 화면 말과 같게 부른다
                floor_name = "예상 환불액" if c.floor == c.refund.refund else "하한선"
                return Action(type="counter", reason=f"제시액이 {floor_name}보다 적어요", warn=True)
            if c.offered >= c.target:
                return Action(type="confirm_agreement", reason="제시액이 희망 금액 이상이에요")
            return Action(type="counter", reason="하한선은 넘지만 희망 금액보다 적어요. 받아들일지 정하세요")
        return Action(type="counter", reason="근거를 들어 다시 요청하세요")
    if c.stage == "agreed":
        left = f" (남은 {c.agreed_amount - c.deposited:,}원)" if c.deposited else ""
        if today <= c.deposit_due_on:
            return Action(type="wait", reason=f"{_md(c.deposit_due_on)}까지 입금을 기다려요{left}")
        # 기한이 지나면 독촉하고, 그 뒤 wait_days가 더 지나도 다 들어오지 않으면 1372로 간다
        if today <= c.deposit_due_on + timedelta(days=POLICY["wait_days"]):
            return Action(type="remind_deposit", reason=f"입금 기한이 지났어요{left}")
        return Action(type="go_1372", reason=f"입금 기한이 지나고 독촉 뒤에도 입금되지 않았어요{left}")
    if c.stage == "handed_off":
        return Action(type="go_1372", reason="1372 상담 결과를 기다려요")
    return Action(type="close", reason="환불금을 받았어요")
