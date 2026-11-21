"""소비자24의 분쟁조정·피해구제·상담 사례에서 헬스·요가·필라테스 건을 찾아 원문 글을 받는다. 표준 라이브러리만 쓴다.
사용: python eval/fetch_cases.py <저장 폴더>
원문은 저장소에 넣지 않는다. 읽고 적은 요지와 출처만 eval/case_pool.jsonl에 둔다.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.consumer.go.kr"
BOARDS = {  # 게시판: (주소 앞부분, 글 번호 이름)
    "mdat": ("/user/ftc/consumer/trublmdatcase/116/selectTrublMdatCase", "trublMdatCaseSn"),  # 분쟁조정
    "rlif": ("/user/ftc/consumer/dmgerlifcase/115/selectDmgeRlifCase", "dmgeRlifCaseSn"),  # 피해구제
    "cnslt": ("/user/ftc/consumer/cnsltcase/114/selectCnsltCase", "prgnCnsltCaseSn"),  # 상담
}
WORDS = ["헬스", "휘트니스", "피트니스", "필라테스", "요가", "PT", "스포츠센터", "체육시설", "스피닝", "크로스핏", "트레이닝"]


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)"})
    for wait in (2, 10, None):  # 잠깐 끊긴 연결 때문에 목록을 처음부터 다시 받지 않게 두 번 더 해 본다
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except OSError:
            if wait is None:
                raise
            time.sleep(wait)


def text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    page = re.sub(r"(?i)<br\s*/?>|</p>|</tr>|</div>|</li>|</h\d>", "\n", page)
    page = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\r\xa0]+", " ", page)).strip()


def body(page_text: str) -> str:
    """글 본문만. 화면의 '…상세화면 입니다.'와 '목록' 사이다."""
    m = re.search(r"상세화면 입니다\.\s*(.*?)\n\s*목록\s*\n", page_text, re.S)
    return re.sub(r"\n\s+", "\n", m.group(1)).strip() if m else ""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict] = {}
    for board, (path, key) in BOARDS.items():
        for word in WORDS:
            for page in range(1, 40):
                url = f"{BASE}{path}List.do?page={page}&row=50&searchCnd=1&searchWrd={urllib.parse.quote(word)}"
                found = re.findall(rf'(?is)<a[^>]+href="[^"]*View\.do\?{key}=(\d+)[^"]*"[^>]*>(.*?)</a>', get(url))
                for sn, title in found:
                    index.setdefault(f"{board}-{sn}", {"title": text(html.unescape(title)),
                                                       "url": f"{BASE}{path}View.do?{key}={sn}"})
                time.sleep(0.3)  # 공공 누리집에 부담을 주지 않게 천천히 받는다
                if len(found) < 50:
                    break
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, row in index.items():
        f = out / f"{k}.txt"
        if not f.exists():
            found = body(text(get(row["url"])))
            if found:
                f.write_text(found, encoding="utf-8")
            else:  # 빈 파일을 남기면 다음 실행이 다시 받지 않는다
                print(f"본문을 못 찾았다: {k} {row['url']}", file=sys.stderr)
            time.sleep(0.3)
    print(f"{len(index)}건을 {out}에 받았다")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
