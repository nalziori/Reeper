# Reeper

Refund-keeper. 전화와 불편한 말을 어려워하는 청년을 위해, 헬스장·PT·필라테스 환불을 말 꺼내기부터 입금까지 챙겨 주는 AI 에이전트다.

> **근거를 다 찾아 두고, 그대로 보내거나 말할 문장을 만들어 주고, 환불금이 계좌에 들어올 때까지 추적한다.**

2026 대한민국 청년 CAREER FAIR AI 해커톤 출품작이며, 제출 마감은 2026-11-23 17:00이다.

## 현재 상태

걷는 뼈대가 동작한다. 가짜 LLM으로 접수 → 환불액 → 문자 문안·통화 준비 카드 → 기록 → 업체 반응 대응 → 합의 → 입금 확인까지 간다.

- 실제 LLM(OpenAI) 구현은 서버에 있다. 키를 넣은 실제 호출 확인, 화면 연결, 배포는 아직 없다.
- **환불 계산식은 임시다.** 고시 원문 확인 전이며 화면에도 그렇게 표시한다. [환불 규칙](docs/환불_규칙.md) 참고.

## 실행

Python 3.13 이상과 Node 22 이상이 필요하다.

```bash
# 서버
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS·Linux는 .venv/bin/python
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000 --env-file .env   # .env가 없으면 --env-file을 뺀다

# 화면 (다른 터미널)
cd frontend
npm install
npm run dev        # http://localhost:5173, /api는 8000번으로 넘어간다
```

실제 LLM은 `backend/.env.example`을 `backend/.env`로 복사해 키를 넣으면 켜진다. 없으면 가짜 LLM으로 돈다. `.env`는 저장소에 올라가지 않는다.

| 환경변수 | 기본값 | 뜻 |
|---|---|---|
| `OPENAI_API_KEY` | 없음 | 있으면 실제 LLM을 쓴다 |
| `OPENAI_MODEL` | `gpt-6-luna` | 모델명 |
| `LLM_DAILY_LIMIT` | 300 | 하루 전체 호출 상한. 넘으면 고정 양식과 키워드 판단으로 계속 간다 |
| `ALLOW_UPLOAD` | 꺼짐 | `1`이면 계약서 사진 읽기를 켠다 |

`GET /api/health`에서 쓰는 구현, 남은 호출 수, 오늘 쓴 토큰을 본다.

테스트는 키 없이 돈다.

```bash
cd backend && .venv/Scripts/python -m pytest -q
cd frontend && npm run build
```

배포 형태로 확인하려면 `npm run build` 뒤 서버만 띄우고 `http://localhost:8000`을 연다. 서버가 `frontend/dist`를 함께 내보낸다. 컨테이너는 `docker build -t reeper . && docker run -p 8000:8000 reeper`.

## 구조

```
backend/app/
  models.py   공유 계약: Contract, Refund, Case, Event, Action
  rules.py    환불 계산, 근거 표와 정책값 읽기
  engine.py   단계 전이: open_case, apply, next_action
  agent.py    LLM이 맡는 일(지금은 FakeLLM), 문안 양식 채우기와 검사
  main.py     API와 화면 서빙
backend/tests/test_app.py
frontend/src/ App.tsx(화면), api.ts(서버 계약 사본)
data/         rules.json(근거), policy.json(정책값), templates/(문안 양식), samples/(가상 계약서)
docs/         기획안, 개발 계획, 계약, 환불 규칙
```

## 설계 원칙

- **계산은 코드, 읽기는 AI, 보내고 말하는 것은 사람.** 에이전트는 전화하지 않고, 문자를 보내지 않고, 통화를 듣지 않는다.
- **서버는 사건을 저장하지 않는다.** 사건은 브라우저에만 보관하고, 서버는 받은 사건에 규칙을 적용해 돌려준다.
- **금액은 코드가 계산한다.** 문안 속 금액과 조문은 검사를 통과해야 한다.
- **근거는 `data/rules.json`에 있는 것만 쓴다.**
- **법적 판단을 확정하지 않는다.** "일반적인 기준 안내"로 표시하고 1372 소비자상담센터로 연결한다.
- **가상 데이터만 쓴다.** 실제 계약서, 개인정보, API 키를 저장소에 넣지 않는다.

## 문서

- [기획안](docs/기획안.md): 목표, 문제 정의, 사건 흐름, 안전장치, 평가 계획.
- [개발 계획](docs/개발_계획.md): 범위, 개발 방식, 단계와 통과 조건, 3인 트랙, 우선순위.
- [계약](docs/계약.md): 사건 상태, 이벤트, 행동, API. 바꾸기 전에 다른 트랙과 조율한다.
- [환불 규칙](docs/환불_규칙.md): 법적 근거 표와 확인이 필요한 항목.
- [에이전트 작업 규칙](AGENTS.md): AI 코딩 에이전트가 지킬 것.
