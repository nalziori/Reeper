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
    "notice_sent", "call_attempted", "reply_received", "counter_sent", "time_passed",
    "agreement_recorded", "deposit_confirmed", "escalation_sent", "handoff_done",
]
# 업체 쪽 사정의 유형. data/mediation_cases.json의 kinds와 같은 이름에 other를 더했다
FaultKind = Literal["trainer_change", "schedule_cut", "closure", "relocation", "other"]
ActionType = Literal[
    "send_notice", "wait", "follow_up", "counter", "confirm_agreement",
    "certified_mail", "go_1372", "remind_deposit", "close",
]


class Contract(BaseModel):
    gym_name: str = ""
    total_paid: int = Field(gt=0)  # 실제 결제금액(원). 보증금은 빼고 security_deposit에 따로
    start_date: date
    end_date: date
    special_terms: str = ""
    unit: Literal["day", "month", "count"] = "day"  # 계약서의 공급 단위(고시 제2조 제3호). 없으면 일
    total_count: int | None = Field(default=None, gt=0)  # 월·회 단위의 총 개월 수 또는 총 횟수
    used_count: int | None = Field(default=None, ge=0)  # 회 단위에서 이미 쓴 횟수
    addon_value: int = Field(default=0, ge=0)  # 계약서에 가액이 적힌 부가상품만(고시 제6조 제2항)
    security_deposit: int = Field(default=0, ge=0)  # 보증금. 전액 돌려받는다(고시 제5조 제2항)
    # 해지 이유. 사용자가 고른 값이고 서버는 업체 잘못이 맞는지 판단하지 않는다. 금액에 어떻게 반영할지는 rules.py가 정한다
    cancel_reason: Literal["consumer", "business"] = "consumer"
    fault_kind: FaultKind | None = None  # 업체 쪽 사정일 때의 유형. 문안의 사유 구절을 고르는 데만 쓴다


class Refund(BaseModel):
    total_days: int  # 총 단위 수(unit이 일이 아니면 개월 수·횟수)
    used_days: int  # 이용한 단위 수
    used_amount: int
    penalty: int
    refund: int
    per_day_loss: int  # 한 단위 늦을 때마다 줄어드는 금액
    addon: int = 0  # 공제한 부가상품 가액
    unit_label: str = "일"  # total_days·used_days의 단위: 일·개월·회
    security_deposit: int = 0  # 환불액에 더한 보증금
    refs: list[str]  # data/rules.json의 id
    provisional: bool = True  # 고시 원문 확인 전


class Record(BaseModel):
    on: date
    type: str
    text: str = ""


class Ground(BaseModel):
    rule_id: str  # data/rules.json의 id
    why: str  # 이 건에서 왜 쓰는지
    verified: bool = False  # 근거 표에서 확인된 근거인지. 서버가 붙인다


class ContractPoint(BaseModel):
    quote: str  # 특약 원문 그대로
    how_to_handle: str


class Objection(BaseModel):
    objection: str  # 업체가 할 법한 반론
    response: str


class Strategy(BaseModel):
    """상황 설명을 듣고 LLM이 세운 전략. 표시용이며 단계 전이와 금액은 이 값을 보지 않는다."""
    summary: str = ""
    grounds: list[Ground] = []
    contract_points: list[ContractPoint] = []
    objections: list[Objection] = []
    cautions: list[str] = []  # 기대를 조정하는 안내
    questions: list[str] = []  # 사용자에게 되물을 것


class Case(BaseModel):
    contract: Contract
    refund: Refund
    target: int  # 희망 금액
    floor: int  # 하한선
    stage: Stage = "ready"
    notified_on: date | None = None  # 해지 의사 도달일
    deadline_on: date | None = None  # 답변 기한
    attempts: int = 0  # 통지·재요청 횟수
    last_reply: ReplyType | None = None
    offered: int | None = None  # 업체가 마지막으로 제시한 금액
    agreed_amount: int | None = None
    deposited: int = 0  # 합의 뒤 확인한 입금 합계. agreed_amount 이상이 되면 종결한다
    deposit_due_on: date | None = None
    timeline: list[Record] = []
    situation: str = Field(default="", max_length=1000)  # 사용자가 적은 상황 설명
    strategy: Strategy | None = None  # POST /api/cases/strategy가 채운다


class Event(BaseModel):
    type: EventType
    channel: Literal["sms", "call"] | None = None  # notice_sent
    text: str = ""  # reply_received: 붙여넣은 답장이나 통화 메모
    reply_type: ReplyType | None = None  # 버튼으로 고른 경우. 없으면 text를 읽어 분류한다
    amount: int | None = None


class Action(BaseModel):
    type: ActionType
    reason: str
    warn: bool = False  # 제시액이 하한선보다 적음


class Claim(BaseModel):
    """업체 답장 속 주장 하나. 사용자에게만 보여 준다."""
    quote: str  # 답장 원문 그대로
    claim: str  # 무슨 주장인지
    rule_id: str | None = None  # data/rules.json의 id. 없으면 화면이 "확인 필요"로 보여 준다
    advice: str  # 어떻게 답하면 되는지


class Analysis(BaseModel):
    """붙여넣은 답장을 LLM이 짚은 결과. 표시용이며 단계 전이와 금액은 이 값을 보지 않는다."""
    claims: list[Claim] = []
    note: str = ""  # 지금 조심할 점


class Extracted(BaseModel):
    """계약서 사진에서 읽은 값 하나. 화면은 check가 참인 값을 사람에게 확인받는다."""
    value: str | int | None
    confidence: float  # 0~1. LLM이 스스로 매긴 값이라 참고용이다
    quote: str = ""  # 값을 읽은 자리의 원문
    check: bool = True
