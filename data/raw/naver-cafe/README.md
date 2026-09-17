# data/raw/naver-cafe/

네이버 카페 게시판의 a11y 스냅샷 / 게시글 목록 원시 수집 결과.
**비-MCP 소스** — 브라우저 자동화(Playwright/Chrome MCP 등)로 수집.

---

## 카페별 폴더

| 폴더 | 카페 | clubId | 분석 노트 |
|---|---|---:|---|
| [`jodalpower/`](jodalpower/) | cafe.naver.com/jodalpower (조달파워) | 29615909 | [`docs/research/cafes/README.md`](../../../docs/research/cafes/README.md) |
| [`bidmaster/`](bidmaster/) | cafe.naver.com/bidmaster (건설입찰정보동호회) | 10253580 | 동상 |

---

## 명명 규칙

```
{cafeId}/main_{YYYYMMDD_HHMMSS}.json         ← 메인 페이지 a11y
{cafeId}/board_{boardId}_{YYYYMMDD_HHMMSS}.json   ← 특정 게시판 글 목록
{cafeId}/article_{articleId}_{YYYYMMDD_HHMMSS}.json   ← (예정) 본문 수집
```

---

## 윤리·운영 정책 (요약)

상세는 [`../../../docs/research/cafes/README.md`](../../../docs/research/cafes/README.md) §"윤리·운영 정책".

핵심:
- 닉네임은 **이니셜 + 마스킹** (`홍길동` → `홍**`)
- PII (연락처/이메일/사업자번호) 자동 마스킹
- 호출 간 3-5초 텀, 카페당 누적 페이지뷰 ≤ 10
- **읽기 전용** — 댓글/좋아요/가입 글 등 흔적 남기는 행위 금지

---

## gitignore

`*.json` 은 git 제외 ([`../../../.gitignore`](../../../.gitignore) 참조).

---

## 관련 문서

- [`../README.md`](../README.md) — raw 전체 규칙
- [`../../../docs/research/README.md`](../../../docs/research/README.md) — 리서치 인덱스
- [`../../../docs/research/cafes/README.md`](../../../docs/research/cafes/README.md) — 카페별 메타 표
