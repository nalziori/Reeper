# Graph Report - Reeper  (2026-11-15)

## Corpus Check
- 26 files · ~8,566 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .ini 1, .css 1)

## Summary
- 239 nodes · 362 edges · 16 communities (13 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4c60ccfc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- package.json
- Case
- App.tsx
- compilerOptions
- compilerOptions
- test_app.py
- devDependencies
- .oxlintrc.json
- 계약
- tsconfig.json
- Reeper 기획안
- 개발 계획
- 환불 규칙

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 18 edges
2. `Case` - 16 edges
3. `compilerOptions` - 15 edges
4. `Reeper 기획안` - 13 edges
5. `open_case()` - 11 edges
6. `validate()` - 10 edges
7. `apply()` - 10 edges
8. `calculate()` - 10 edges
9. `개발 계획` - 10 edges
10. `Contract` - 9 edges

## Surprising Connections (you probably didn't know these)
- `아키텍처 결정` --references--> `validate()`  [INFERRED]
  docs/개발_계획.md → backend/app/agent.py
- `에이전트 작업 규칙` --references--> `validate()`  [INFERRED]
  AGENTS.md → backend/app/agent.py
- `LLM 함수 (트랙 B)` --references--> `validate()`  [INFERRED]
  docs/계약.md → backend/app/agent.py
- `LLM 함수 (트랙 B)` --references--> `FakeLLM`  [INFERRED]
  docs/계약.md → backend/app/agent.py
- `이벤트 (Event)` --references--> `call()`  [INFERRED]
  docs/계약.md → frontend/src/api.ts

## Import Cycles
- None detected.

## Communities (16 total, 3 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.12
Nodes (28): _agree(), apply(), log(), date, 사건 단계 전이. 순수 함수이며 저장하지 않는다. 클라이언트가 사건을 보관하고 판단은 여기서 한다., health(), FastAPI 앱. 서버는 사건을 저장하지 않는다. 사건은 요청에 담겨 오고 응답으로 돌아간다., rules() (+20 more)

### Community 1 - "package.json"
Cohesion: 0.07
Nodes (29): dependencies, @astryxdesign/core, @astryxdesign/theme-neutral, react, react-dom, @stylexjs/stylex, name, private (+21 more)

### Community 2 - "Case"
Cohesion: 0.19
Nodes (20): drafts_for(), facts(), LLM이 맡는 일: 계약서 읽기, 답장 읽기, 말투 다듬기. 그리고 문안 양식과 검사. 지금은 FakeLLM만 있다. 실제 OpenAI 구현은…, 문안 속 금액은 계산된 금액이어야 하고, 조문은 근거 표에 있어야 한다., 지금 행동에 필요한 문안. 키는 양식 이름이다., render(), validate(), next_action() (+12 more)

### Community 3 - "App.tsx"
Cohesion: 0.18
Nodes (17): Action, api, Case, Contract, Refund, Rules, Sample, Step (+9 more)

### Community 4 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+11 more)

### Community 5 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 6 - "test_app.py"
Cohesion: 0.17
Nodes (13): open_case(), Flow, 가짜 LLM으로 키 없이 돈다. 실행: backend 폴더에서 `pytest`., API만으로 사건을 끝까지 몰아 보는 도우미., test_all_templates_render_and_pass_validation(), test_call_card_has_the_five_things_to_say(), test_happy_path_to_deposit(), test_low_offer_warns_then_agreement() (+5 more)

### Community 7 - "devDependencies"
Cohesion: 0.22
Nodes (9): devDependencies, @astryxdesign/cli, oxlint, @types/node, @types/react, @types/react-dom, typescript, vite (+1 more)

### Community 8 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 9 - "계약"
Cohesion: 0.12
Nodes (13): FakeLLM, 키 없이 개발·테스트하기 위한 가짜 구현. 키워드로만 판단한다., API, LLM 함수 (트랙 B), 계약, 단계 (stage), 사건 (Case), 원칙 (+5 more)

### Community 12 - "Reeper 기획안"
Cohesion: 0.09
Nodes (21): graphify, 에이전트 작업 규칙, Reeper 기획안, 목표, 문제 정의, 사건의 흐름, 수치 증거, 실제와 모의의 경계 (+13 more)

### Community 13 - "개발 계획"
Cohesion: 0.20
Nodes (10): 3인 트랙 (2단계), 개발 계획, 개발 방식, 단계와 통과 조건, 목표와 범위 가드, 비용과 보안, 사용자 여정, 아키텍처 결정 (+2 more)

### Community 14 - "환불 규칙"
Cohesion: 0.25
Nodes (8): 계산식 (초안, 확인 전), 단정하면 안 되는 것, 반론 유형과 대응 근거 (초안), 참고 링크, 확인 기록, 확인된 것, 확인이 필요한 것, 환불 규칙

## Knowledge Gaps
- **112 isolated node(s):** `$schema`, `plugins`, `react/rules-of-hooks`, `react/only-export-components`, `name` (+107 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 139 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `계약` connect `계약` to `Reeper 기획안`?**
  _High betweenness centrality (0.319) - this node is a cross-community bridge._
- **Why does `call()` connect `계약` to `App.tsx`?**
  _High betweenness centrality (0.277) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `Case` (e.g. with `drafts_for()` and `facts()`) actually correct?**
  _`Case` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `plugins`, `react/rules-of-hooks` to the rest of the system?**
  _112 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.07056451612903226 - nodes in this community are weakly interconnected._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._