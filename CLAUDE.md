# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 목적
나라장터(KONEPS/G2B) 데이터를 **MCP(Model Context Protocol) 경유**로 조회하고, 향후 자체 비즈니스 로직(추천/매칭/스코어링)을 얹을 플랫폼의 기반.

**현재 단계** (v0.2.0, 2026-09-17): MCP 서버 3개.

- `koneps-sionlab` — **자체 구현** (`src/koneps_mcp/`). 물품·용역에 한정되지 않고
  공사·외자·기타공고·사전규격·조달요청·계약과정통합·누리장터까지 조회한다.
- `nara-jangteo`, `data-go-mcp.pps-narajangteo` — 서드파티(uvx). 유지하되
  후자는 2025-09 이후 업스트림 릴리스가 없다.

비즈니스 로직(추천·매칭·스코어링)과 UI 는 여전히 **스코프 밖**이다.

**자체 MCP 수정 시 지켜야 할 것**
- 엔드포인트 네임스페이스(`/ad/`·`/as/`·`/ao/`)는 서비스마다 다르다.
  `src/koneps_mcp/g2b.py` 의 `SERVICES` 가 정본이며 전부 실측으로 확인했다.
  "통일"하려는 리팩터는 `tests/test_g2b.py` 가 막는다.
- 담당자 연락처는 tool 응답에서 기본 제외한다(`_CONTACT_FIELDS`).
  응답에 실제로 담당자 실명·전화·이메일이 온다.
- 테스트는 API 를 호출하지 않는다. `urlopen` 을 스텁으로 바꿔 일일 한도를
  쓰지 않으므로, 새 기능에도 같은 방식을 유지한다.

## Architecture — Big Picture

```
사용자 → 메인 Claude (Opus)
         │
         ├─(직접 호출)──────────┐
         │                      ▼
         │               [MCP 프로토콜 층]
         │                      ▲
         │                      │  JSON-RPC over stdio
         ▼                      │
  [서브에이전트 층]              │
  orchestrator ─ 요청 분해       │
  ├─ mcp-operator (MCP tool 권한 보유) ─┘
  ├─ data-modeler (JSON→DDL)
  ├─ verifier (증거 수집)
  └─ docs-writer (문서 유지)
                  │
                  ▼
         [MCP 서버 프로세스]
         run-own-mcp.sh (자체)  ·  run-mcp.sh {target} (서드파티)
                  │
                  ▼  .env 로드 → 서버 기동
      ┌───────────┼───────────────┐
      ▼           ▼               ▼
 koneps-sionlab  nara-mcp-server  data-go-mcp.pps-narajangteo
 (src/koneps_mcp) (Datajang)      (Koomook)
  전 업무구분+정렬                 │
      │           │               │
      ▼           ▼               ▼
     data.go.kr 공공데이터포털 API
```

**핵심 설계 결정**:
1. **`.mcp.json` 에 API 키 0개** — 대신 `scripts/run-mcp.sh` 가 `.env` 를 로드 후 uvx 기동. 키 교체 시 `.env` 한 곳만 수정.
2. **메인 vs 서브에이전트 MCP 접근** — `mcp-operator` 만 frontmatter `tools:` 에 MCP tool 12개(자체 3 + 서드파티 7 + 메타 2) 권한. 다른 에이전트는 MCP 접근 **불가**. 대량/반복 호출은 `mcp-operator` 위임, 간단 조회는 메인이 직접.
3. **uvx on-demand** — MCP 서버 글로벌 설치 없음. 세션 기동 시 PyPI 에서 pull. 첫 호출 10~30초, 이후 캐시.
4. **프로젝트 스코프 엄격 준수** — 글로벌 `~/.claude.json` **절대 수정 금지**. `claude mcp add` 류 user-scope CLI **사용 금지**.

## 에이전트 팀 (.claude/agents/)

| 에이전트 | 역할 | MCP tool 권한 |
|---|---|---|
| `orchestrator` | 요청 분해 → 배분 (코드 작성 안 함) | ❌ |
| `mcp-operator` | MCP tool 실행, 응답 요약 | ✅ 10개 + 메타 2개 |
| `data-modeler` | MCP 응답 JSON → SQLite DDL 설계 | ❌ |
| `verifier` | 완료 주장 전 증거 수집 | ❌ |
| `docs-writer` | README/런북/ERD 유지 | ❌ |

**동시성 규칙**: 서브에이전트 최대 2개 동시. 3개+ 필요 시 2+1 패턴.

## 자주 쓰는 명령어

### 초기 설정
```bash
cp .env.example .env
# .env 에 data.go.kr 인증키(URL 디코딩된 원본) 입력
claude                    # 프로젝트 디렉토리에서 기동 → 프로젝트 MCP 승인
```

### 설정 검증
```bash
python3 -m json.tool < .mcp.json > /dev/null && echo OK   # JSON 문법
grep -c '^NARA_API_KEY=' .env                              # 키 존재
ls -la .env .mcp.json                                      # 권한 600 확인
bash -n scripts/run-mcp.sh                                 # shell 문법
```

### MCP 서버 수동 기동 테스트 (세션 독립)
```bash
bash scripts/run-mcp.sh nara-jangteo    # stdout 에 MCP 프로토콜 메시지 출력되면 정상
bash scripts/run-mcp.sh data-go-mcp
```

### uvx 캐시 관리
```bash
uvx --help                                        # 설치 확인 (필요 시 curl -LsSf https://astral.sh/uv/install.sh | sh)
uvx --refresh --python 3.11 --from nara-mcp-server nara-server --help   # 캐시 강제 갱신
```

### 증거/캐시 파일 확인
```bash
ls data/raw/*.json | wc -l                        # 수집된 원시 응답 개수
jq '._meta' data/raw/*.json                       # 호출 메타데이터 점검
```

## MCP Tool 카탈로그 (실측 기반)

**`nara-jangteo`** (3개)
- `get_bids_by_keyword(keyword, days=7)` — 일반 입찰공고 + 사전규격 동시 검색
- `recommend_bids_for_dept(keyword, department_profile, days=7)` — 부서 프로필 기반 Top 추천
- `analyze_bid_detail(file_url, filename, department_profile?)` — HWP/PDF/DOCX 텍스트 추출

**`data-go-mcp.pps-narajangteo`** (4개)
- `search_bid_announcements(start_date?, end_date?, num_of_rows=10, page_no=1)` — 최대 1개월, 미지정 시 당일
- `get_bid_detail(bid_notice_no)` — ⚠️ 업스트림 버그로 현재 실패, `search_bid_announcements` 로 대체
- `search_successful_bids(business_type, start_date?, end_date?, ...)` — 용역=5, 물품=1, 공사=3 등. 최대 1주일
- `search_contracts(start_date?, end_date?, institution_type?, institution_code?, ...)` — 최대 1개월

세부 시그니처는 `docs/mcp-tools.md` 참조.

## 데이터 보존 규칙

모든 MCP 응답은 **가공 전** `data/raw/{source}/{tool}/[full/]{extra?}_{YYYYMMDD_HHMMSS}.json` 형식으로 저장 (2단 디렉터리. `data/raw/` 루트 평면 적재는 금지 — `check_layout.sh` 가 잡는다). 파일 최상위에 `_meta` 필드(`source`, `tool`, `called_at`, `params`, `note`) 포함. 규칙은 `data/raw/README.md` 참조. `data/raw/*.json` 는 git 제외 대상.

## Rate Limit 정책

동일 쿼리를 1분 내 3회 이상 호출 금지. 반복 조회 전 `data/raw/` 최근 파일을 먼저 확인. API 키는 `data.go.kr` 기준 **일일 쿼터 공유** — 두 MCP 서버가 같은 키를 쓰므로 호출 총량 주의.

## 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| tool 미노출 (`mcp__*` 없음) | `.mcp.json` 문법 오류 또는 Claude Code 미재시작. 프로젝트 디렉토리에서 `claude` 재기동 후 MCP 승인 프롬프트 확인 |
| 401/403 응답 | `.env` 키 미입력 또는 `data.go.kr` 활용신청 승인 대기(1~2시간). 사전규격은 **별도 승인** 필요할 수 있음 |
| `uvx` hang | 네트워크 / `UV_LINK_MODE=copy` 누락 / Python 3.11 미설치. `uvx --refresh` 재시도 |
| 서브에이전트 "tool not available" | `.claude/agents/{name}.md` frontmatter `tools:` 에 MCP tool 누락. 수정 후 **Claude Code 세션 재시작 필요** |
| `API 오류: (코드: )` (Koomook `get_bid_detail`) | 업스트림 패키지 버그. `search_bid_announcements` 로 대체 조회 |

## 검증 원칙 (verification-before-completion)

"완료/수정됨/통과" 주장 **전** 반드시:
1. 명령어 실제 출력 확인 (추측 금지)
2. `verifier` 에이전트 호출 또는 직접 검증
3. 증거 파일/커밋 해시/로그 경로 제시

금지 표현: "아마 될 겁니다", "설정은 맞아 보입니다", "완료했습니다(증거 없이)".

## SQL 스킬 활용 가이드

3단계(스키마 설계) 진입 시 `data-modeler` 에이전트와 함께:
- 스키마 설계: `database-architect` 스킬
- 인덱스/튜닝: `database-optimizer` 스킬
- Postgres 이관 시: `supabase-postgres-best-practices` 스킬
- 플로우: MCP 응답 샘플 (`data/raw/`) → 필드 매핑표 (`docs/schema-mapping.md`) → SQLite DDL (`db/schema.sql`) → `sqlite3 :memory: < db/schema.sql` 검증

## 코드 스타일

- 주석/커밋 메시지: **한국어**
- 시간대: ISO-8601, DB 저장은 UTC, 조회 시 KST 변환
- 민감정보는 `.env` 외 저장 금지. `.mcp.json` 에도 키 직접 기재 금지 (래퍼 스크립트 경유)

## Out of Scope (지금은 하지 않음)

- 웹/앱 UI
- 비즈니스 추천 로직 (매칭·스코어링)
- 자사 DB 조인
- `db/schema.sql` — 아직 없다. `.claude/agents/verifier.md` 의 정적 검사 항목에
  들어 있으나 현재는 실패한다

## 개인정보 취급

나라장터 응답에는 수요기관 담당자 실명·전화·이메일이 포함된다
(`ntceInsttOfclNm`·`ntceInsttOfclTel`·`ofclNm`·`fnlSucsfCorpContactTel` 등).

- 가공 산출물(`data/processed`·`reports`·`analysis`)은 `.gitignore` 대상이다.
  공개 저장소에 올리지 않는다.
- CI 가 추적 파일의 전화번호 패턴과 영업 산출물 추적 여부를 검사한다.
- 회사 메타데이터를 인라인 하드코딩한 일회성 스크립트 3개도 제외 대상이다.

## 참고 링크

- 입찰공고 API: https://www.data.go.kr/data/15129394/openapi.do
- 낙찰정보 API: https://www.data.go.kr/data/15129397/openapi.do
- 사전규격 API: https://www.data.go.kr/data/15129437/openapi.do
- 누리장터 민간입찰 API: https://www.data.go.kr/data/15129456/openapi.do
- Datajang MCP: https://github.com/Datajang/narajangteo_mcp_server
- Koomook MCP: https://github.com/Koomook/data-go-mcp-servers
