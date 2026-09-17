# MCP Tool 카탈로그 (실측 기반)

**검증 시각**: 자체 서버 2026-09-17 KST / 서드파티 2026-04-24 KST.

---

## `koneps-sionlab` (자체 구현 · `src/koneps_mcp/`)

2026-09-17 stdio JSON-RPC 실행으로 확인. 읽기 전용(GET).

### 1. `koneps_search`
9개 서비스를 업무구분별로 조회한다. 서드파티 두 서버가 다루지 않는
공사·외자·기타공고·사전규격·조달요청·계약과정통합·누리장터를 포함한다.

| 인자 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `service` | enum | `bid` | bid·award·prespec·contract·lifecycle·request·private·openstd_bid·openstd_award |
| `business_type` | enum\|null | null | 물품·용역·공사·외자·기타 / request 만 일반용역·기술용역 |
| `begin` | string | — | `YYYYMMDDHHMM` (분 단위 필수) |
| `end` | string | — | `YYYYMMDDHHMM` |
| `keyword` | string\|null | null | 공고명 부분일치 (현재 페이지 클라이언트 필터) |
| `page_no` | int | 1 | 1~1000 |
| `num_of_rows` | int | 20 | 1~100 |
| `include_contacts` | bool | **false** | 담당자 실명·전화·이메일 포함 여부 |

**검증 상태** (2026-09-16 하루치, `numOfRows=1`):

| 조합 | 오퍼레이션 | totalCount |
|---|---|---|
| bid/물품 | `getBidPblancListInfoThng` | 677 |
| bid/용역 | `getBidPblancListInfoServc` | 565 |
| bid/공사 | `getBidPblancListInfoCnstwk` | 478 |
| bid/외자 | `getBidPblancListInfoFrgcpt` | 10 |
| **bid/기타** | `getBidPblancListInfoEtc` | 24 |
| award/외자 | `getScsbidListSttusFrgcpt` | 5 |
| prespec/용역 | `getPublicPrcureThngInfoServc` | 460 |
| request/기술용역 | `getPrcrmntReqInfoListTechServc` | 17 |
| private/용역 | `getPrvtBidPblancListInfoServc` | 66 |
| openstd_award | `getDataSetOpnStdScsbidInfo` | 8,661 |

잘못된 조합(예: award + 기타)은 호출 전에 차단된다 — 실측 확인.

### 2. `koneps_coverage`
서비스·업무구분 가능 조합과 `public_data_pk`(활용신청 번호)를 반환한다.
**API 를 호출하지 않으므로 일일 한도를 쓰지 않는다.**

---

## 서드파티 서버 (검증 2026-04-24)

## `nara-jangteo` (Datajang/nara-mcp-server)

### 1. `mcp__nara-jangteo__get_bids_by_keyword`
키워드로 **일반 입찰공고 + 사전규격 공고**를 동시에 조회 (용역/컨설팅/개발/SI).

| 인자 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keyword` | string | — | 공고명 검색어 (예: "AI", "플랫폼") |
| `days` | integer | 7 | 조회 기간 (일). 30/60/90 확장 가능 |

**반환**: 일반 입찰공고 리스트 + 사전규격 리스트 (공고번호, 기관명, 예산, 마감일, RFP URL 포함)
**검증 상태**: ✅ 실제 응답 확인 (일반 541건 + 사전규격 335건, 30일)

### 2. `mcp__nara-jangteo__recommend_bids_for_dept`
부서 프로필 기반 Top 5 맞춤 추천.

### 3. `mcp__nara-jangteo__analyze_bid_detail`
공고번호로 첨부 RFP(HWP/HWPX/PDF/DOCX/XLSX/ZIP) 자동 다운로드 + 텍스트 추출.

---

## `data-go-mcp.pps-narajangteo` (Koomook)

### 4. `mcp__data-go-mcp_pps-narajangteo__search_bid_announcements`
나라장터 입찰공고 정보 검색.

| 인자 | 타입 | 기본 | 비고 |
|---|---|---|---|
| `start_date` | string\|null | null=오늘 | `YYYY-MM-DD` or `YYYYMMDD` |
| `end_date` | string\|null | null=오늘 | 조회 기간 최대 1개월 |
| `num_of_rows` | int | 10 | 최대 999 |
| `page_no` | int | 1 | |

**반환 필드**(주요): `bidNtceNo`, `bidNtceNm`, `bidNtceSttusNm`, `ntceInsttNm`, `dmndInsttNm`, `asignBdgtAmt`(배정예산), `presmptPrce`(추정가), `bidClseDate`, `bidNtceUrl`
**검증 상태**: ✅ 실제 응답 확인 (812건/당일)

### 5. `mcp__data-go-mcp_pps-narajangteo__get_bid_detail`
개별 입찰공고 상세 조회.

### 6. `mcp__data-go-mcp_pps-narajangteo__search_successful_bids`
낙찰정보 검색 (낙찰자, 낙찰금액, 낙찰일).

### 7. `mcp__data-go-mcp_pps-narajangteo__search_contracts`
계약정보 검색 (계약번호, 계약금액, 계약기간).

---

## MCP 메타 tool (Claude Code 내장)
- `ListMcpResourcesTool` — 서버 리소스 목록
- `ReadMcpResourceTool` — 리소스 내용 읽기

## 응답 저장 규칙
모든 호출 결과는 `data/raw/{source}_{tool}_{extra?}_{YYYYMMDD_HHMMSS}.json` 형식으로 저장. 세부는 `data/raw/README.md` 참조.

## Rate limit 정책
동일 쿼리 1분 내 3회 이상 호출 금지. 캐시(= 최근 `data/raw/` 파일) 우선 조회 후 없을 때만 신규 호출.
