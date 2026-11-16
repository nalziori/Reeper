# Graph Report - Reeper  (2026-11-16)

## Corpus Check
- 38 files · ~75,466 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .jsonl 4, .example 1)

## Summary
- 423 nodes · 795 edges · 19 communities (16 shown, 3 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 68 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2acf6e25`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- package.json
- agent.py
- App.tsx
- compilerOptions
- compilerOptions
- test_app.py
- calculate
- .oxlintrc.json
- 계약
- tsconfig.json
- run.py
- Reeper 기획안
- test_agent.py
- 환불 규칙
- OpenAILLM
- test_negotiation.py

## God Nodes (most connected - your core abstractions)
1. `calculate()` - 30 edges
2. `Case` - 26 edges
3. `Contract` - 18 edges
4. `compilerOptions` - 18 edges
5. `open_case()` - 17 edges
6. `Flow` - 16 edges
7. `apply()` - 15 edges
8. `real()` - 15 edges
9. `contract()` - 15 edges
10. `compilerOptions` - 15 edges

## Surprising Connections (you probably didn't know these)
- `아키텍처 결정` --references--> `validate()`  [INFERRED]
  docs/개발_계획.md → backend/app/agent.py
- `근거 정답 필드` --references--> `plan()`  [INFERRED]
  eval/README.md → backend/app/agent.py
- `LLM 함수 (트랙 B)` --references--> `OpenAILLM`  [INFERRED]
  docs/계약.md → backend/app/agent.py
- `에이전트 작업 규칙` --references--> `validate()`  [INFERRED]
  AGENTS.md → backend/app/agent.py
- `평가 데이터` --references--> `plan()`  [INFERRED]
  eval/README.md → backend/app/agent.py

## Import Cycles
- None detected.

## Communities (19 total, 3 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.11
Nodes (43): _agree(), apply(), log(), InvalidTransition, next_action(), date, 사건 단계 전이. 순수 함수이며 저장하지 않는다. 클라이언트가 사건을 보관하고 판단은 여기서 한다., 현재 사건에서 처리할 수 없는 이벤트. (+35 more)

### Community 1 - "package.json"
Cohesion: 0.05
Nodes (38): dependencies, @astryxdesign/core, @astryxdesign/theme-neutral, react, react-dom, @stylexjs/stylex, devDependencies, @astryxdesign/cli (+30 more)

### Community 2 - "agent.py"
Cohesion: 0.06
Nodes (50): analyze_reply(), ok(), _brief(), _counter_kind(), drafts_for(), extract_contract(), facts(), FakeLLM (+42 more)

### Community 3 - "App.tsx"
Cohesion: 0.14
Nodes (23): Action, Analysis, api, Case, CaseEvent, Claim, Contract, Refund (+15 more)

### Community 4 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+11 more)

### Community 5 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 6 - "test_app.py"
Cohesion: 0.11
Nodes (20): 에이전트 작업 규칙, Flow, parametrize, 가짜 LLM으로 키 없이 돈다. 실행: backend 폴더에서 `pytest`., API만으로 사건을 끝까지 몰아 보는 도우미., test_call_card_has_the_five_things_to_say(), test_counter_after_certified_mail_can_still_reach_1372_and_deposit(), test_counter_starts_new_wait_without_resetting_notice() (+12 more)

### Community 7 - "calculate"
Cohesion: 0.11
Nodes (32): Contract, calculate(), _calculate(), date, 환불 계산과 근거 표. 금액은 여기서만 만든다. LLM은 숫자를 만들지 않는다., 도달일이 속한 달까지 이용한 것으로 센다(개시일 기준 한 달 단위)., 중도해지 환불액. 기준은 docs/환불_규칙.md 결정표. 환불액 = max(총계약대금 - 이용분 - 부가상품 가액 - 위약금, 0) +…, _used_months() (+24 more)

### Community 8 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 9 - "계약"
Cohesion: 0.20
Nodes (9): API, 계약, 단계 (stage), 사건 (Case), 원칙, 이벤트 (Event), 정책값 (`data/policy.json`), 행동 (Action) (+1 more)

### Community 11 - "run.py"
Cohesion: 0.08
Nodes (20): argparse, collections, `main`과 어긋났을 때, 담당 밖 파일을 바꿀 때, 만들고 올리기, 브랜치 규칙, 실험 브랜치, 이름 (+12 more)

### Community 12 - "Reeper 기획안"
Cohesion: 0.07
Nodes (29): 3인 트랙 (2단계), 개발 계획, 개발 방식, 단계와 통과 조건, 목표와 범위 가드, 비용과 보안, 사용자 여정, 아키텍처 결정 (+21 more)

### Community 13 - "test_agent.py"
Cohesion: 0.12
Nodes (32): open_case(), analyze(), claim(), good_plan(), 실제 LLM 구현을 키 없이 검사한다. OpenAI 응답은 가짜로 끼운다., 20만 원을 제시받은 사건에 LLM 분석을 끼워 analyze_reply를 부른다., 환불 불가 특약이 있는 계약과 전액을 바라는 상황 설명에 LLM 전략을 끼워 plan을 부른다., OpenAILLM을 끼우고, _chat이 돌려줄 값을 정하는 함수를 준다. (+24 more)

### Community 14 - "환불 규칙"
Cohesion: 0.17
Nodes (12): 계산 범위와 근거 요약의 성격, 계산식 (2026-11-15 팀 결정), 단정하면 안 되는 것, 반론 유형과 대응 근거 (초안), 정본 원문 (verified 근거), 참고 링크, 코드에 반영할 것 (정본 대조 후), 팀 확인이 필요한 구현 (2026-11-15, C) (+4 more)

### Community 16 - "OpenAILLM"
Cohesion: 0.18
Nodes (8): _field(), OpenAILLM, 답장을 읽는다. 세 번째 값은 실제 LLM이 실패해 키워드 판단으로 대체했는지다., Chat Completions를 구조화 출력으로 부른다. 실패는 예외로 올리고, 대체는 아래 함수들이 한다., read_reply(), test_chat_sends_strict_schema_and_counts_tokens(), test_daily_limit_stops_real_calls(), ReplyType

### Community 17 - "test_negotiation.py"
Cohesion: 0.42
Nodes (8): open_case(), parametrize, step(), test_explicit_zero_offer_and_agreement_are_preserved(), test_offer_at_negotiation_boundaries(), test_omitted_limits_use_calculated_refund(), test_rejects_invalid_negotiation_limits(), fastapi_testclient

## Knowledge Gaps
- **124 isolated node(s):** `$schema`, `plugins`, `react/rules-of-hooks`, `react/only-export-components`, `name` (+119 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 197 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `계약` connect `계약` to `agent.py`, `Reeper 기획안`, `test_agent.py`?**
  _High betweenness centrality (0.285) - this node is a cross-community bridge._
- **Why does `call()` connect `계약` to `App.tsx`?**
  _High betweenness centrality (0.229) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `calculate()` (e.g. with `Contract` and `contracts.jsonl`) actually correct?**
  _`calculate()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Case` (e.g. with `analyze_reply()` and `_brief()`) actually correct?**
  _`Case` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `Contract` (e.g. with `open_case()` and `OpenRequest`) actually correct?**
  _`Contract` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `plugins`, `react/rules-of-hooks` to the rest of the system?**
  _124 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10917874396135266 - nodes in this community are weakly interconnected._