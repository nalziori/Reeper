"""여러 답장이 이어질 때의 흐름을 조합으로 돌린다(키 없음).

답장 읽기 결과가 정해진 다음부터(문안 고르기 → 반박 횟수 → 내용증명 → 1372)는 정해진 로직이다.
2026-11-22에 업체 사정 사건의 한 번뿐인 반박이 "확인한 뒤 다시 연락드리겠습니다"가 되어, 내 입장을 한 번도
말하지 않고 1372로 넘어간 일이 있었다(#166). 답장 하나씩 보는 테스트로는 이어지는 흐름을 못 봐서 조합으로 본다.
"""
from datetime import date
from itertools import product

import pytest

from app import agent
from app.engine import apply, next_action, open_case
from app.models import Contract, Event

CONTRACT = Contract(gym_name="가상피트니스", total_paid=600_000,
                    start_date=date(2026, 11, 5), end_date=date(2027, 2, 2))
D = date(2026, 11, 14)

# 업체 답(유형, 원문, 금액). None 금액의 low_offer는 '다퉈질 때 금액'(업체 사정 사건만 있음)을 뜻한다
REPLIES = {
    "refuse": ("refuse", "환불은 어렵습니다", None),
    "list_price": ("list_price", "정상가로 다시 계산해야 합니다", None),
    "visit": ("visit", "센터에 직접 오셔서 서류를 쓰셔야 합니다", None),
    "unknown": ("unknown", "환불 요청은 접수했습니다. 처리 중입니다.", None),
    "unknown_fault": ("unknown", "새 강사를 배정해 드렸으니 저희 귀책이 없어 위약금을 부담할 수 없습니다.", None),
    "low": ("low_offer", "10만원까지 가능합니다", 100_000),
    "low_disputed": ("low_offer", "위약금 빼고 넣어 드릴게요", None),
    "callback": ("callback", "확인해 보고 연락드릴게요", None),  # no_answer도 같은 기다림이라 하나만 둔다
}
SENT_FOR = {"counter": "counter_sent", "certified_mail": "escalation_sent"}


def run(reason: str, seq: tuple[str, ...]) -> list[tuple[str, str]]:
    """답장을 차례로 넣고, 보낼 글이 나오면 보냈다고 기록한다. 지나간 (행동, 문안) 목록을 돌려준다."""
    case = open_case(CONTRACT.model_copy(update={"cancel_reason": reason,
                                                 "fault_kind": "trainer_change" if reason == "business" else None}), D)
    case = apply(case, Event(type="notice_sent", channel="sms"), D)
    seen: list[tuple[str, str]] = []
    for name in seq:
        kind, text, amount = REPLIES[name]
        if name == "low_disputed":
            amount = case.refund.disputed_refund if reason == "business" else 400_000
        case = apply(case, Event(type="reply_received", reply_type=kind, text=text, amount=amount), D)
        action = next_action(case, D)
        drafts = agent.drafts_for(case, action)
        for k, body in drafts.items():
            assert agent.validate(body, case), (reason, seq, k, body)
            seen.append((action.type, k))
        if action.type == "go_1372":
            break
        if action.type in SENT_FOR:
            case = apply(case, Event(type=SENT_FOR[action.type]), D)
    return seen


SEQS = list(product(REPLIES, repeat=4))  # 소비자 사정은 반박 두 번, 내용증명, 다시 거절까지 답장 네 번이 지나야 1372에 닿는다


@pytest.mark.parametrize("reason", ["consumer", "business"])
def test_no_case_reaches_1372_without_stating_the_users_position(reason):
    """1372로 넘어가기 전에, 해지 이유·금액을 밝힌 글(확인 후 연락이 아닌 반박이나 내용증명)을 한 번은 보낸다.
    업체 사정 사건은 반박이 한 번뿐이라, 어떤 답이 와도 반박 문안이 '확인 후 연락'이 되지 않는다."""
    reached = 0
    for seq in SEQS:
        seen = run(reason, seq)
        if reason == "business":
            assert ("counter", "counter_unknown") not in seen, seq
        if seen and seen[-1][0] == "go_1372":
            reached += 1
            sent = [k for a, k in seen[:-1] if a in SENT_FOR]
            assert any(k != "counter_unknown" for k in sent), (reason, seq, seen)
    assert reached > 0  # 조합이 실제로 1372까지 닿는지(검사가 비어 있지 않은지)
