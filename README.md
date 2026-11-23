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
