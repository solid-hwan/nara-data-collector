#!/usr/bin/env bash
# scripts/check_layout.sh
# KONEPS_sionlab 폴더 구조 / 명명 규칙 / 산출물 무결성 자동 검증.
# 모든 항목 통과 시 exit 0, 1개라도 실패 시 exit 1.
#
# 사용법:
#   bash scripts/check_layout.sh
#   bash scripts/check_layout.sh --quiet   # 실패 항목만 출력

set -u

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# 색상 (TTY 일 때만)
if [ -t 1 ]; then
  C_OK='\033[0;32m'; C_FAIL='\033[0;31m'; C_DIM='\033[0;90m'; C_END='\033[0m'
else
  C_OK=''; C_FAIL=''; C_DIM=''; C_END=''
fi

PASS=0
FAIL=0
LOG_FILE=$(mktemp)

step() {
  local n="$1" total="$2" name="$3"
  printf "[%d/%d] %-32s " "$n" "$total" "$name"
}

ok() {
  PASS=$((PASS+1))
  printf "${C_OK}OK${C_END} %s\n" "${1:-}"
}

fail() {
  FAIL=$((FAIL+1))
  printf "${C_FAIL}FAIL${C_END} %s\n" "${1:-}"
  [ -n "${2:-}" ] && echo "$2" | sed 's/^/       /'
  echo "FAIL: ${3:-step}" >> "$LOG_FILE"
}

TOTAL=8

# 1. raw 루트 평면 파일 0
step 1 $TOTAL "raw 루트 평면 파일"
n=$(ls data/raw/*.json 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then
  ok "(0)"
else
  fail "($n)" "$(ls data/raw/*.json)" "raw_flat"
fi

# 2. JSON 문법
step 2 $TOTAL "JSON 문법"
bad=$(mktemp)
while IFS= read -r f; do
  python3 -c "import json,sys; json.load(open(sys.argv[1],encoding='utf-8'))" "$f" 2>/dev/null \
    || echo "$f" >> "$bad"
done < <(find data/raw -name "*.json")
n=$(wc -l < "$bad")
total=$(find data/raw -name "*.json" | wc -l)
if [ "$n" -eq 0 ]; then
  ok "($total files)"
else
  fail "($n/$total broken)" "$(cat "$bad")" "json_syntax"
fi
rm -f "$bad"

# 3. 빈 폴더
step 3 $TOTAL "빈 폴더"
empty=$(find data docs -type d -empty 2>/dev/null)
if [ -z "$empty" ]; then
  ok "(0)"
else
  n=$(echo "$empty" | wc -l)
  fail "($n)" "$empty" "empty_dirs"
fi

# 4. archive 폴더 잔존
step 4 $TOTAL "archive 잔존"
arch=$(find data -type d -name "archive" 2>/dev/null)
if [ -z "$arch" ]; then
  ok "(0)"
else
  n=$(echo "$arch" | wc -l)
  fail "($n)" "$arch" "archive_left"
fi

# 5. .txt 잔존
step 5 $TOTAL ".txt 잔존"
txt=$(find data/raw -name "*.txt" 2>/dev/null)
if [ -z "$txt" ]; then
  ok "(0)"
else
  n=$(echo "$txt" | wc -l)
  fail "($n)" "$txt" "txt_left"
fi

# 6. 명명 패턴 (4개 폴더)
step 6 $TOTAL "명명 패턴"
NAMING_OK=1
NAMING_DETAIL=""
check_pattern() {
  local label="$1" dir="$2" regex="$3"
  if [ ! -d "$dir" ]; then
    NAMING_DETAIL+="    - $label: (폴더 없음, skip)\n"
    return
  fi
  local total match
  total=$(find "$dir" -maxdepth 1 -name "*.json" -type f | wc -l)
  match=$(find "$dir" -maxdepth 1 -name "*.json" -type f | grep -cE "$regex" || true)
  if [ "$total" -eq "$match" ]; then
    NAMING_DETAIL+="    - $label: $match/$total\n"
  else
    NAMING_OK=0
    local violators
    violators=$(find "$dir" -maxdepth 1 -name "*.json" -type f | grep -vE "$regex" || true)
    NAMING_DETAIL+="    - $label: $match/$total ${C_FAIL}FAIL${C_END}\n"
    NAMING_DETAIL+="$(echo "$violators" | sed 's/^/        /')\n"
  fi
}

check_pattern "search_successful_bids" \
  "data/raw/data-go-mcp/search_successful_bids" \
  '/(용역|물품)_w7d2026[0-9]{4}-[0-9]{4}_p[0-9]{2}_[0-9]{8}_[0-9]{6}\.json$'
check_pattern "search_successful_bids/full" \
  "data/raw/data-go-mcp/search_successful_bids/full" \
  '/(용역|물품)_w7d2026[0-9]{4}-[0-9]{4}_p[0-9]{2}_full_[0-9]{8}_[0-9]{6}\.json$'
check_pattern "search_bid_announcements" \
  "data/raw/data-go-mcp/search_bid_announcements" \
  '/1mo2026[0-9]{4}-[0-9]{4}_p[0-9]{2}_[0-9]{8}_[0-9]{6}\.json$'
check_pattern "get_bids_by_keyword" \
  "data/raw/nara-jangteo/get_bids_by_keyword" \
  '/.+_[0-9]+d_[0-9]{8}_[0-9]{6}\.json$'

if [ "$NAMING_OK" -eq 1 ]; then
  ok ""
  [ "$QUIET" -eq 0 ] && printf "$NAMING_DETAIL"
else
  fail "" "" "naming"
  printf "$NAMING_DETAIL"
fi

# 7. 필수 README + SUMMARY 존재
step 7 $TOTAL "README/SUMMARY"
REQUIRED=(
  "PROJECT_MAP.md"
  "README.md"
  ".claude/agents/README.md"
  "scripts/README.md"
  "docs/README.md"
  "docs/research/README.md"
  "docs/research/cafes/README.md"
  "data/raw/README.md"
  "data/raw/nara-jangteo/README.md"
  "data/raw/data-go-mcp/README.md"
  "data/raw/naver-cafe/README.md"
  "data/processed/README.md"
  "data/reports/README.md"
  "data/raw/nara-jangteo/get_bids_by_keyword/SUMMARY-20260508.md"
  "data/raw/nara-jangteo/recommend_bids_for_dept/SUMMARY-20260508.md"
  "data/raw/nara-jangteo/analyze_bid_detail/SUMMARY-20260508.md"
  "data/raw/data-go-mcp/search_bid_announcements/SUMMARY-20260508.md"
  "data/raw/data-go-mcp/search_successful_bids/SUMMARY-20260508.md"
  "data/raw/naver-cafe/jodalpower/SUMMARY-20260508.md"
  "data/raw/naver-cafe/bidmaster/SUMMARY-20260508.md"
)
miss=()
for f in "${REQUIRED[@]}"; do
  [ -f "$f" ] || miss+=("$f")
done
if [ "${#miss[@]}" -eq 0 ]; then
  ok "(${#REQUIRED[@]}/${#REQUIRED[@]})"
else
  fail "(${#miss[@]} missing)" "$(printf '%s\n' "${miss[@]}")" "docs_missing"
fi

# 8. processed 산출물
step 8 $TOTAL "processed 산출물"
PROCESSED=(
  "data/processed/winners_pool_full.csv"
  "data/processed/winners_match_keyword.csv"
  "data/processed/winners_pool_2w_20260425-0508.csv"
  "data/processed/winners_match_agency_2w_20260425-0508.csv"
  "data/processed/matches_phase3.csv"
  "data/processed/matches_phase3_top30.md"
  "data/processed/winner_collab_score.csv"
  "data/processed/contacts.csv"
)
miss=()
for f in "${PROCESSED[@]}"; do
  [ -f "$f" ] || miss+=("$f")
done
if [ "${#miss[@]}" -eq 0 ]; then
  ok "(${#PROCESSED[@]}/${#PROCESSED[@]})"
else
  fail "(${#miss[@]} missing)" "$(printf '%s\n' "${miss[@]}")" "processed_missing"
fi

# 종합
echo ""
if [ "$FAIL" -eq 0 ]; then
  printf "${C_OK}✅ 전체 %d개 항목 통과${C_END}\n" "$TOTAL"
  rm -f "$LOG_FILE"
  exit 0
else
  printf "${C_FAIL}❌ 실패 항목: %d / %d${C_END}\n" "$FAIL" "$TOTAL"
  rm -f "$LOG_FILE"
  exit 1
fi
