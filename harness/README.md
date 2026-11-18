# 검증 하니스

실제 LLM 키 없이(가짜 LLM) 서버와 화면을 끝까지 돌려 보는 자동 검증이다. 유료 API를 쓰지 않는다.

| 파일 | 하는 일 |
|---|---|
| `lib.py` | 키를 지운 서버를 임의 포트에 띄우고 HTTP로 부른다. 표준 라이브러리만 쓴다 |
| `api_paths.py` | 사건 경로 8개(수용, 저액 제시 후 반박, 정상가, 방문, 무응답→1372, 입금 지연, 시연 버튼 문장, 거절 입력)를 흘리고, 단계 전이가 허용된 그래프 안에 있는지 매 호출마다 확인한다 |
| `ui_flow.py` | 빌드된 화면을 headless Chrome으로 데스크톱·모바일에서 종결까지 돌린다. 소요 시간, 가로 넘침, 파일 내보내기, 깨진 저장값 복구, 콘솔 오류를 확인하고 스크린샷을 남긴다 |
| `run_all.sh` | 위 둘과 `pytest`, `npm run build`, `oxlint`를 차례로 돌린다 |

브라우저 하니스는 `playwright`(Python)와 Chrome이 필요하다. Chrome은 따로 받지 않고 깔린 것을 쓴다. 경로는 `CHROME` 환경변수로 넘기고, 없으면 `/usr/bin/google-chrome`이다.

Windows(Git Bash)에서는 `run_all.sh`가 쓰는 `python3`, `.venv/bin/python`이 없을 수 있어 `ui_flow.py`를 직접 부른다.

```
backend/.venv/Scripts/python -m pip install playwright
cd frontend && npm run build && cd ../harness
CHROME="C:/Program Files/Google/Chrome/Application/chrome.exe" ../backend/.venv/Scripts/python ui_flow.py [스크린샷 폴더]
```
