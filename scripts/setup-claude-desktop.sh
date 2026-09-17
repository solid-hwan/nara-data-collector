#!/usr/bin/env bash
# Claude Desktop 용 MCP 설정 자동 생성 스크립트
# 현재 프로젝트 절대 경로를 치환하여 플랫폼별 설정 파일 위치에 저장한다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE="${PROJECT_ROOT}/docs/claude-desktop-config.template.json"

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "❌ 템플릿 없음: ${TEMPLATE}" >&2
  exit 1
fi

# OS 별 Claude Desktop 설정 경로 결정
case "$(uname -s)" in
  Darwin)
    CONFIG_DIR="${HOME}/Library/Application Support/Claude"
    ;;
  Linux)
    # WSL 에서 Windows 쪽 Claude Desktop 을 대상으로 하는 경우
    if grep -qi microsoft /proc/version 2>/dev/null; then
      # 0순위: 사용자 명시 override
      WIN_USER_HOME="${WIN_USER_HOME:-}"
      if [[ -z "${WIN_USER_HOME}" ]]; then :; fi
      # 1순위: USERPROFILE 환경변수 (WSL interop 활성화 시)
      if [[ -n "${USERPROFILE:-}" ]]; then
        WIN_USER_HOME="$(wslpath "${USERPROFILE}" 2>/dev/null || true)"
      fi
      # 2순위: cmd.exe 로 질의 (interop 필요)
      if [[ -z "${WIN_USER_HOME}" ]] && command -v cmd.exe >/dev/null 2>&1; then
        WIN_RAW="$(cmd.exe /C 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r' | tail -1)"
        if [[ -n "${WIN_RAW}" ]]; then
          WIN_USER_HOME="$(wslpath "${WIN_RAW}" 2>/dev/null || true)"
        fi
      fi
      # 3순위: /mnt/c/Users 스캔 — Default 계열 제외, AppData 존재하는 것만
      if [[ -z "${WIN_USER_HOME}" || ! -d "${WIN_USER_HOME}" ]]; then
        CANDIDATES=()
        while IFS= read -r -d '' appdata; do
          user_dir="$(dirname "$(dirname "${appdata}")")"
          base="$(basename "${user_dir}")"
          case "${base}" in
            Default|"Default User"|Public|All\ Users) continue ;;
          esac
          CANDIDATES+=("${user_dir}")
        done < <(find /mnt/c/Users -mindepth 3 -maxdepth 3 -type d -name Roaming -print0 2>/dev/null)

        if [[ ${#CANDIDATES[@]} -eq 1 ]]; then
          WIN_USER_HOME="${CANDIDATES[0]}"
        elif [[ ${#CANDIDATES[@]} -gt 1 ]]; then
          echo "⚠️ 여러 Windows 사용자 후보 발견:" >&2
          printf '  - %s\n' "${CANDIDATES[@]}" >&2
          echo "환경변수로 지정: WIN_USER_HOME=/mnt/c/Users/<이름> bash $0" >&2
          exit 2
        fi
      fi
      if [[ -z "${WIN_USER_HOME}" || ! -d "${WIN_USER_HOME}" ]]; then
        echo "❌ Windows 사용자 홈을 찾지 못했습니다. WIN_USER_HOME 환경변수로 지정하세요." >&2
        exit 3
      fi
      CONFIG_DIR="${WIN_USER_HOME}/AppData/Roaming/Claude"
    else
      echo "⚠️ 순수 Linux 에는 Claude Desktop 공식 빌드가 없습니다." >&2
      echo "   설정 파일만 표준 출력으로 보여드립니다." >&2
      CONFIG_DIR=""
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*)
    CONFIG_DIR="${APPDATA}/Claude"
    ;;
  *)
    echo "❌ 지원하지 않는 OS: $(uname -s)" >&2
    exit 1
    ;;
esac

# WSL 여부에 따라 렌더 방식 분기
# - WSL + Windows Desktop 대상: wsl.exe 를 통해 bash 호출 (Windows 프로세스가 Linux 경로 실행 불가)
# - macOS/Windows 네이티브: bash 직접 호출
if grep -qi microsoft /proc/version 2>/dev/null && [[ "$(uname -s)" == "Linux" ]]; then
  OUTPUT=$(python3 - "${PROJECT_ROOT}" <<'PY'
import json, sys
root = sys.argv[1]
cfg = {
  "mcpServers": {
    # 자체 구현 서버. 물품·용역 외(공사·외자·기타공고·사전규격·
    # 조달요청·누리장터)는 이 서버만 조회할 수 있다.
    "koneps-sionlab": {
      "command": "wsl.exe",
      "args": ["-e", "bash", f"{root}/scripts/run-own-mcp.sh"]
    },
    "nara-jangteo": {
      "command": "wsl.exe",
      "args": ["-e", "bash", f"{root}/scripts/run-mcp.sh", "nara-jangteo"]
    },
    "data-go-mcp.pps-narajangteo": {
      "command": "wsl.exe",
      "args": ["-e", "bash", f"{root}/scripts/run-mcp.sh", "data-go-mcp"]
    }
  }
}
print(json.dumps(cfg, ensure_ascii=False, indent=2))
PY
)
else
  OUTPUT=$(sed "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" "${TEMPLATE}")
fi

if [[ -z "${CONFIG_DIR}" ]]; then
  echo "----- 생성된 설정 (복사해서 사용) -----"
  echo "${OUTPUT}"
  exit 0
fi

CONFIG_FILE="${CONFIG_DIR}/claude_desktop_config.json"
mkdir -p "${CONFIG_DIR}"

if [[ -f "${CONFIG_FILE}" ]]; then
  BACKUP="${CONFIG_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
  cp "${CONFIG_FILE}" "${BACKUP}"
  echo "📦 기존 설정 백업: ${BACKUP}"

  # 기본: 기존 mcpServers 에 본 프로젝트 3개 항목만 병합 (다른 서버 보존)
  TMP_MERGED="$(mktemp)"
  TMP_OW="$(mktemp)"
  python3 - "${CONFIG_FILE}" "${OUTPUT}" "${TMP_MERGED}" "${TMP_OW}" <<'PY'
import json, sys
existing = json.load(open(sys.argv[1], encoding='utf-8'))
incoming = json.loads(sys.argv[2])
existing.setdefault('mcpServers', {})
overwritten = [n for n in incoming.get('mcpServers', {}) if n in existing['mcpServers']]
for name, conf in incoming.get('mcpServers', {}).items():
    existing['mcpServers'][name] = conf
with open(sys.argv[3], 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
with open(sys.argv[4], 'w', encoding='utf-8') as f:
    f.write(','.join(overwritten))
PY
  OW="$(cat "${TMP_OW}")"
  if [[ -n "${OW}" ]]; then
    echo "⚠️ 동일 이름으로 덮어쓴 항목: ${OW}"
  fi
  MERGED="$(cat "${TMP_MERGED}")"
  rm -f "${TMP_MERGED}" "${TMP_OW}"
  printf '%s\n' "${MERGED}" > "${CONFIG_FILE}"
  echo "✅ 병합 완료: ${CONFIG_FILE}"
else
  printf '%s\n' "${OUTPUT}" > "${CONFIG_FILE}"
  echo "✅ 생성 완료: ${CONFIG_FILE}"
fi

# 최종 JSON 문법 검증
if ! python3 -m json.tool < "${CONFIG_FILE}" > /dev/null 2>&1; then
  echo "❌ 생성된 JSON 문법 오류. 백업에서 복구하세요: ${BACKUP:-없음}" >&2
  exit 5
fi

echo "   Claude Desktop 을 완전 종료 후 재시작하세요."
