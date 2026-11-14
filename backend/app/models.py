"""공유 계약: 사건 상태, 이벤트, 행동. 바꾸기 전에 docs/계약.md와 다른 트랙 담당자를 확인한다."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["ready", "waiting", "negotiating", "escalated", "agreed", "closed", "handed_off"]
ReplyType = Literal[
    "accept", "low_offer", "refuse", "list_price", "visit", "unknown",  # 업체의 답
    "no_answer", "callback",  # 통화 결과: 안 받음, 나중에 연락 준다고 함
]
EventType = Literal[
    "notice_sent", "reply_received", "time_passed",
    "agreement_recorded", "deposit_confirmed", "escalation_sent", "handoff_done",
]
ActionType = Literal[
    "send_notice", "wait", "follow_up", "counter", "confirm_agreement",
    "certified_mail", "go_1372", "remind_deposit", "close",
]


class Contract(BaseModel):
    gym_name: str = ""
    total_paid: int = Field(gt=0)  # 실제 결제금액(원)
    start_date: date
    end_date: date
    special_terms: str = ""


class Refund(BaseModel):
    total_days: int
    used_days: int
    used_amount: int
    penalty: int
    refund: int
    per_day_loss: int
    refs: list[str]  # data/rules.json의 id
    provisional: bool = True  # 고시 원문 확인 전


class Record(BaseModel):
    on: date
    type: str
    text: str = ""


class Case(BaseModel):
    contract: Contract
    refund: Refund
    target: int  # 목표 금액
    floor: int  # 최저 수용선
    stage: Stage = "ready"
    notified_on: date | None = None  # 해지 의사 도달일
    deadline_on: date | None = None  # 답변 기한
    attempts: int = 0  # 통지·재요청 횟수
    last_reply: ReplyType | None = None
    offered: int | None = None  # 업체가 마지막으로 제시한 금액
    agreed_amount: int | None = None
    deposit_due_on: date | None = None
    timeline: list[Record] = []


class Event(BaseModel):
    type: EventType
    channel: Literal["sms", "call"] | None = None  # notice_sent
    text: str = ""  # reply_received: 붙여넣은 답장이나 통화 메모
    reply_type: ReplyType | None = None  # 버튼으로 고른 경우. 없으면 text를 읽어 분류한다
    amount: int | None = None


class Action(BaseModel):
    type: ActionType
    reason: str
    warn: bool = False  # 제시액이 최저 수용선보다 적음
