## 담당 밖 파일 변경 (브랜치 규칙)

| 파일 | 이유 |
|---|---|
| `docs/계약.md` | 버튼 `accept`+`amount`는 `low_offer`로 처리, `agreement_recorded` 금액 0 이하 거절, 요청 본문 한도(413) 명시. **세 명 모두 리뷰 필요.** 필드·경로는 바꾸지 않았다 |
| `backend/tests/` | A3 전이 보강과 413 한도를 고정하는 새 테스트 파일 2개. 기존 `test_app.py`는 그대로 |
| `harness/` (새 폴더) | 키 없이 서버와 화면을 끝까지 돌리는 검증 스크립트. 코드에서 import하지 않는다 |
| `Dockerfile`, `.dockerignore` | A9 배포 준비: 비루트 실행, HEALTHCHECK, 이미지에서 제외할 폴더 |

`backend/app/models.py`는 바꾸지 않았다.

## 무엇을 했나 (A 트랙 개발 계획 A1~A4, A6~A9)

- **A1 화면 분리**: `App.tsx` 418줄 → 88줄. `steps/`(Intake, Evidence, Prepare, Respond, Deposit), `components/`, `useCase.ts`, `format.ts`로 나눴다. 동작과 문구는 그대로다.
- **A2 버튼 경로**: 답장 유형 버튼 8개와 금액 입력. LLM 없이도 종결까지 간다.
- **A3 전이 보강** (`engine.py`): 버튼으로 `accept`+양수 `amount`가 오면 `low_offer`로 취급해 목표·최저 수용선 비교를 거친다. 음수 금액과 `accept`+0원, `agreement_recorded`+0 이하는 409.
- **A4 LLM 결과 표시**: `llm_fallback` 경고, `analysis` 카드(표시 전용), 자동 읽기를 쓸 수 없을 때 안내.
- **A6**: 남은 날과 기한 한 줄, 타임라인 예정 항목. "서비스가 정한 기준, 법정 기한 아님"을 함께 적었다.
- **A7**: 사건 요약(.txt)·보관용(.json) 내보내기와 복사. 서버를 거치지 않는다.
- **A8**: 시연 패널을 단계별로 정리(엔진이 거절할 버튼은 숨김)하고, "실제로 되는 것과 시연용인 것" 카드를 넣었다.
- **A9**: 요청 본문 256KB 한도(`MAX_BODY_BYTES`, 413), Dockerfile 정리, `docs/배포.md`.
- 저장값 보호: 깨진 `localStorage`, 모양이 틀린 사건, 렌더링 예외에 흰 화면이 나지 않도록 검증과 에러 경계를 넣었다.

계획서: A 트랙 상세 개발 계획 (docs 문서). A5(계약 확인)는 계산식 원문 확인(0단계) 뒤로 미뤘다.

## 확인한 것

| 확인 | 결과 |
|---|---|
| `cd backend && pytest -q` | 162개 전체 통과 (main 병합 후, CI와 같은 범위) |
| `cd frontend && npm run build` | 성공 |
| `npx oxlint` | 경고 0 |
| `bash harness/run_all.sh` | API 하니스 8/8, 브라우저 하니스 포함 전체 47/47 통과 |
| 독립 검토 | 결함 5건(저장값 검증이 얕음 등)을 찾아 모두 고쳤다 |

하니스는 가짜 LLM으로 돈다. 데스크톱(1280px)과 모바일(390px)에서 샘플 사건이 종결까지 1~2초에 가고, 가로 넘침과 콘솔 오류가 없다.

## 확인하지 못한 것

- 실제 LLM(OpenAI) 경로: 유료 호출이라 AGENTS.md에 따라 돌리지 않았다. `analysis` 카드는 화면에서 한 번도 뜬 적이 없다.
- Docker 이미지 빌드와 컨테이너 실행. 배포처도 미정이다.
- Windows에서 `harness/ui_flow.py`: Chrome 경로가 Linux(`/usr/bin/google-chrome`) 기준이다.
- 다른 브랜치(`feature/journey-screens`, `fix/case-transitions` 등)의 변경과 겹치는지는 보지 못했다. `engine.py`, `App.tsx`, `계약.md`에서 충돌이 날 수 있다.

## B 트랙 리뷰 반영

1. **0원 합의는 막는 쪽으로 정했다.** `test_negotiation.py`의 테스트를 "0원 제시액은 보존, 0원 합의는 409"로 바꿨다. `docs/계약.md`에 0원 제시액은 그대로 기록하지만 합의 금액은 0원보다 커야 한다고 적었다. 화면의 "○원에 합의했어요" 버튼은 제시액이 0원보다 클 때만 보인다.
2. 버튼 경로에서 `accept`+금액이 `low_offer`로 바뀌면 타임라인에도 바뀐 유형을 적는다(`last_reply`와 일치).
3. 대체 경고와 분석 카드를 `ReplyReading`으로 옮겨 단계와 상관없이 보인다. 답장이 `waiting`이나 `agreed`로 가도 뜨며, 버튼으로 고칠 수 없는 단계에서는 "지금 단계가 업체 답장과 맞는지 확인"으로 안내한다.
4. 사진 경로(4MB 이상 원본)는 이 PR 범위 밖이다. 만들 때 화면에서 줄여 보내고 경로별 한도를 따로 두겠다.
5. main을 합쳤다(#38 포함).
- Dockerfile HEALTHCHECK의 겹친 따옴표를 `%` 서식으로 바꿨다. Docker 빌드는 여전히 돌리지 않았다.

## 리뷰 부탁

- 한 PR에 여러 작업이 들어 있다(규칙상 쪼개는 것이 맞다). 의존이 있어 한 번에 올렸으니, 쪼개길 원하면 A1(화면 분리)과 A3(엔진)부터 나누겠다.
- 미룬 제안: 입금 요청 문안을 보냈다는 기록 이벤트(`deposit_requested`)는 계약 변경이라 구현하지 않았다.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01VWSMFDFx1t6FjjqGmKFoSm
