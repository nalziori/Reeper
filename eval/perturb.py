"""변형 시험(CheckList식). 답장 64건(replies_* 30 + unseen_* 34)에서 정답이 정해진 변형을 만들고 채점한다.

사람이 정답을 새로 붙이지 않는다. 변형마다 정답이 어떻게 되는지 RULES에 한 줄로 적었다.
  불변: 문장을 바꿔도 유형과 금액은 그대로다.
  방향: 제시액 표기나 금액만 바꾼다. 정답 금액만 따라 바뀐다.

    python eval/perturb.py          # eval/perturbed_c.jsonl을 다시 만들고 가짜 LLM으로 채점(무료)
    python eval/perturb.py --check  # 파일이 지금 규칙으로 만든 것과 같은지만 본다
    python eval/run.py --live eval/perturbed_c.jsonl   # 실제 모델(유료, 팀에 먼저 묻는다)

통화 메모(b09처럼 "…안 받음", "…라고 함")는 업체가 한 말이 아니라서 말투 변형(인사말, 반말, 줄임말, ㅋㅋ)을 하지 않는다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import run  # noqa: E402  eval/run.py. backend 경로도 run이 넣는다
from app import agent  # noqa: E402

FILES = ["replies_b.jsonl", "replies_c.jsonl", "unseen_replies_b.jsonl", "unseen_replies_c.jsonl"]
OUT = ROOT / "perturbed_c.jsonl"

RULES = {
    "nospace": ("불변", "띄어쓰기를 모두 없애도 유형과 금액은 그대로다."),
    "typo": ("불변", "흔한 맞춤법 실수(게요→께요, 됐→됬, 돼→되, 습니다→슴니다)는 유형과 금액을 바꾸지 않는다."),
    "abbrev": ("불변", "줄임말(첫머리 네→ㅇㅇ, 맞습니다→ㅇㅋ, 안 됩니다→ㄴㄴ)은 유형과 금액을 바꾸지 않는다."),
    "banmal": ("불변", "존댓말을 반말로 바꿔도(드릴게요→줄게, 하신→한, 끝의 요 빼기) 유형과 금액은 그대로다."),
    "greet": ("불변", "앞에 인사말을 붙여도 유형과 금액은 그대로다."),
    "excuse": ("불변", "앞에 답이 늦은 사정을 붙여도 유형과 금액은 그대로다."),
    "laugh": ("불변", "끝에 ㅋㅋ를 붙여도 유형과 금액은 그대로다."),
    "emoji": ("불변", "끝에 이모티콘을 붙여도 유형과 금액은 그대로다."),
    "amount_format": ("방향", "제시액 표기만 바꾸면(400,000원 / 40만원 / 사십만 원) 유형과 금액은 그대로다."),
    "amount_change": ("방향", "제시액을 5만 원 줄이면 정답 금액도 5만 원 줄고 유형은 그대로다. 다른 금액이 함께 있는 문장(계산식, 비교)은 바꾸지 않는다."),
}
SPEECH = {"abbrev", "banmal", "greet", "excuse", "laugh", "emoji"}

TYPOS = [("게요", "께요"), ("됐", "됬"), ("돼", "되"), ("습니다", "슴니다")]
# 긴 것부터. 높임(-시-, 드리다)을 먼저 낮추고, 합쇼체를 반말로, 마지막에 해요체의 끝 요를 뺀다.
BANMAL = [
    ("말씀하신", "말한"), ("말씀드리겠습니다", "말해 줄게"), ("드릴 말씀 없습니다", "할 말 없어"),
    ("드리겠습니다", "줄게"), ("드릴게요", "줄게"), ("드립니다", "줄게"), ("드리긴", "주긴"), ("드리는", "주는"),
    ("드려야", "줘야"), ("드릴", "줄"), ("드려", "줘"),
    ("넘기시는", "넘기는"), ("하시는", "하는"), ("받으신", "받은"), ("쓰신", "쓴"), ("쓰실", "쓸"), ("하신", "한"),
    ("하시면", "하면"), ("주시면", "주면"), ("하셔야", "해야"), ("주셔야", "줘야"), ("내셔야", "내야"),
    ("오셔서", "와서"), ("이셔서", "이라서"), ("하시죠", "하자"), ("하세요", "해"), ("주세요", "줘"),
    ("하겠습니다", "할게"), ("가능합니다", "가능해"), ("불가합니다", "불가야"), ("어렵습니다", "어려워"),
    ("없습니다", "없어"), ("있습니다", "있어"), ("맞습니다", "맞아"), ("같습니다", "같아"), ("했습니다", "했어"),
    ("됐습니다", "됐어"), ("되었습니다", "됐어"), ("됩니다", "돼"), ("나옵니다", "나와"), ("들어갑니다", "들어가"),
    ("입니다", "이야"), ("합니다", "해"), ("이에요", "이야"), ("예요", "야"),
]
GREET = "안녕하세요 회원님, 문의 주셔서 감사합니다. "
EXCUSE = "요즘 문의가 많아서 답이 늦었습니다. "

DIGIT = "영일이삼사오육칠팔구"
HAN = "일이삼사오육칠팔구십백천만"
# 금액 앞이 숫자·₩·한글 수(140만원, 사백사십만 원), 숫자 안 쉼표(1,40만원), 수 뒤 띄어쓰기(사백 사십만 원)면 더 큰 수의 일부다.
# 문장 쉼표(공제,38만원)는 경계다.
BEFORE = rf"(?<![0-9₩{HAN}])(?<!\d,)(?<![0-9{HAN}]\s)"
AFTER = r"(?!\d|,\d)"  # 뒤의 쉼표는 문장 쉼표(38만원,)일 수 있다
NUM_H = "[일이삼사오육칠팔구십백천]"
MONEY = re.compile(rf"₩\s?\d[\d,]*|\d[\d,]*\s?만(?:\s?\d[\d,]*\s?천?)?\s?원|\d[\d,]*\s?원|{NUM_H}*만(?:\s?{NUM_H}+)?\s?원|{NUM_H}+\s?원")


def nospace(t):
    return re.sub(r"\s+", "", t)


def typo(t):
    for a, b in TYPOS:
        t = t.replace(a, b)
    return t


def abbrev(t):
    s = re.sub(r"^네(?=[ ,])", "ㅇㅇ", t).replace("맞습니다", "ㅇㅋ").replace("안 됩니다", "ㄴㄴ")
    return s if s != t else None


def banmal(t):
    for a, b in BANMAL:
        t = t.replace(a, b)
    return re.sub(r"(?<!필)요(?=[.,!?~\s]|$)", "", t)


TEXT_RULES = {
    "nospace": nospace, "typo": typo, "abbrev": abbrev, "banmal": banmal,
    "greet": lambda t: GREET + t, "excuse": lambda t: EXCUSE + t,
    "laugh": lambda t: t + " ㅋㅋ", "emoji": lambda t: t + " 😊",
}


def _small(n: int) -> str:
    """1~9999를 한글로. 십·백·천 앞의 일은 읽지 않는다(백 원, 천 원)."""
    out = ""
    for unit, size in (("천", 1000), ("백", 100), ("십", 10), ("", 1)):
        d, n = divmod(n, size)
        if d:
            out += ("" if d == 1 and unit else DIGIT[d]) + unit
    return out


def _parts_hangul(n: int) -> list[str]:
    a, b = divmod(n, 10000)
    return [p for p in (("" if a == 1 else _small(a)) + "만" if a else "", _small(b) if b else "") if p]


def _parts_man(n: int) -> list[list[str]]:
    """만 단위 표기의 조각. 천 단위가 아닌 나머지는 쉼표가 있는 것과 없는 것 둘 다."""
    a, b = divmod(n, 10000)
    if not b:
        return [[f"{a}만"]]
    if b % 1000 == 0:
        return [[f"{a}만", f"{b // 1000}천"]]
    return [[f"{a}만", f"{b:,}"], [f"{a}만", str(b)]]


def comma(n: int) -> str:
    return f"{n:,}원"


def man(n: int) -> str:
    return comma(n) if n < 10000 else " ".join(_parts_man(n)[0]) + "원"


def hangul(n: int) -> str:
    return " ".join(_parts_hangul(n)) + " 원"


RENDER = {"comma": comma, "man": man, "hangul": hangul}


def _spellings(parts: list[str]) -> list[str]:
    return [j.join(parts) + s + "원" for j in (" ", "") for s in ("", " ")]


def find(text: str, n: int) -> list[tuple[int, int, str]]:
    """문장에서 금액 n이 쓰인 곳 전부. [(시작, 끝, 표기 방식)], 세 표기를 다 찾는다. 더 큰 수의 일부(140만원의 40만원)는 뺀다."""
    styles = {"comma": [f"₩{n:,}", f"{n:,}원", f"{n:,} 원", f"{n}원", f"{n} 원"],
              "man": [s for p in _parts_man(n) for s in _spellings(p)] if n >= 10000 else [],
              "hangul": _spellings(_parts_hangul(n)) if 0 < n < 10 ** 8 else []}
    hits = []
    for style, words in styles.items():
        if words:
            alt = "|".join(map(re.escape, sorted(set(words), key=len, reverse=True)))
            hits += [(m.start(), m.end(), style) for m in re.finditer(rf"{BEFORE}(?:{alt}){AFTER}", text)]
    return sorted(hits)


def is_memo(r: dict) -> bool:
    return r["text"].rstrip(" .").endswith(("함", "됨", "음"))


def _make(r: dict, rule: str, text: str, amount, tag: str = "") -> dict:
    v = {"id": f"{r['id']}~{rule}{tag}", "src": r["id"], "rule": rule, "test": RULES[rule][0], "text": text,
         "reply_type": r["reply_type"], "amount": amount}
    if r.get("also"):
        v["also"] = r["also"]
    v["note"] = RULES[rule][1]
    return v


def variants(r: dict) -> list[dict]:
    out = []
    for rule, fn in TEXT_RULES.items():
        if rule in SPEECH and is_memo(r):
            continue
        t = fn(r["text"])
        if t and t != r["text"]:
            out.append(_make(r, rule, t, r["amount"]))
    g, text = r["amount"], r["text"]
    hits = find(text, g) if r["reply_type"] == "low_offer" and g else []
    if len(hits) != 1:  # 없거나, 같은 금액이 여러 곳(정가 400,000원 … 40만원)이라 제시액을 하나로 못 정한다
        return out
    s, e, style = hits[0]

    def put(word: str) -> str:
        return text[:s] + word + text[e:]

    for other in RENDER:
        if other != style:
            out.append(_make(r, "amount_format", put(RENDER[other](g)), g, f"_{other}"))
    new = g - 50000
    # 다른 금액이 함께 있으면(c03 "60만원에서 20만원 공제하고 40만원") 계산이 틀어지므로, 줄인 금액이 이미 있어도(u03) 만들지 않는다
    if new > 0 and len(MONEY.findall(text)) == 1 and not find(text, new):
        out.append(_make(r, "amount_change", put(f"₩{new:,}" if text[s] == "₩" else RENDER[style](new)), new))
    return out


def sources() -> list[dict]:
    return run.load([ROOT / f for f in FILES])


SRC = {r["id"]: r for r in sources()}


def generate(rows: list[dict]) -> list[dict]:
    return [v for r in rows for v in variants(r)]


def dump(rows: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def report(src: list[dict], var: list[dict]) -> dict:
    """규칙별, 그리고 불변·방향 전체의 C1 지표(run.score)와 원본 대비 변화.
    broken: 원본은 맞았는데 변형은 틀림 / fixed: 원본은 틀렸는데 변형은 맞음 / changed: 응답(유형, 금액)이 원본과 다름."""
    real, cache = agent.read_reply, {}

    def read(t):
        if t not in cache:
            cache[t] = real(t)
        return cache[t]

    by_id = {r["id"]: r for r in src}
    agent.read_reply = read  # run.score도 이걸 부른다. 같은 문장은 한 번만 읽는다
    try:
        base_bad = {m["id"] for m in run.score(src)["misses"]}
        groups = {}
        for v in var:
            groups.setdefault(v["rule"], []).append(v)
        for v in var:
            groups.setdefault(f"{RULES[v['rule']][0]} 전체", []).append(v)
        out = {}
        for name, grp in groups.items():
            s = run.score(grp)
            bad = {m["id"] for m in s["misses"]}
            broken = [v["id"] for v in grp if v["src"] not in base_bad and v["id"] in bad]
            out[name] = {"n": len(grp), "score": s, "broken": len(broken), "broken_ids": broken,
                         "fixed": sum(v["src"] in base_bad and v["id"] not in bad for v in grp),
                         "changed": sum(read(v["text"])[:2] != read(by_id[v["src"]]["text"])[:2] for v in grp)}
        return out
    finally:
        agent.read_reply = real


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="perturbed_c.jsonl이 지금 규칙으로 만든 것과 같은지만 본다")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    rows = sources()
    var = generate(rows)
    text = dump(var)
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            sys.exit(f"{OUT.name}이 낡았다. python eval/perturb.py로 다시 만든다")
        print(f"{OUT.name} 최신 ({len(var)}건)")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    agent.llm = agent.FAKE  # 채점은 가짜 LLM만. 실제 모델은 run.py --live로 돌린다
    base = run.score(rows)
    print(f"변형 시험(가짜 LLM, 무료): 원본 {len(rows)}건 → 변형 {len(var)}건, {OUT.name}에 저장")
    print(f"원본: 유형 {base['type_acc']:.1%}  오류 위험 {base['risk']['high']}·중간 {base['risk']['mid']}·안전 {base['risk']['safe']}")
    rep = report(rows, var)
    for name, x in rep.items():
        s, kind = x["score"], RULES[name][0] if name in RULES else name.split()[0]
        r = s["risk"]
        amt = f"  제시액 {s['amount_acc']:.1%}({s['amount_n']})" if s["amount_n"] else ""
        chg = f"  응답 바뀜 {x['changed']}" if kind == "불변" else ""
        print(f"{name:<14} {kind} {x['n']:>3}건  유형 {s['type_acc']:.1%}{amt}  위험 {r['high']}·중간 {r['mid']}·안전 {r['safe']}"
              f"  원래 맞던 것 틀림 {x['broken']}  맞게 바뀜 {x['fixed']}{chg}")
        if name in RULES:
            print(f"    {RULES[name][1]}")
    print("원래 맞던 것이 틀린 건:")
    got = {m["id"]: m for k in RULES if k in rep for m in rep[k]["score"]["misses"]}
    for k in RULES:
        for i in rep.get(k, {}).get("broken_ids", []):
            m = got[i]
            print(f"  {i} [{run.RISK_LABEL[m['risk']]}]: 정답 {m['want']} / 응답 {m['got']}")


if __name__ == "__main__":
    main()
