# scripts/ — 데이터 가공 및 운영 스크립트

`data/raw/` 의 MCP 응답 JSON을 읽어 `data/processed/` 의 CSV/MD로 변환하거나, MCP 서버를 기동/설정한다.

---

## 카탈로그

| 파일 | 종류 | 입력 | 출력 | 목적 |
|---|---|---|---|---|
| [`run-own-mcp.sh`](run-own-mcp.sh) | shell 래퍼 | `.env` | (stdout, MCP 프로토콜) | **자체 MCP 서버**(`src/koneps_mcp/`) 기동. 물품·용역 외 전 업무구분 |
| [`run-mcp.sh`](run-mcp.sh) | shell 래퍼 | `.env`, 인수 `{nara-jangteo\|data-go-mcp}` | (stdout, MCP 프로토콜) | `.mcp.json` 가 호출하는 MCP 서버 기동 |
| [`setup-claude-desktop.sh`](setup-claude-desktop.sh) | shell 셋업 | `.env`, `docs/claude-desktop-config.template.json` | `~/.config/Claude/claude_desktop_config.json` (병합) | Claude Desktop 에서 동일 MCP 사용 |
| [`check_layout.sh`](check_layout.sh) | shell 검증 | (없음, 프로젝트 루트 상대) | exit 0/1 + 콘솔 리포트 | 폴더 구조/명명/산출물 8개 항목 자동 점검 |
| [`keyword_search.py`](keyword_search.py) | Python | `data/raw/data-go-mcp/search_successful_bids/full/*.json` + `*_w7d2026*` | `data/processed/winners_pool_full.csv`, `winners_match_keyword.csv` | 9개 키워드 카테고리(OCR/AI/ERP/CRM 등) 매칭 |
| [`winner_match.py`](winner_match.py) | Python | `data/raw/data-go-mcp/search_successful_bids/*_w7d20260425-0501_p*.json` + `*_w7d20260502-0508_p*.json` | `data/processed/winners_pool_2w_20260425-0508.csv`, `winners_match_agency_2w_20260425-0508.csv` | 2주 낙찰 풀 + 기관 매칭 |
| [`match_phase3.py`](match_phase3.py) | Python | `data/raw/**/*.json` (전체) | `data/processed/matches_phase3.csv`, `matches_phase3_top30.md` | 키워드 정규식 19개 + 부서별 점수 |
| [`winner_collab_score.py`](winner_collab_score.py) | Python | `data/raw/data-go-mcp/search_successful_bids/**/*.json` | `data/processed/winner_collab_score.csv` | 하도급/협업 가능 도메인별 스코어링 |

### 수집 스크립트 (MCP 를 stdio 로 직접 호출)

| 파일 | 호출 tool | 출력 |
|---|---|---|
| [`fetch_winners.py`](fetch_winners.py) | `search_successful_bids` | `data/raw/data-go-mcp/search_successful_bids/full/` |
| [`fetch_bids_keyword.py`](fetch_bids_keyword.py) | `get_bids_by_keyword` | `data/raw/nara-jangteo/get_bids_by_keyword/` |
| [`fetch_rfp_contacts.py`](fetch_rfp_contacts.py) | `analyze_bid_detail` | `data/raw/nara-jangteo/analyze_bid_detail/` |

응답이 100KB/페이지라 Claude 컨텍스트를 거치지 않고 디스크에 직접 쓴다.

### 그 외 가공 스크립트

`winner_match_0616.py`·`winner_collab_score_0616.py` 는 특정 주차용 포크,
`winner_bracket.py`·`bracket_enricher.py` 는 금액 구간 분할·URL 보강,
`call_calendar_auto.py` 는 요일별 콜 캘린더 생성이다.

> ⚠️ **위 Python 스크립트는 신규 클론에서 바로 실행되지 않는다.** 입력
> (`data/raw/**/*.json`)과 출력(`data/processed/`) 모두 공개 저장소에서
> 제외돼 있다. 먼저 수집 스크립트로 `data/raw/` 를 채워야 한다.

---

## 실행 방법

### MCP 기동 (수동 테스트)
```bash
bash scripts/run-mcp.sh nara-jangteo    # stdout 에 JSON-RPC 메시지가 보이면 정상
bash scripts/run-mcp.sh data-go-mcp
```
정상 운용 시 `.mcp.json` 이 자동 호출하므로 직접 실행할 일은 거의 없다.

### Claude Desktop 셋업
```bash
bash scripts/setup-claude-desktop.sh
```
`~/.config/Claude/claude_desktop_config.json` 에 본 프로젝트 MCP 서버를 병합 등록.

### Python 가공
```bash
python3 scripts/keyword_search.py
python3 scripts/winner_match.py
python3 scripts/match_phase3.py
python3 scripts/winner_collab_score.py
```
의존성: 표준 라이브러리만 사용 (json/csv/glob/re/pathlib). 가상환경 불필요.

### 폴더 무결성 검증
```bash
bash scripts/check_layout.sh           # 전체 8개 항목 점검 + 리포트
bash scripts/check_layout.sh --quiet   # 실패 항목만 출력
```
exit code 0 = 통과, 1 = 실패. CI/pre-commit hook 연동 가능. 폴더 정리 후 또는 수집 사이클 끝에 호출.

---

## 입출력 경로 (요약)

스크립트 상단 상수로 하드코딩되어 있다. 수정 시 그쪽도 갱신 필요.

| 스크립트 | 상수 |
|---|---|
| `keyword_search.py` | `RAW_GLOBS`, `OUT_FULL`, `OUT_MATCH` |
| `winner_match.py` | `RAW_GLOBS`, `OUT_FULL`, `OUT_MATCH` |
| `match_phase3.py` | `RAW_DIR`, `OUT_DIR` |
| `winner_collab_score.py` | `RAW_DIR`, `OUT` |

---

## 명명 규칙 (산출 CSV)

2026-05-08 정규화 완료. 산출물 카탈로그는 `data/processed/README.md` 에 있으나
로컬 전용이다(공개 저장소에서 제외).

---

## 관련 문서

- [`../PROJECT_MAP.md`](../PROJECT_MAP.md) — 데이터 흐름 전체도
- [`../data/raw/README.md`](../data/raw/README.md) — 입력 데이터 명세
- [`../docs/mcp-tools.md`](../docs/mcp-tools.md) — MCP tool 시그니처
