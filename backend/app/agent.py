"""LLM이 맡는 일: 계약서 읽기, 답장 읽기, 말투 다듬기. 그리고 문안 양식과 검사.

지금은 FakeLLM만 있다. 실제 OpenAI 구현은 같은 메서드 세 개를 채우면 된다(트랙 B).
"""
import re

from .models import Action, Case, ReplyType
from .rules import DATA, RULES

TEMPLATES = {p.stem: p.read_text(encoding="utf-8").strip() for p in (DATA / "templates").glob("*.txt")}
COUNTER_KIND = {"refuse": "counter_refuse", "list_price": "counter_list_price",
                "visit": "counter_visit", "low_offer": "counter_low_offer"}


class FakeLLM:
    """키 없이 개발·테스트하기 위한 가짜 구현. 키워드로만 판단한다."""

    def read_reply(self, text: str) -> tuple[ReplyType, int | None]:
        amount = None
        if m := re.search(r"(\d+)\s*만\s*원?", text):
            amount = int(m.group(1)) * 10_000
        elif m := re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,})\s*원", text):
            amount = int(m.group(1).replace(",", ""))
        if amount is not None:
            return "low_offer", amount
        for words, kind in ((("정상가", "정가"), "list_price"), (("방문", "오셔", "와서"), "visit"),
                            (("불가", "안 돼", "안돼", "안 됩니다"), "refuse"),
                            (("알겠", "해드릴", "환불해", "처리해"), "accept")):
            if any(w in text for w in words):
                return kind, None
        return "unknown", None

    def polish(self, text: str, tone: str) -> str:
        return text


llm = FakeLLM()


def facts(case: Case) -> dict[str, str]:
    c, r = case.contract, case.refund
    return {
        "gym": c.gym_name or "센터",
        "total": f"{c.total_paid:,}", "used": f"{r.used_amount:,}", "penalty": f"{r.penalty:,}",
        "refund": f"{r.refund:,}", "used_days": str(r.used_days), "total_days": str(r.total_days),
        "start": f"{c.start_date:%Y년 %m월 %d일}",
        "notified": f"{case.notified_on:%Y년 %m월 %d일}" if case.notified_on else "오늘",
        "offered": f"{case.offered:,}" if case.offered is not None else "",
        "agreed": f"{case.agreed_amount:,}" if case.agreed_amount is not None else "",
        "due": f"{case.deposit_due_on:%m월 %d일}" if case.deposit_due_on else "",
    }


def render(kind: str, case: Case) -> str:
    return TEMPLATES[kind].format(**facts(case))


def validate(text: str, case: Case) -> bool:
    """문안 속 금액은 계산된 금액이어야 하고, 조문은 근거 표에 있어야 한다."""
    allowed = {v for v in facts(case).values() if v}
    amounts = re.findall(r"(\d{1,3}(?:,\d{3})+)\s*원", text)
    articles = set(re.findall(r"제\s*(\d+)\s*조", text))
    known = {a for rule in RULES.values() for a in re.findall(r"제\s*(\d+)\s*조", rule["title"])}
    return all(a in allowed for a in amounts) and articles <= known


def drafts_for(case: Case, action: Action) -> dict[str, str]:
    """지금 행동에 필요한 문안. 키는 양식 이름이다."""
    kinds = {
        "send_notice": ["notice_sms", "call_card", "after_call_sms"],
        "follow_up": ["follow_up"],
        "counter": [COUNTER_KIND.get(case.last_reply or "", "counter_unknown")],
        "confirm_agreement": ["accept_offer"],
        "certified_mail": ["certified_mail"],
        "go_1372": ["go_1372"],
        "remind_deposit": ["remind_deposit"],
    }.get(action.type, [])
    if action.type == "wait" and case.stage == "agreed":
        kinds = ["confirm_agreement"]
    return {k: render(k, case) for k in kinds}
