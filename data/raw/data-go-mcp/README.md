# data/raw/data-go-mcp/

**Koomook** 의 `data-go-mcp.pps-narajangteo` (PyPI) 가 반환한 원시 응답.
공공데이터포털(data.go.kr) 의 PPS 나라장터 OpenAPI 를 그대로 wrapping.

---

## tool 별 폴더

| tool 폴더 | 설명 | 기간 제약 | 응답 핵심 필드 |
|---|---|---|---|
| [`search_bid_announcements/`](search_bid_announcements/) | 입찰공고 검색 | 최대 1개월, 미지정 시 당일 | `bidNtceNo`, `bidNtceNm`, `dminsttNm`, `bidBeginDt`, `bidClseDt`, `presmptPrce` |
| [`search_successful_bids/`](search_successful_bids/) | 낙찰 결과 검색 (업종별) | 최대 1주일 | `bidNtceNo`, `fnlSucsfCorpNm`, `fnlSucsfAmt`, `fnlSucsfRt`, `fnlSucsfDate` |
| `search_contracts/` | 계약 정보 검색 (현재 데이터 없음, 호출 시 폴더 자동 생성) | 최대 1개월 | `cntrctNo`, `cntrctCnclsAmt`, `dminsttNm`, `cntrctnmpr` |
| `get_bid_detail/` | 공고 상세 (단건) | — | ⚠️ **업스트림 버그로 현재 미사용**. `search_bid_announcements` 로 대체 |

업종 코드 (search_successful_bids `business_type`):
- `1` = 물품, `3` = 공사, `5` = 용역

---

## 명명 규칙

상위 [`../README.md`](../README.md) 의 규칙을 따른다:
```
{extra}_{YYYYMMDD_HHMMSS}.json
```

**단일 패턴**으로 통일 (2026-05-08 정규화):

`search_successful_bids/`:
```
{업종}_w7d{YYYYMMDD-MMDD}_p{NN}_{ts}.json           ← 루트
{업종}_w7d{YYYYMMDD-MMDD}_p{NN}_full_{ts}.json      ← full/ 하위 (전체 페이지)
```
- 업종: `용역` | `물품`
- 종료 일자: MMDD 4자리 (월 경계 안전)
- 페이지: zero-pad 2자리

`search_bid_announcements/`:
```
1mo{YYYYMMDD-MMDD}_p{NN}_{ts}.json                  ← 1개월 윈도우
```

---

## 갱신 주체

`mcp-operator` 에이전트 또는 메인 Claude 의 직접 호출. 모든 응답은 `_meta` 필드 포함:
```json
{
  "_meta": {
    "source": "data-go-mcp",
    "tool": "search_successful_bids",
    "called_at": "2026-05-08T16:13:23Z",
    "params": {"business_type": 5, "start_date": "20260408", ...},
    "note": "..."
  },
  "items": [...]
}
```

---

## 관련 문서

- [`../README.md`](../README.md) — 전체 raw 명명 규칙
- [`docs/mcp-tools.md`](../../../docs/mcp-tools.md) — tool 시그니처/제약
- [`README.md`](../../../README.md) — data.go.kr 인증키 발급·트러블슈팅
