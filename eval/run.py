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
import math
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


RISK_LABEL = {"high": "위험", "mid": "중간", "safe": "안전"}


def risk(r: dict, kind: str, amount: int | None) -> str:
    """틀린 한 건의 위험 등급. 위에서부터 처음 걸리는 것을 쓴다(docs/어려운_답장_작업_분담.md C1).
    high: 수용이 아닌데 accept(금액 없는 accept는 예상 환불액으로 합의된다, engine.py),
          제시가 아닌데 금액을 읽음, 금액을 틀리게 읽음(수용선 경고와 반박 금액이 틀어진다)
    safe: unknown(합의·수용선 경고를 만들지 않는다. 합의는 accept와 반박 뒤 합의뿐, engine.apply)
    mid:  나머지. 유형끼리 혼동, low_offer인데 금액을 못 읽음(사용자가 금액을 넣는다)"""
    want, allowed = r["reply_type"], {r["reply_type"], *r.get("also", [])}
    if kind == "accept" and "accept" not in allowed:
        return "high"
    if amount is not None and (want != "low_offer" or amount != r["amount"]):
        return "high"
    if kind == "unknown":
        return "safe"
    return "mid"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """비율 k/n의 95% Wilson 신뢰구간."""
    if not n:
        return 0.0, 0.0
    p = k / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, mid - half), min(1.0, mid + half)


def score(rows: list[dict]) -> dict:
    """한 건씩 읽혀 유형과 제시액을 정답과 비교한다. 제시액은 정답이 low_offer인 건만 센다.
    `also`가 있으면 그 유형으로 읽어도 맞은 것으로 센다(정답을 하나로 정하기 어려운 답, note에 이유)."""
    misses, fallbacks, by_type, confusion, risks = [], 0, Counter(), Counter(), Counter()
    type_ok = amount_ok = amount_n = 0
    for r in rows:
        kind, amount, failed = agent.read_reply(r["text"])
        fallbacks += failed
        ok_t = kind == r["reply_type"] or kind in r.get("also", [])
        type_ok += ok_t
        by_type[(r["reply_type"], ok_t)] += 1
        ok_a = amount is None  # 제시가 아닌 답에 금액이 붙으면 틀림(위험)
        if r["reply_type"] == "low_offer":
            amount_n += 1
            ok_a = amount == r["amount"]
            amount_ok += ok_a
        if not (ok_t and ok_a):
            confusion[(r["reply_type"], kind)] += 1
            level = risk(r, kind, amount)
            risks[level] += 1
            misses.append({"id": r["id"], "want": [r["reply_type"], r["amount"]], "got": [kind, amount], "risk": level})
    n_miss = len(misses)
    return {"n": len(rows), "type_acc": type_ok / len(rows) if rows else 0.0,
            "type_ci": wilson(type_ok, len(rows)),
            "risk": {k: risks[k] for k in RISK_LABEL},
            "high_rate": risks["high"] / len(rows) if rows else 0.0,
            "high_ci": wilson(risks["high"], len(rows)),
            "safe_share": risks["safe"] / n_miss if n_miss else None,
            "confusion": {f"{w}->{g}": c for (w, g), c in sorted(confusion.items())},  # 틀린 건만
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


# 위약금이 그대로 빠진다는 단정. "빠집니다"는 환급액에서 공제된다는 뜻으로 본다(면제 뜻이 아님).
# 같은 문장에 유보 구절(HEDGE)이 있으면 단정으로 보지 않는다. "않"·"면제"·"확인" 같은 단어 하나로는 유보로 보지 않는다.
PENALTY_STAYS = re.compile(r"위약금\s*(?:은|이|을|도)?\s*(?:\S+\s*){0,4}?(?:그대로|공제됩니다|공제돼요|공제합니다|유지됩니다|빠집니다|빠져요|내야|내셔야|부담해야|물어야)")
HEDGE = re.compile(r"단정할 수 없|단정하기 어렵|단정하지 않|다를 수 있|달라질 수 있|않을 수 있|아닐 수 있|면제될 수 있|여지가 있|라면")
# 단정 표현 "뒤"에서 그 단정을 부정하면("공제되지 않습니다", "내야 하는 건 아닙니다") 단정이 아니다.
# 앞에 있는 부정("면제되지 않고 그대로 공제됩니다")은 보지 않는다.
NEGATED = re.compile(r"(?:지|진)\s*않|(?:건|것은?)\s*아(?:니|닙)|필요(?:가|는)?\s*없")
# 업체 사정(서비스 중단·변경·계약상 약속)을 되묻는 질문. "변경"·"이전"은 수업·강사·센터 같은 말과 함께 나올 때만 인정한다.
FAULT_QUESTION = re.compile(r"퇴사|그만두|그만뒀|그만둔|교체|휴업|폐업|문을 닫|리모델링|폐지|없어졌|없어진|중단|약속|보장|계약할 때|계약 당시"
                            r"|(?:수업|강사|트레이너|시간|시간표|프로그램)\S*\s*(?:\S+\s*){0,2}?(?:변경|바뀌|바뀐|바꿨|바꾼)"
                            r"|(?:센터|헬스장|업체|매장)\S*\s*(?:\S+\s*){0,3}?(?:이전했|이전된|이전한|옮겼|옮긴)")
CONSUMER_ASK = re.compile(r"요청하|원하|희망하")  # 소비자가 바꾸려 했는지 묻는 질문은 업체 사정 질문이 아니다


def _penalty_stays(text: str) -> bool:
    for x in re.split(r"(?<=[.?!])(?!\d)\s*|\n", text):
        m = PENALTY_STAYS.search(x)
        if m and not HEDGE.search(x) and not NEGATED.search(x[m.end():]):
            return True
    return False


def _fault_question(q: str) -> bool:
    return q.rstrip().endswith("?") and bool(FAULT_QUESTION.search(q)) and not CONSUMER_ASK.search(q)


def _texts(strategy: dict) -> list[str]:
    """앱이 사용자에게 보여 주는 조언 글 전부. 업체가 할 반론(objection)과 특약 원문(quote)은 뺀다."""
    out = [strategy.get("summary") or "", *strategy.get("cautions", []), *strategy.get("questions", [])]
    out += [g.get("why", "") for g in strategy.get("grounds", [])]
    out += [c.get("how_to_handle", "") for c in strategy.get("contract_points", [])]
    out += [o.get("response", "") for o in strategy.get("objections", [])]
    return [t for t in out if isinstance(t, str)]


def score_plans(rows: list[dict]) -> dict:
    """반환된 근거와 업체 귀책 사례의 간단한 내용 조건을 채점한다."""
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
        content_ok = None
        if r["cause"] == "business" or r["cause"].startswith("업체"):
            cautions = strategy.get("cautions", [])
            questions = strategy.get("questions", [])
            content_ok = (
                any("1372" in text for text in cautions + questions)
                or any(_fault_question(q) for q in questions)
            ) and not any(_penalty_stays(text) for text in _texts(strategy))
        results.append({"id": r["id"], "rule_ids": rule_ids, "content_ok": content_ok,
                        "must_hit": len(returned & required) if required else None,
                        "must_n": len(required),
                        "forbid_hit": len(returned & set(r["forbid_grounds"])),
                        "out_of_table": len(returned - rules.keys()), "empty": bool(empty),
                        "dropped": strategy.get("dropped", 0)})
    must_hit = sum(r["must_hit"] or 0 for r in results)
    must_n = sum(r["must_n"] for r in results)
    return {"n": len(rows), "must_hit": must_hit, "must_n": must_n,
            "must_recall": must_hit / must_n if must_n else None,
            "forbid_hits": sum(r["forbid_hit"] for r in results),
            "out_of_table": sum(r["out_of_table"] for r in results),
            "business_content_failures": sum(r["content_ok"] is False for r in results),
            "empty": sum(r["empty"] for r in results), "dropped": sum(r["dropped"] for r in results),
            "situations": results}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="실제 모델을 부른다(유료)")
    ap.add_argument("--photos", action="store_true", help="계약서 사진 추출을 평가한다(--live 필요)")
    ap.add_argument("--plans", action="store_true", help="상황별 전략 근거를 평가한다")
    ap.add_argument("files", nargs="*", help="기본: eval/replies_*.jsonl 전부")
    args = ap.parse_args(argv)
    if args.photos and args.plans:  # 정답 파일과 호출 수가 달라 한 번에 돌리지 않는다
        sys.exit("--photos와 --plans는 따로 돌린다")
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
        rows = load(args.files or [ROOT / "situations_b.jsonl"])
        if not args.live:
            print("FakeLLM은 빈 전략을 반환하므로 점수는 N/A입니다.")
            for r in rows:
                print(f"  {r['id']}: {r['situation']}")
            return
        s = score_plans(rows)
        model = getattr(agent.llm, "model", type(agent.llm).__name__)
        recall = f"{s['must_recall']:.1%}" if s["must_recall"] is not None else "N/A"
        print(f"모델: {model}  N={s['n']}")
        print(f"필수 근거 재현율 {recall} ({s['must_hit']}/{s['must_n']})  "
              f"금지 근거 {s['forbid_hits']}  표 밖 근거 {s['out_of_table']}  빈 전략/대체 {s['empty']}")
        print(f"업체 귀책 내용 검사 실패 {s['business_content_failures']}  서버 검사로 버려진 항목 {s['dropped']}")
        for r in s["situations"]:
            print(f"  {r['id']}: {r['rule_ids']}  버림 {r['dropped']}")
        return
    s = score(load(args.files))
    print(f"모델: {type(agent.llm).__name__}  답장 {s['n']}건")
    print(f"유형 정답률 {s['type_acc']:.1%}  제시액 정답률 {s['amount_acc']:.1%} ({s['amount_n']}건)  대체 {s['fallbacks']}건")
    print("유형별:", ", ".join(f"{t} {v}" for t, v in s["per_type"].items()))
    lo, hi = s["type_ci"]
    print(f"유형 정답률 95% 신뢰구간(Wilson) {lo:.1%}~{hi:.1%}")
    safe = f"{s['safe_share']:.1%}" if s["safe_share"] is not None else "N/A"
    lo, hi = s["high_ci"]
    print(f"오류 {len(s['misses'])}건: " + ", ".join(f"{RISK_LABEL[k]} {v}" for k, v in s["risk"].items())
          + f"  위험 오류율 {s['high_rate']:.1%} ({lo:.1%}~{hi:.1%})  안전하게 틀린 비율 {safe}")
    if s["confusion"]:
        print("틀린 건(정답->응답):", ", ".join(f"{k} {v}" for k, v in sorted(s["confusion"].items(), key=lambda x: -x[1])))
    for m in s["misses"]:
        print(f"  틀림 {m['id']} [{RISK_LABEL[m['risk']]}]: 정답 {m['want']} / 응답 {m['got']}")


if __name__ == "__main__":
    main()
