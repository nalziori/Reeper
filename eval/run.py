"""답장 읽기 평가. 업체 답장 정답셋(replies_*.jsonl)으로 유형과 제시액 정답률을 잰다.

기본은 가짜 LLM(키워드 판단)이라 키 없이 돈 들지 않고 돈다. 실제 모델은 --live를 붙여야만
부르며 답장 1건에 1번 호출한다. 유료라 돌리기 전에 팀에 먼저 말한다.

    python eval/run.py            # 가짜 LLM
    python eval/run.py --live     # 실제 모델 (OPENAI_API_KEY 필요)

계약서 추출 평가는 아직 없다. 추출기가 사진만 받는데 contracts.jsonl은 글이다.
"""
import argparse
import base64
import os
import re
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app import agent  # noqa: E402
from app.engine import open_case  # noqa: E402
from app.models import Contract  # noqa: E402


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


def score_plans(rows: list[dict]) -> dict:
    """앱과 같은 사건으로 전략을 만들고, 반환된 근거만 채점한다."""
    rules = json.loads((ROOT.parent / "data" / "rules.json").read_text(encoding="utf-8"))
    results = []
    for r in rows:
        today = date.fromisoformat(r["today"])
        case = open_case(Contract.model_validate(r["contract"]), today)
        strategy = agent.plan(case, r["situation"], today)
        rule_ids = [g["rule_id"] for g in strategy.get("grounds", [])]
        returned = set(rule_ids)
        required = set(r["must_grounds"])
        empty = strategy.get("fallback", False) or not any(
            strategy.get(key) for key in
            ("summary", "grounds", "contract_points", "objections", "cautions", "questions")
        )
        results.append({"id": r["id"], "rule_ids": rule_ids,
                        "must_hit": len(returned & required) if required else None,
                        "must_n": len(required),
                        "forbid_hit": len(returned & set(r["forbid_grounds"])),
                        "out_of_table": len(returned - rules.keys()), "empty": bool(empty)})
    must_hit = sum(r["must_hit"] or 0 for r in results)
    must_n = sum(r["must_n"] for r in results)
    return {"n": len(rows), "must_hit": must_hit, "must_n": must_n,
            "must_recall": must_hit / must_n if must_n else None,
            "forbid_hits": sum(r["forbid_hit"] for r in results),
            "out_of_table": sum(r["out_of_table"] for r in results),
            "empty": sum(r["empty"] for r in results), "situations": results}


NO_TERMS = re.compile(r"^(없음|해당\s*없음|별도의?\s*특약\s*사항은?\s*없(다|음|습니다)\.?)$")


def norm(name: str, value):
    """채점용으로 값을 맞춘다. 특약 없음의 여러 표현은 빈 문자열, 글은 공백을 지운다."""
    if isinstance(value, str):
        value = re.sub(r"\s+", "", value) if name != "special_terms" else " ".join(value.split())
        if name == "special_terms" and NO_TERMS.match(value):
            value = ""
    return value


def score_photos(rows: list[dict], photo_dir: Path = ROOT / "contract_photos") -> dict:
    """사진이 있는 계약서만 agent.extract_contract로 읽어 추출 필드 5개를 정답과 비교한다."""
    fields, results = list(agent.FIELDS), []
    for r in rows:
        img = photo_dir / f"{r['id']}.jpg"
        if "photo_layout" not in r or not img.exists():
            continue
        url = "data:image/jpeg;base64," + base64.b64encode(img.read_bytes()).decode()
        got, failed = agent.extract_contract(url)
        want = {f: r["contract"].get(f, "") for f in fields}
        ok = {f: norm(f, got[f].value or "") == norm(f, want[f]) for f in fields}
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
    ap.add_argument("--plans", action="store_true", help="상황별 전략 근거를 평가한다")
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
    if args.plans:
        s = score_plans(load(args.files or [ROOT / "situations_b.jsonl"]))
        model = getattr(agent.llm, "model", type(agent.llm).__name__)
        recall = f"{s['must_recall']:.1%}" if s["must_recall"] is not None else "N/A"
        print(f"모델: {model}  N={s['n']}")
        print(f"필수 근거 재현율 {recall} ({s['must_hit']}/{s['must_n']})  "
              f"금지 근거 {s['forbid_hits']}  표 밖 근거 {s['out_of_table']}  빈 전략/대체 {s['empty']}")
        for r in s["situations"]:
            print(f"  {r['id']}: {r['rule_ids']}")
        return
    s = score(load(args.files))
    print(f"모델: {type(agent.llm).__name__}  답장 {s['n']}건")
    print(f"유형 정답률 {s['type_acc']:.1%}  제시액 정답률 {s['amount_acc']:.1%} ({s['amount_n']}건)  대체 {s['fallbacks']}건")
    print("유형별:", ", ".join(f"{t} {v}" for t, v in s["per_type"].items()))
    for m in s["misses"]:
        print(f"  틀림 {m['id']}: 정답 {m['want']} / 응답 {m['got']}")


if __name__ == "__main__":
    main()
