# 평가 데이터

| 파일 | 무엇 | 담당 |
|---|---|---|
| `replies_b.jsonl`, `replies_c.jsonl` | 업체 답장과 정답 유형·제시액 | B, C |
| `contracts.jsonl` | 가상 계약서 27건과 정답 필드·금액 (`make_contracts.py`로 생성) | C |
| `situations_b.jsonl` | 상황 설명과 계약 10건. 전략(`agent.plan`) 평가용. 근거 정답은 C가 더한다 | B |

모두 가상 데이터다. 실제 계약서와 개인정보는 넣지 않는다.

## situations_b.jsonl (형식은 제안)

한 줄: `id`, `cause`, `note`(무엇을 보는 사례인지), `today`, `contract`(`backend/app/models.py`의 `Contract` 필드), `situation`(사용자가 적은 상황 설명).

- `cause`는 해지 이유가 누구 쪽인지다. `consumer`(개인 사정) 7건, `business`(업체 쪽 사유: 트레이너 퇴사, 휴업, 약속한 수업 폐지) 3건.
- `business` 사례에서는 전략이 "위약금이 그대로다"라고 말하면 안 된다. 업체 사유인지 되묻고 1372 상담을 안내해야 한다. 요청액은 서버 계산값 그대로다(계산은 소비자 사정으로 해지하는 경우만 다룬다).
- 사례마다 반드시 나와야 할 근거와 나오면 안 되는 근거는 아직 없다. C가 정답으로 더한다.
- 정답이 없는 글이라 채점은 검사에 걸려 버려진 항목 수, 표 밖 근거 수, 금액 불일치 수, 근거 정답률로 한다.

## contracts.jsonl

한 줄: `id`, `basis`, `note`, `text`(계약서 본문), `contract`(추출 정답), `usage`(사용자 입력: 회 단위 `used_count`), `notified_on`, `expected`(금액 정답).

- **지금 쓰임은 회귀 확인이다.** `backend/tests/test_contracts.py`가 `rules.calculate`와 `expected`를 비교한다. 정답은 `rules.py`를 부르지 않고 계산했지만 같은 팀 결정표를 따르므로, 일치는 법적 정확도의 증거가 아니다.
- **`basis`**
  - `kca_case`: 한국소비자원 조정 사례 금액과 대조했다(k03, 211,847원).
  - `decision_table`: `docs/환불_규칙.md` 팀 결정표를 따른다.
  - `unverified_month`: 월 단위 해석(도달일이 속한 달까지 이용). 팀 확인 전이라 정확도 수치에서 뺀다.
- **`total_paid`는 보증금 제외**(`docs/계약.md`, 고시 제5조 제2항). k26처럼 본문에 "총 납부액 650,000원(회원권 600,000원 + 보증금 50,000원)"이 있으면 정답은 `total_paid` 600,000, `security_deposit` 50,000이다. 650,000을 읽으면 오답이다.
- **추출 채점 대상**은 추출기가 읽는 필드만이다. 지금 `agent.py`의 `FIELDS`는 `gym_name`, `total_paid`, `start_date`, `end_date`, `special_terms` 5개다. `unit`, `total_count`, `addon_value`, `security_deposit`은 추출기가 읽게 되면 채점한다.
- **보고할 수 있는 수치**: 추출 필드 정답률과 (`unverified_month` 제외) 환불액 일치율. 본문은 템플릿으로 만든 문장이라 실제 계약서 난이도를 대표하지 않는다고 함께 적는다.
- `expected.per_day_loss`: 하루 늦게 도달했을 때 줄어드는 환불액(오늘 환불액 − 내일 환불액).

## 답장 유형 판정 기준 (2026-11-15, C)

유형을 늘리지 않고 지금 유형 안에서 판정한다. 유형을 늘리면 `models.py`, `api.ts`, 화면 버튼이 함께 바뀐다.

| 답장 | 유형 | 이유 |
|---|---|---|
| 금액이 있는 답(수용 표현이어도) | `low_offer` | `계약.md` 108행. 받을지는 서버가 정한다 |
| "담당자에게 전달했습니다", "본사에 확인해 봐야 합니다" | `callback` | 미루는 쪽이 업체다. 기다렸다가 기한 뒤 재요청 |
| "전화로 얘기하시죠", "서류 보내 주세요", "본사 고객센터로 문의하세요" | `visit` | 해지와 상관없는 절차·창구 요구. 해지 의사는 이미 전달했다고 답한다 |
| 적립금, 기간 연장, 홀딩, 양도 제안 | `refuse` | 현금 환불이 아니다 |
| "소비자원에 신고하세요" | `refuse` | 환불을 하지 않겠다는 뜻 |
| "요청 금액 맞고요, 다음 달 말 입금", "이미 처리했습니다" | `accept` | 수용. 입금 기한·확인은 추적 단계(시행규칙 제22조: 3영업일 넘으면 지연배상) |
| 금액 없이 위약금 비율만 주장("20%입니다") | `unknown` | 맞는 유형이 없다. 문안은 `counter_penalty` 양식을 쓰도록 B가 연결 |

## run.py

답장 정답셋으로 `agent.read_reply`의 유형·제시액 정답률을 잰다. 기본은 가짜 LLM이라 키 없이 돈다.

```
cd backend && .venv/Scripts/python ../eval/run.py          # 가짜 LLM (기준선)
cd backend && .venv/Scripts/python ../eval/run.py --live   # 실제 모델, 답장 1건에 1번 호출 (유료, 팀에 먼저 말한다)
```

- 제시액 정답률은 정답이 `low_offer`인 건만 센다.
- 가짜 LLM 수치는 키워드 판단의 기준선이다. 실제 모델 성능이 아니다.
- 계약서 추출 평가는 아직 없다. 추출기가 사진만 받는데 `contracts.jsonl`은 글이다.
