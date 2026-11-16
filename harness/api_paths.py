"""API 하니스: 가짜 LLM으로 사건의 모든 경로를 서버에 흘려 단언한다.
실행: python harness/api_paths.py   (backend/.venv가 있으면 그 파이썬으로 서버를 띄운다)"""
import sys
from datetime import date, timedelta

from lib import call, server

D0 = date(2026, 11, 16)
# 사건 단계 전이 그래프에서 허용되는 이동. 응답마다 이 밖으로 나가면 불변식 위반이다.
ALLOWED = {
    ("ready", "ready"), ("ready", "waiting"),
    ("waiting", "waiting"), ("waiting", "negotiating"), ("waiting", "agreed"), ("waiting", "escalated"),
    ("waiting", "handed_off"),
    ("negotiating", "negotiating"), ("negotiating", "waiting"), ("negotiating", "escalated"),
    ("negotiating", "agreed"),
    ("escalated", "escalated"), ("escalated", "negotiating"), ("escalated", "agreed"),
    ("escalated", "handed_off"),
    ("handed_off", "handed_off"), ("handed_off", "agreed"),
    ("agreed", "agreed"), ("agreed", "closed"), ("closed", "closed"),
}
rows: list[tuple[str, str, str]] = []
failures: list[str] = []


class Case:
    """사건 하나를 서버에 흘리는 도우미. 단계 이동과 기본 불변식을 매 호출마다 확인한다."""

    def __init__(self, base, label, contract, target=None, floor=None, day=0):
        self.base, self.label, self.day, self.trail = base, label, day, []
        body = {"contract": contract, "today": self.today.isoformat()}
        if target is not None:
            body["target"], body["floor"] = target, floor
        status, res = call(base, "/api/cases", body)
        assert status == 200, (label, status, res)
        self.res = res
        self.trail.append(res["case"]["stage"])

    @property
    def today(self):
        return D0 + timedelta(days=self.day)

    @property
    def case(self):
        return self.res["case"]

    @property
    def stage(self):
        return self.case["stage"]

    @property
    def action(self):
        return self.res["action"]["type"]

    def step(self, event, day=None, expect=200):
        if day is not None:
            self.day = day
        before = self.stage
        status, res = call(self.base, "/api/cases/step",
                           {"case": self.case, "event": event, "today": self.today.isoformat()})
        assert status == expect, f"{self.label}: {event} → {status} {res}"
        if status == 200:
            after = res["case"]["stage"]
            assert (before, after) in ALLOWED, f"{self.label}: 허용되지 않은 전이 {before}→{after}"
            c = res["case"]
            assert c["target"] >= c["floor"] >= 0, f"{self.label}: 목표·수용선 불변식 위반"
            if event["type"] != "time_passed":  # 시간 경과는 사건을 바꾸지 않는다
                self.res = res
            else:
                assert res["case"] == self.case, f"{self.label}: time_passed가 사건을 바꿨다"
                self.res = res
            if self.stage != self.trail[-1]:
                self.trail.append(self.stage)
        return res

    def done(self, name, ok_note=""):
        rows.append((name, " → ".join(self.trail), ok_note or "통과"))


def check(cond, msg):
    if not cond:
        failures.append(msg)
        raise AssertionError(msg)


def scenario(name):
    def deco(fn):
        def run(base, contract):
            try:
                fn(base, contract)
            except AssertionError as e:
                rows.append((name, "-", f"실패: {e}"))
                failures.append(f"{name}: {e}")
        run.__name__ = fn.__name__
        return run
    return deco


@scenario("a 수용")
def path_accept(base, contract):
    c = Case(base, "a", contract)
    check(c.action == "send_notice", "시작 행동이 send_notice가 아님")
    check({"notice_sms", "call_card", "after_call_sms"} <= set(c.res["drafts"]), "접수 문안 키 누락")
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "reply_received", "reply_type": "accept"})
    check(c.stage == "agreed" and c.case["agreed_amount"] == c.case["refund"]["refund"], "수용 금액이 환불액이 아님")
    c.step({"type": "deposit_confirmed"})
    check(c.stage == "closed" and c.action == "close", "종결 실패")
    c.done("a 수용")


@scenario("b 저액 제시 → 반박 → 합의")
def path_low_offer(base, contract):
    c = Case(base, "b", contract, target=460000, floor=400000)
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "reply_received", "reply_type": "low_offer", "amount": 100000})
    check(c.action == "counter" and c.res["action"]["warn"], "수용선 미만 제시에 경고가 없음")
    check("counter_low_offer" in c.res["drafts"], "반박 문안 키 누락")
    c.step({"type": "counter_sent"})
    check(c.stage == "waiting", "반박 뒤 waiting이 아님")
    c.step({"type": "reply_received", "reply_type": "low_offer", "amount": 400000})
    check(c.action == "counter" and not c.res["action"]["warn"], "수용선 정확히 400000에서 경고가 떠야 하지 않음")
    c.step({"type": "reply_received", "reply_type": "low_offer", "amount": 399999})
    check(c.res["action"]["warn"], "수용선보다 1원 적은데 경고가 없음")
    c.step({"type": "reply_received", "reply_type": "low_offer", "amount": 460000})
    check(c.action == "confirm_agreement" and "accept_offer" in c.res["drafts"], "목표 금액 제시가 합의 확인이 아님")
    c.step({"type": "agreement_recorded", "amount": 460000})
    c.step({"type": "deposit_confirmed"})
    check(c.stage == "closed", "종결 실패")
    c.done("b 저액 제시 → 반박 → 합의")


@scenario("c 정상가 주장")
def path_list_price(base, contract):
    c = Case(base, "c", contract)
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "reply_received", "reply_type": "list_price"})
    check(c.action == "counter" and "counter_list_price" in c.res["drafts"], "정상가 반박 문안 없음")
    c.done("c 정상가 주장")


@scenario("d 방문 요구")
def path_visit(base, contract):
    c = Case(base, "d", contract)
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "reply_received", "reply_type": "visit"})
    check(c.action == "counter" and "counter_visit" in c.res["drafts"], "방문 반박 문안 없음")
    c.done("d 방문 요구")


@scenario("e 무응답 → 재요청 → 내용증명 → 1372 → 합의")
def path_silence(base, contract):
    c = Case(base, "e", contract)
    c.step({"type": "notice_sent", "channel": "sms"})
    d = c.case["deadline_on"]
    c.step({"type": "time_passed"}, day=3)
    check(c.action == "wait", "기한 당일이 wait가 아님")
    c.step({"type": "time_passed"}, day=4)
    check(c.action == "follow_up" and "follow_up" in c.res["drafts"], f"기한 다음 날이 follow_up이 아님({d})")
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "time_passed"}, day=8)
    check(c.action == "certified_mail" and "certified_mail" in c.res["drafts"], "내용증명 단계가 아님")
    c.step({"type": "escalation_sent"})
    check(c.stage == "escalated", "escalated가 아님")
    c.step({"type": "time_passed"}, day=12)
    check(c.action == "go_1372" and "go_1372" in c.res["drafts"], "1372 단계가 아님")
    c.step({"type": "handoff_done"})
    c.step({"type": "agreement_recorded", "amount": 0}, expect=409)
    c.step({"type": "agreement_recorded"}, expect=409)
    c.step({"type": "agreement_recorded", "amount": 300000})
    check(c.stage == "agreed" and c.case["agreed_amount"] == 300000, "1372 후 합의 실패")
    c.step({"type": "deposit_confirmed"})
    check(c.stage == "closed", "종결 실패")
    c.done("e 무응답 → 재요청 → 내용증명 → 1372 → 합의")


@scenario("f 합의 → 입금 지연 → 입금")
def path_late_deposit(base, contract):
    c = Case(base, "f", contract)
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "reply_received", "reply_type": "accept"})
    c.step({"type": "time_passed"}, day=3)
    check(c.action == "wait", "입금 기한 당일이 wait가 아님")
    c.step({"type": "time_passed"}, day=4)
    check(c.action == "remind_deposit" and "remind_deposit" in c.res["drafts"], "입금 요청이 나오지 않음")
    c.step({"type": "deposit_confirmed"})
    check(c.stage == "closed", "종결 실패")
    c.done("f 합의 → 입금 지연 → 입금")


@scenario("g 시연 버튼 문장(가짜 LLM 키워드 판단)")
def path_demo_phrases(base, contract):
    want = {"네 알겠습니다 환불해 드릴게요": "accept", "20만원만 드릴게요": "low_offer",
            "이벤트 상품은 환불 불가입니다": "refuse", "정상가 기준으로 차감합니다": "list_price",
            "방문하셔야 처리됩니다": "visit"}
    seen = {}
    for text, expected in want.items():
        c = Case(base, "g", contract)
        c.step({"type": "notice_sent", "channel": "sms"})
        res = c.step({"type": "reply_received", "text": text})
        seen[text] = c.case["last_reply"]
        check(c.case["last_reply"] == expected, f"'{text}' → {c.case['last_reply']} (기대 {expected})")
        check(res.get("llm_fallback") in (False, None, True), "응답 형태 이상")
    rows.append(("g 시연 버튼 문장", "5개 문장 분류", "통과"))


@scenario("h 거절돼야 하는 입력")
def path_rejections(base, contract):
    c = Case(base, "h", contract)
    c.step({"type": "deposit_confirmed"}, expect=409)         # 통지 전 입금 확인
    c.step({"type": "reply_received", "reply_type": "accept"}, expect=409)  # 통지 전 답장
    c.step({"type": "notice_sent", "channel": "sms"})
    c.step({"type": "reply_received", "reply_type": "low_offer", "amount": -5}, expect=409)
    c.step({"type": "reply_received", "reply_type": "accept", "amount": 0}, expect=409)
    c.step({"type": "reply_received", "reply_type": "accept", "amount": 100000})  # 금액 있는 수용 → 합의 아님
    check(c.stage == "negotiating" and c.action == "counter" and c.res["action"]["warn"],
          "금액 있는 accept가 수용선 비교를 건너뜀")
    c.day = -1  # 마지막 기록보다 이른 날짜
    c.step({"type": "time_passed"}, expect=409)
    status, _ = call(base, "/api/cases", {"contract": contract, "today": D0.isoformat(), "target": 10, "floor": 20})
    check(status == 422, f"수용선>목표가 422가 아님({status})")
    status, _ = call(base, "/api/cases", raw=b"x" * 400_000)
    check(status == 413, f"큰 본문이 413이 아님({status})")
    status, _ = call(base, "/api/health")
    check(status == 200, "health 실패")
    rows.append(("h 거절돼야 하는 입력", "409·422·413", "통과"))


def main() -> int:
    with server() as base:
        status, samples = call(base, "/api/samples")
        assert status == 200 and samples, "샘플이 없음"
        health = call(base, "/api/health")[1]
        print(f"서버: llm={health['llm']} upload={health['upload']} calls_left={health['calls_left']}")
        contract = samples[0]["contract"]
        for fn in (path_accept, path_low_offer, path_list_price, path_visit, path_silence,
                   path_late_deposit, path_demo_phrases, path_rejections):
            fn(base, contract)
    width = max(len(r[0]) for r in rows)
    for name, trail, note in rows:
        print(f"{name.ljust(width)}  {trail}  [{note}]")
    print(f"\n{len(rows) - len(failures)}/{len(rows)} 통과")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
