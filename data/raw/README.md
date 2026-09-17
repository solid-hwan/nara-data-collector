# data/raw

MCP 서버가 반환한 **원시 JSON 응답**을 가공 없이 그대로 보관한다. 스키마 리버스, 재현, 디버깅의 단일 진실 원본.

## 폴더 구조 (source / 2단계)

원시 응답은 평면 적재 금지. 다음 2단계 디렉토리 구조에 저장한다:

```
data/raw/
├── nara-jangteo/                  # MCP source — tool별 분리
│   ├── get_bids_by_keyword/
│   ├── recommend_bids_for_dept/
│   └── analyze_bid_detail/
├── data-go-mcp/                   # MCP source — tool별 분리
│   ├── search_bid_announcements/
│   ├── search_successful_bids/
│   ├── search_contracts/
│   └── get_bid_detail/            # ⚠️ 업스트림 버그로 현재 미사용
└── naver-cafe/                    # 비-MCP source — 카페별 분리
    ├── jodalpower/                # cafe.naver.com/jodalpower
    └── bidmaster/                 # cafe.naver.com/bidmaster
```

- **MCP source** (`nara-jangteo`, `data-go-mcp`): 2단계는 tool 명
- **비-MCP source** (`naver-cafe` 등 브라우저 자동화 수집): 2단계는 의미적 그룹(카페 ID, 사이트 ID 등)

새 MCP 서버/tool/카페가 추가되면 동일 패턴으로 디렉토리만 생성하고 위 표를 업데이트.

## 파일 명명 규칙

폴더가 source/tool을 표현하므로 **파일명에는 source/tool을 반복하지 않는다**:

```
data/raw/{source}/{tool}/{extra?}_{YYYYMMDD_HHMMSS}.json
```

| 토큰 | 의미 | 예시 |
|---|---|---|
| `source` | 폴더 1단계 — MCP 서버 식별자 | `nara-jangteo`, `data-go-mcp` |
| `tool` | 폴더 2단계 — tool 명 (`mcp__` 접두사 제거) | `get_bids_by_keyword`, `search_bid_announcements` |
| `extra` | 주요 파라미터 요약 (선택). 키워드 / 기관 / 공고번호 / 업종+기간 등 | `AI_14d`, `용역_20260424-30`, `R26BK01419485` |
| `YYYYMMDD_HHMMSS` | 호출 시각 (KST) | `20260508_144405` |

### 예시 (현행)
```
data/raw/nara-jangteo/get_bids_by_keyword/AI_14d_20260508_144405.json
data/raw/nara-jangteo/analyze_bid_detail/R26BK01419485_20260424_134535.json
data/raw/data-go-mcp/search_successful_bids/용역_20260424-30_20260508_144440.json
data/raw/data-go-mcp/search_bid_announcements/all_p1_20260508_144513.json
data/raw/naver-cafe/jodalpower/main_20260508_150219.json
data/raw/naver-cafe/bidmaster/board_5_20260508_150330.json
```

### naver-cafe 전용 명명 보충

| 파일 종류 | 패턴 | extra |
|---|---|---|
| 카페 메인 | `main_{ts}.json` | — |
| 게시판 글 목록 | `board_{menuid}_{ts}.json` | menuid는 네이버 카페 게시판 식별자 (예: 5=공동도급 요청) |
| 단일 글 본문 | `article_{articleId}_{ts}.json` | (다음 사이클부터) |

## 파일 스키마 규약
각 파일의 최상위에 `_meta` 필드를 둔다:

```json
{
  "_meta": {
    "source": "nara-jangteo",
    "tool": "get_bids_by_keyword",
    "called_at": "2026-04-24T13:41:21+09:00",
    "params": {"keyword": "AI", "days": 30},
    "note": "..."
  },
  "result": { /* MCP 원시 응답 */ }
}
```

## 금지
- 수정/가공된 데이터 저장 금지 (별도 `data/processed/` 사용)
- 같은 호출 결과 중복 저장 금지 (timestamp 로 자연스럽게 구분되지만 의도적 덮어쓰기 X)
- Git 커밋 금지 — 대용량/변동성. `data/raw/**/*.json` 이 `.gitignore` 대상이다(이 README 등 문서는 추적)
- **`data/raw/` 루트에 평면 적재 금지** — 반드시 `{source}/{tool}/` 하위에. 위반 발견 시 `mv` 로 즉시 재배치 (2026-05-08 1회 정리됨)

## 위반 발견 시
1. `ls data/raw/*.json` 결과가 0이어야 정상
2. 위반 파일 발견 시 `mv` 로 올바른 `{source}/{tool}/` 폴더로 이동
3. 파일명에 `data-go-mcp_search_successful_bids_` 같은 source/tool prefix가 남아있다면, 폴더 위치만 정리하고 rename 은 별도 단계 (스크립트 영향도 검토 필요)

## 하위 폴더별 README
- [`nara-jangteo/README.md`](nara-jangteo/README.md) — 3 tool 응답 스키마
- [`data-go-mcp/README.md`](data-go-mcp/README.md) — 4 tool 응답 스키마, 명명 일관성 안내
- [`naver-cafe/README.md`](naver-cafe/README.md) — 카페 수집 정책
