#!/usr/bin/env bash
# 전체 검증: 서버 테스트 → 화면 빌드·린트 → API 하니스 → 브라우저 하니스. 하나라도 실패하면 멈춘다.
# 실행: bash harness/run_all.sh   (backend/.venv와 frontend/node_modules가 있어야 한다)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=backend/.venv/bin/python
[ -x "$PY" ] || PY=python3
echo "== 1/4 서버 테스트 =="; (cd backend && ../"$PY" -m pytest -q 2>&1 | tail -3)
echo "== 2/4 화면 빌드·린트 =="; (cd frontend && npm run build 2>&1 | grep -E "error|✓ built" && npx oxlint)
echo "== 3/4 API 경로 하니스 =="; (cd harness && ../"$PY" api_paths.py)
echo "== 4/4 브라우저 하니스 =="; (cd harness && python3 ui_flow.py "${SHOTS:-/tmp/reeper-shots}")
echo "모두 통과"
