"""키워드 판정(FakeLLM)의 회귀 테스트. 평가 답장 164건과 변형 435건에서 지금 맞히는 것을 고정한다.

규칙을 고칠 때 다른 문장이 깨지는 것을 사람 눈이 아니라 테스트로 막는다(docs/어려운_답장_작업_분담.md B2).
지금 틀리는 건의 id는 keyword_misses.txt에 있다. 목록 밖의 건이 틀리면 실패하고, 목록의 건이 맞게 되면
목록에서 지우라고 실패한다. 목록 다시 쓰기: backend에서 `PYTHONPATH=. python tests/test_keyword_regression.py`
"""
import importlib.util
from pathlib import Path

from app import agent

EVAL = Path(__file__).resolve().parents[2] / "eval"
spec = importlib.util.spec_from_file_location("eval_run", EVAL / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

FILES = ["replies_b.jsonl", "replies_c.jsonl", "unseen_replies_b.jsonl", "unseen_replies_c.jsonl",
         "hard_replies_c.jsonl", "perturbed_c.jsonl"]
MISSES = Path(__file__).with_name("keyword_misses.txt")


def read_all() -> tuple[set[str], dict[str, str]]:
    """(틀린 id, 위험하게 틀린 id와 읽은 결과). 채점은 eval/run.py와 같다."""
    missed, risky = set(), {}
    for r in run.load([EVAL / f for f in FILES]):
        kind, amount = agent.FAKE.read_reply(r["text"])
        ok_type = kind == r["reply_type"] or kind in r.get("also", [])
        ok_amount = amount == r["amount"] if r["reply_type"] == "low_offer" else amount is None
        if not (ok_type and ok_amount):
            missed.add(r["id"])
            if run.risk(r, kind, amount) == "high":
                risky[r["id"]] = f"{kind} {amount}"
    return missed, risky


def test_keyword_reader_keeps_what_it_gets_right():
    known = set(MISSES.read_text(encoding="utf-8").split())
    missed, risky = read_all()
    assert not risky, f"위험하게 틀린다(잘못된 수용, 없는 금액, 틀린 금액): {risky}"
    assert not missed - known, f"맞던 답장이 틀리게 됐다: {sorted(missed - known)}"
    assert not known - missed, f"이제 맞는다. keyword_misses.txt에서 지운다: {sorted(known - missed)}"


if __name__ == "__main__":
    MISSES.write_text("\n".join(sorted(read_all()[0])) + "\n", encoding="utf-8", newline="\n")


def test_man_with_remainder_is_one_amount():
    read = agent.FAKE.read_reply
    assert read("계산하신 47만 3,334원 맞습니다. 입금해 드릴게요.") == ("low_offer", 473334)  # 3,334원으로 읽던 버그
    assert read("47만 3천원 드릴게요") == ("low_offer", 473000)
    assert read("40만 3일 안에 입금해 드릴게요") == ("low_offer", 400000)  # 뒤에 원이 없으면 붙이지 않는다
