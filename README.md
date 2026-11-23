# Reeper

헬스장·PT·필라테스 계약을 중도 해지할 때, 예상 환불액 계산부터 입금 확인까지 돕는 서비스입니다.

2026 대한민국 청년 CAREER FAIR AI 해커톤 출품작입니다. [공개 데모](https://reeper-9jp2.onrender.com)

## 주요 기능

1. **환불액 계산** — 계약 정보로 예상 환불액을 계산하고, 공제 내역과 적용 근거를 보여 줍니다.
2. **해지 요청과 대응** — 문자 문안과 통화 대본을 만들고, 업체의 답변에 따라 재요청·내용증명·1372 상담을 안내합니다. 연락은 사용자가 직접 합니다.
3. **입금 추적** — 합의 금액과 입금 기한을 기록하고, 입금이 늦어지면 입금 요청 문안을 제공합니다.

진행 기록은 브라우저에 저장됩니다. 환불액은 일반적인 기준에 따른 예상액입니다. [환불 규칙](docs/환불_규칙.md)

## 로컬 실행

Python 3.13 이상과 Node.js 22 이상이 필요합니다. 저장소 루트에서 아래 두 블록을 각각 다른 터미널에서 실행합니다.

**백엔드**

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

macOS·Linux에서는 `.venv/Scripts/python`을 `.venv/bin/python`으로 바꿔 실행합니다.

**프런트엔드**

```sh
cd frontend
npm ci
npm run dev
```

PowerShell에서 `npm.ps1` 실행이 차단되면 위 명령의 `npm`을 `npm.cmd`로 바꿉니다.

브라우저에서 [http://localhost:5173](http://localhost:5173)을 엽니다. API 키 없이도 고정 문안과 키워드 판정으로 환불 절차를 체험할 수 있습니다. [AI 설정 및 배포](docs/배포.md)

## 프로젝트 문서

- [API와 사건 상태](docs/계약.md)
- [개발 계획](docs/개발_계획.md)
- [AI 평가 결과](docs/평가_결과.md)

## Credits / Licenses

「AI 해커톤 AI 활용 및 출처 표기 기준」 제5조의 형식을 따른다. AI와 팀의 역할은 [AI 활용내역](docs/제출_AI활용내역.md)에 있다.

### 오픈소스

| 이름 | 라이선스 | 링크 | 용도 |
|---|---|---|---|
| React 19 | MIT | github.com/facebook/react | 화면 |
| Vite | MIT | github.com/vitejs/vite | 화면 빌드 |
| TypeScript | Apache-2.0 | github.com/microsoft/TypeScript | 화면 |
| Tailwind CSS 4, tw-animate-css | MIT | github.com/tailwindlabs/tailwindcss | 화면 스타일 |
| shadcn/ui | MIT | github.com/shadcn-ui/ui | 화면 부품(코드를 받아 고쳐 씀) |
| Base UI | MIT | github.com/mui/base-ui | 화면 부품의 바탕 |
| class-variance-authority | Apache-2.0 | github.com/joe-bell/cva | 화면 부품 변형 |
| Heroicons | MIT | github.com/tailwindlabs/heroicons | 아이콘 |
| FastAPI, Pydantic | MIT | github.com/fastapi/fastapi, github.com/pydantic/pydantic | 서버 |
| Uvicorn, HTTPX, python-dotenv | BSD-3-Clause | github.com/encode/uvicorn, github.com/encode/httpx, github.com/theskumar/python-dotenv | 서버 실행, OpenAI 호출, 환경변수 |
| pytest, Playwright | MIT, Apache-2.0 | github.com/pytest-dev/pytest, github.com/microsoft/playwright | 테스트, 화면 흐름 점검 |
| matplotlib | Matplotlib License(PSF 기반) | github.com/matplotlib/matplotlib | 소개서 그래프(`docs/소개서/make_charts.py`) |

### 데이터

| 데이터 | 제공기관 | 라이선스·이용 조건 | 기준일 |
|---|---|---|---|
| 방문판매 등에 관한 법률, 「계속거래 등의 해지·해제에 따른 위약금 및 대금의 환급에 관한 산정기준」(공정거래위원회 고시) | 국가법령정보센터(law.go.kr) | 법령·고시는 저작권 보호 대상이 아니다(저작권법 제7조) | 2026-11-18 원문 확인 |
| 헬스·PT·필라테스 분쟁조정·피해구제·상담 사례 | 소비자24(consumer.go.kr), 한국소비자원(kca.go.kr) | 공개 사례를 요약해 쓰고 사례마다 출처 주소를 남겼다(`data/mediation_cases.json`, `eval/case_pool.jsonl`) | 2026-11-21 수집 |
| 헬스장 피해구제·상담 통계, 체육시설업 현황 | 한국소비자원 보도자료, 문화체육관광부 | 출처 표기(`docs/소개서/출처.md`) | 각 자료의 발표일 |
| 평가용 계약서·답장·상황 | 팀 제작(가상 데이터) | 저장소와 같음 | - |

### 이미지·음원·폰트

| 자료 | 제작자·출처 | 라이선스 |
|---|---|---|
| Pretendard | github.com/orioncactus/pretendard | SIL OFL 1.1 |
| Noto Sans KR | Google Fonts | SIL OFL 1.1 (소개서 PDF 글꼴, 저장소 외) |
| 맑은 고딕 | Microsoft (Windows 기본 글꼴) | 소개서 그래프 그림에만 쓰임 |
| 마스코트(딱따구리) 그림 `frontend/src/assets/mascot/` | AI 생성(ChatGPT 웹), A 트랙 | OpenAI 이용약관 |
| 시연 영상 배경음 「Afterglow Circuit」(시연 영상에만, 저장소 외) | AI 생성(OpenAI gpt-6-astra), C 트랙 | OpenAI 이용약관 |

### AI 모델·API

| 이름 | 제공 | 용도 |
|---|---|---|
| gpt-6.1-terra (Chat Completions API) | OpenAI, 이용약관 | 서비스의 답장 읽기·분석, 조언, 말투 다듬기, 계약서 사진 읽기 |
| Claude Code | Anthropic, 이용약관 | 개발(코드·테스트·문서 작성, 리뷰 초안) |
| Codex | OpenAI, 이용약관 | 개발(교차 검증) |
