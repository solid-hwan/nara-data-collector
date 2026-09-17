#!/usr/bin/env bash
# 자체 MCP 서버 실행 래퍼 (src/koneps_mcp).
# 서드파티 MCP 2종과 달리 이 저장소의 코드를 직접 실행한다.
#
# 사용법: ./scripts/run-own-mcp.sh
# .mcp.json 의 command 로 지정해 Claude Code 가 자동 기동한다.

set -euo pipefail

export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

: "${NARA_API_KEY:?.env 에 NARA_API_KEY 가 정의되어야 합니다}"

if [[ "${NARA_API_KEY}" == "YOUR_DECODED_SERVICE_KEY_HERE" ]]; then
  echo "[run-own-mcp] ERROR: NARA_API_KEY 가 placeholder 상태입니다." >&2
  exit 1
fi

export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

# mcp<2 상한: mcp 2.0 이 mcp.server.fastmcp 경로를 제거했다.
exec uv run --quiet --no-project \
  --with "mcp<2" --with "pydantic>=2" \
  python -m koneps_mcp.server
