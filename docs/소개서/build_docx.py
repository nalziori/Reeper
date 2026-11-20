"""소개서.md → 소개서.docx. 같은 폴더에서 `python build_docx.py`.
마크다운을 HTML로 바꿔 워드로 저장한 뒤(md2docx_img.ps1), 그림 자리를 실제 그림으로 바꾸고 작성자 속성을 비운다."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

import markdown
from docx import Document
from docx.shared import Cm

HERE = Path(__file__).parent
SRC, OUT = HERE / "소개서.md", HERE / "소개서.docx"
CSS = ("body{font-family:'맑은 고딕';font-size:10.5pt;line-height:1.5}h1{font-size:20pt}h2{font-size:14pt;margin-top:18pt}"
       "table{border-collapse:collapse;width:100%}td,th{border:1px solid #888;padding:4pt 6pt;font-size:9.5pt;vertical-align:top}"
       "th{background:#eee}code{font-family:Consolas;background:#fff2cc}blockquote{color:#555}")

md = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", r"[[IMG:\1]]", SRC.read_text(encoding="utf-8"))
# 저장소에 적지 않는 값(팀원 이름, 심사용 주소)은 같은 폴더의 제출값.json에서 채운다. 이 파일은 .gitignore로 빠진다.
# 예: {"[이름 A]": "…", "[이름 B]": "…", "[이름 C]": "…", "[심사용 주소]": "https://…/unlock/…"}
LOCAL = HERE / "제출값.json"
if LOCAL.exists():
    for key, value in json.loads(LOCAL.read_text(encoding="utf-8")).items():
        md = md.replace(f"`{key}`", value)
else:
    print("제출값.json이 없어 이름과 심사용 주소 자리를 그대로 둔다")
html = Path(tempfile.gettempdir()) / "intro_draft.html"
html.write_text(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
                + markdown.markdown(md, extensions=["tables", "fenced_code"]) + "</body></html>", encoding="utf-8")
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "md2docx_img.ps1"),
                "-Html", str(html), "-Docx", str(OUT)], check=True)

doc = Document(OUT)
n = 0
for p in doc.paragraphs:
    m = re.match(r"\[\[IMG:(.+?)\]\]", p.text.strip())
    if m:
        for r in p.runs:
            r.text = ""
        p.add_run().add_picture(str(HERE / m.group(1)), width=Cm(15.5))
        n += 1
cp = doc.core_properties
cp.author = cp.last_modified_by = cp.title = cp.comments = ""
doc.save(OUT)
left = sum("[[IMG:" in p.text for p in Document(OUT).paragraphs)
print(f"그림 {n}장, 남은 표시 {left}개")
assert n == md.count("[[IMG:") and left == 0
