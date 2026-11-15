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
