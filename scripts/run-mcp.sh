#!/usr/bin/env bash
# MCP 서버 실행 래퍼.
# .env 에서 API 키를 읽어 환경변수로 주입한 뒤 uvx 로 대상 MCP 서버 기동.
# 사용처: .mcp.json 의 command 로 이 스크립트를 지정.
#
# 사용법:
#   ./scripts/run-mcp.sh nara-jangteo
#   ./scripts/run-mcp.sh data-go-mcp
#
# 설계 의도:
#   - .mcp.json 에 실제 키가 박히지 않음 (git 추적/유출 리스크 제거)
#   - 키 교체는 .env 한 곳만 수정하면 됨
#   - 프로젝트 루트의 .env 를 자동 로드

set -euo pipefail

# Claude Desktop(Windows)이 wsl.exe 경유로 호출 시 non-interactive/non-login shell 이라
# ~/.bashrc·~/.profile 의 PATH 수정이 적용되지 않음. uvx 표준 설치 위치를 명시 보강.
export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[run-mcp] ERROR: ${ENV_FILE} 를 찾을 수 없습니다. .env.example 을 복사하여 생성하세요." >&2
  exit 1
fi

# .env 로드 (export 자동)
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

: "${NARA_API_KEY:?.env 에 NARA_API_KEY 가 정의되어야 합니다}"

# placeholder 감지 — .env.example 을 복사만 하고 값 미치환 시 조기 실패
if [[ "${NARA_API_KEY}" == "YOUR_DECODED_SERVICE_KEY_HERE" ]]; then
  echo "[run-mcp] ERROR: .env 의 NARA_API_KEY 가 placeholder 상태입니다. 실제 키로 치환하세요." >&2
  exit 1
fi

# .env 권한 경고 (600 권장). WSL/Linux 한정.
if [[ -r "${ENV_FILE}" ]] && command -v stat >/dev/null 2>&1; then
  PERM="$(stat -c '%a' "${ENV_FILE}" 2>/dev/null || stat -f '%A' "${ENV_FILE}" 2>/dev/null || echo "")"
  if [[ -n "${PERM}" && "${PERM}" != "600" && "${PERM}" != "400" ]]; then
    echo "[run-mcp] WARN: ${ENV_FILE} 권한이 ${PERM} 입니다. 'chmod 600 .env' 권장." >&2
  fi
fi

TARGET="${1:-}"
case "${TARGET}" in
  nara-jangteo)
    : "${NARA_PRESPEC_API_KEY:?.env 에 NARA_PRESPEC_API_KEY 가 정의되어야 합니다}"
    export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
    # mcp 2.0이 mcp.server.fastmcp 경로를 제거해 상한 고정 필요 (2026-08-01, VPS 실측)
    exec uvx --python 3.11 --from nara-mcp-server --with "mcp<2" nara-server
    ;;
  data-go-mcp)
    # Koomook 서버는 API_KEY 환경변수를 기대함
    export API_KEY="${NARA_API_KEY}"
    exec uvx --with "mcp<2" "data-go-mcp.pps-narajangteo@latest"
    ;;
  *)
    echo "[run-mcp] ERROR: 지원하지 않는 대상 '${TARGET}'. nara-jangteo 또는 data-go-mcp 를 지정하세요." >&2
    exit 2
    ;;
esac
