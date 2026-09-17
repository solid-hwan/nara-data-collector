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

# --python 3.11: 코드가 `X | None` (PEP 604) 문법을 쓰므로 3.10 미만에서는
#   import 시점에 TypeError 가 난다. 시스템 python 이 3.9 인 환경을 대비해 고정한다.
# mcp<2: mcp 2.0 이 mcp.server.fastmcp 경로를 제거했다. 업스트림이 상한을
#   선언하지 않아 uv 가 2.x 를 끌어오므로 여기서 막는다.
exec uv run --quiet --no-project --python 3.11 \
  --with "mcp<2" --with "pydantic>=2" \
  python -m koneps_mcp.server
