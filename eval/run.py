"""답장 읽기 평가. 업체 답장 정답셋(replies_*.jsonl)으로 유형과 제시액 정답률을 잰다.

기본은 가짜 LLM(키워드 판단)이라 키 없이 돈 들지 않고 돈다. 실제 모델은 --live를 붙여야만
부르며 답장 1건에 1번 호출한다. 유료라 돌리기 전에 팀에 먼저 말한다.

    python eval/run.py            # 가짜 LLM
    python eval/run.py --live     # 실제 모델 (OPENAI_API_KEY 필요)

계약서 사진 추출 평가는 --photos --live로 돈다(12회 호출). eval/README.md의 run.py --photos 참고.
"""
import argparse
import base64
import os
import re
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app import agent  # noqa: E402


def load(paths=None) -> list[dict]:
    rows = []
    for p in paths or sorted(ROOT.glob("replies_*.jsonl")):
        rows += [json.loads(line) for line in Path(p).read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def score(rows: list[dict]) -> dict:
    """한 건씩 읽혀 유형과 제시액을 정답과 비교한다. 제시액은 정답이 low_offer인 건만 센다."""
    misses, fallbacks, by_type = [], 0, Counter()
    type_ok = amount_ok = amount_n = 0
    for r in rows:
        kind, amount, failed = agent.read_reply(r["text"])
        fallbacks += failed
        ok_t = kind == r["reply_type"]
        type_ok += ok_t
        by_type[(r["reply_type"], ok_t)] += 1
        ok_a = True
        if r["reply_type"] == "low_offer":
            amount_n += 1
            ok_a = amount == r["amount"]
            amount_ok += ok_a
        if not (ok_t and ok_a):
            misses.append({"id": r["id"], "want": [r["reply_type"], r["amount"]], "got": [kind, amount]})
    return {"n": len(rows), "type_acc": type_ok / len(rows) if rows else 0.0,
            "amount_n": amount_n, "amount_acc": amount_ok / amount_n if amount_n else 0.0,
            "fallbacks": fallbacks, "misses": misses,
            "per_type": {t: f"{by_type[(t, True)]}/{by_type[(t, True)] + by_type[(t, False)]}"
                         for t in sorted({t for t, _ in by_type})}}


NO_TERMS = re.compile(r"^(없음|해당\s*없음|별도의?\s*특약\s*사항은?\s*없(다|음|습니다))\.?$")


# 인용 앞의 칸 이름("특약사항", "비고(특약)", "제5조(특약)")만 떼고, 남은 글 전체가 특약 없음 표현이어야 한다.
TERMS_LABEL = re.compile(r"^\s*(?:제\s*\d+\s*조\s*)?\(?\s*(?:비고\s*\(\s*특약\s*\)|특약\s*사항|특약)\s*\)?\s*[:：]?\s*")


def _quote_says_no_terms(quote: str) -> bool:
    return bool(NO_TERMS.match(TERMS_LABEL.sub("", quote, count=1).strip()))


def norm(name: str, value):
    """채점용으로 값을 맞춘다. 특약 없음의 여러 표현은 빈 문자열, 글은 공백을 지운다."""
    if isinstance(value, str):
        value = re.sub(r"\s+", "", value) if name != "special_terms" else " ".join(value.split())
        if name == "special_terms" and _quote_says_no_terms(value):  # "특약: 없음"처럼 칸 이름을 단 값도
            value = ""
    return value


def score_photos(rows: list[dict], photo_dir: Path = ROOT / "contract_photos") -> dict:
    """사진이 있는 계약서만 agent.extract_contract로 읽어 추출 필드 5개를 정답과 비교한다."""
    fields, results = list(agent.FIELDS), []
    rows = [r for r in rows if "photo_layout" in r]
    missing = [r["id"] for r in rows if not (photo_dir / f"{r['id']}.jpg").exists()]
    if missing:  # 빠진 사진을 건너뛰면 분모가 줄어 점수가 좋아 보인다. 호출 전에 멈춘다.
        raise FileNotFoundError(f"사진이 없다: {', '.join(missing)}")
    for r in rows:
        img = photo_dir / f"{r['id']}.jpg"
        url = "data:image/jpeg;base64," + base64.b64encode(img.read_bytes()).decode()
        got, failed = agent.extract_contract(url)
        want = {f: r["contract"].get(f, "") for f in fields}
        ok = {}
        for f in fields:
            value = got[f].value
            # 추출기가 빈 특약을 None으로 바꾼다. 인용문이 "없음" 같은 특약 없음 표현으로 끝날 때만
            # 특약 없음을 읽은 것으로 본다. "특약사항"처럼 칸 이름만 인용했으면 못 읽은 것이다.
            if f == "special_terms" and value is None and _quote_says_no_terms(got[f].quote):
                value = ""
            ok[f] = value is not None and norm(f, value) == norm(f, want[f])
        results.append({"id": r["id"], "layout": r["photo_layout"], "failed": failed, "ok": ok,
                        "checks": sum(got[f].check for f in fields)})
    n = len(results)
    return {"n": n, "fields": {f: sum(x["ok"][f] for x in results) for f in fields},
            "all_ok": sum(all(x["ok"].values()) for x in results),
            "failed": sum(x["failed"] for x in results), "results": results}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="실제 모델을 부른다(유료)")
    ap.add_argument("--photos", action="store_true", help="계약서 사진 추출을 평가한다(--live 필요)")
    ap.add_argument("files", nargs="*", help="기본: eval/replies_*.jsonl 전부")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not args.live:
        agent.llm = agent.FAKE
    elif agent.llm is agent.FAKE:
        sys.exit("--live에는 OPENAI_API_KEY가 필요하다")
    if args.photos:
        if not args.live:
            sys.exit("사진 추출은 실제 모델만 읽는다. --photos --live로 돌린다(유료)")
        os.environ["ALLOW_UPLOAD"] = "1"
        s = score_photos(load([ROOT / "contracts.jsonl"]))
        print(f"모델: {getattr(agent.llm, 'model', '')}  사진 {s['n']}장 (워드에서 내보낸 이미지, 실제 사진보다 쉽다)")
        print("필드별:", ", ".join(f"{f} {k}/{s['n']}" for f, k in s["fields"].items()),
              f" 전부 맞음 {s['all_ok']}/{s['n']}  대체 {s['failed']}")
        for x in s["results"]:
            bad = [f for f, v in x["ok"].items() if not v]
            print(f"  {x['id']} {x['layout']}: {'OK' if not bad else '틀림 ' + ', '.join(bad)}  확인필요 {x['checks']}")
        return
    s = score(load(args.files))
    print(f"모델: {type(agent.llm).__name__}  답장 {s['n']}건")
    print(f"유형 정답률 {s['type_acc']:.1%}  제시액 정답률 {s['amount_acc']:.1%} ({s['amount_n']}건)  대체 {s['fallbacks']}건")
    print("유형별:", ", ".join(f"{t} {v}" for t, v in s["per_type"].items()))
    for m in s["misses"]:
        print(f"  틀림 {m['id']}: 정답 {m['want']} / 응답 {m['got']}")


if __name__ == "__main__":
    main()
