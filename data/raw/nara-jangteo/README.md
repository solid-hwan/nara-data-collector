# data/raw/nara-jangteo/

**Datajang** 의 `nara-mcp-server` (PyPI: `nara-mcp-server`) 가 반환한 원시 응답.
이 MCP 는 나라장터 화면을 직접 파싱하기 때문에 입찰공고 + 사전규격을 동시 검색한다.

---

## tool 별 폴더

| tool 폴더 | 설명 | 입력 | 응답 핵심 필드 |
|---|---|---|---|
| [`get_bids_by_keyword/`](get_bids_by_keyword/) | 키워드 검색 (최근 N일, 최대 20개) | `keyword`, `days=7` | `bid_no`, `title`, `agency`, `industry`, `posted_at`, `close_at`, `prespec_flag` |
| [`recommend_bids_for_dept/`](recommend_bids_for_dept/) | 부서 프로필 기반 추천 (최대 60개) | `keyword`, `department_profile`, `days=7` | 위 + `score`, `reasons` |
| [`analyze_bid_detail/`](analyze_bid_detail/) | 첨부 파일 텍스트 추출 (HWP/PDF/DOCX) | `file_url`, `filename`, `department_profile?` | `extracted_text`, `summary`, `keyword_hits` |

---

## 명명 규칙

상위 [`../README.md`](../README.md) 의 규칙을 따른다:
```
{extra}_{YYYYMMDD_HHMMSS}.json   ← extra 는 키워드/부서명 등
```

예: `OCR_20260508_144430.json`, `행정안전부AI_20260508_150012.json`

`analyze_bid_detail/` 만 예외적으로 `.txt` 산출물 일부 포함 (추출된 본문 원본 백업).

---

## 갱신 주체

`mcp-operator` 에이전트가 MCP tool 호출 후 직접 저장. 사람이 수동으로 추가하지 않는다.

---

## 관련 문서

- [`../README.md`](../README.md) — 전체 raw 명명 규칙
- [`../../../docs/mcp-tools.md`](../../../docs/mcp-tools.md) — tool 시그니처
- [`../../../.claude/agents/mcp-operator.md`](../../../.claude/agents/mcp-operator.md) — 호출 에이전트
