# 에이전트 작업 규칙

Reeper는 근거를 찾아 두고, 그대로 보내거나 말할 문장을 만들고, 환불금이 입금될 때까지 추적한다. 이 세 가지에 속하지 않는 기능은 만들지 않는다.

- 시작 전에 `README.md`, `docs/개발_계획.md`, `docs/계약.md`를 읽는다.
- 에이전트가 전화하거나, 문자를 보내거나, 통화를 듣는 기능을 만들지 않는다. 보내고 말하는 것은 사용자다.
- 금액은 `backend/app/rules.py`만 만든다. LLM이 숫자를 만들거나 사건 단계를 바꾸게 하지 않는다.
- 법령 내용이나 조문 번호를 지어내지 않는다. `data/rules.json`에 없는 근거는 문안에 넣지 않고, 확인이 필요하면 `docs/환불_규칙.md`에 남긴다.
- 문안은 `data/templates/`의 고정 양식이 기본이다. 새 양식은 `validate`를 통과해야 한다.
- 서버에 사건이나 계약 내용을 저장하거나 로그로 남기지 않는다.
- API 키, 실제 계약서, 개인정보를 저장소에 넣지 않는다. 가상 데이터만 쓴다.
- 테스트는 가짜 LLM으로 키 없이 통과해야 한다. 유료 API를 쓰는 실행은 사람에게 먼저 묻는다.
- `backend/app/models.py`를 바꾸면 `frontend/src/api.ts`와 `docs/계약.md`를 같이 고친다.
- Astryx 컴포넌트는 쓰기 전에 `npx astryx component <이름>`으로 문서를 확인한다.
- 브랜치와 PR은 `docs/브랜치_규칙.md`를 따른다. 담당 밖 파일을 바꾸면 PR 본문 맨 위에 이유를 적는다.
- 바꾼 뒤에는 `backend`에서 `pytest -q`, `frontend`에서 `npm run build`를 돌리고 결과를 PR에 적는다.
- 사건 단계 전이는 `backend/app/engine.py`에서 검증한다. 전이를 바꾸면 `backend/tests/test_app.py`에서 정상 경로, 금지된 전이, 기한 경계를 함께 확인한다. 통지 전 입금 확인으로 사건을 종결하던 오류는 `test_rejects_invalid_transition_before_processing_reply`가 잡는다.
