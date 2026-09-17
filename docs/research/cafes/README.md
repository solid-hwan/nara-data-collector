# 가입 카페 인덱스

본 폴더는 **가입을 마친 네이버 카페**의 메타·게시판 구조·게시글 분석을 카페별로 보관한다. 다음 사이클(주기적 스캔)에서 동일 폴더 패턴으로 누적 갱신한다.

| 카페 | 별칭 | clubId | 회원 | 등급 | 가입상태 | 마지막 스캔 | 분석 노트 | 원시 데이터 |
|---|---|---:|---:|---|---|---|---|---|
| 조달파워 | `jodalpower` | 29615909 | 28,208 | 가지3단계 | ✅ 가입(등업전) | 2026-05-08 | (작성 예정) | [`data/raw/naver-cafe/jodalpower/`](../../../data/raw/naver-cafe/jodalpower/) |
| 건설입찰정보동호회 | `bidmaster` | 10253580 | 16,466 | 씨앗4단계 | ✅ 가입(등업전) | 2026-05-08 | (작성 예정) | [`data/raw/naver-cafe/bidmaster/`](../../../data/raw/naver-cafe/bidmaster/) |

> 이전에는 `jodalpower/`, `bidmaster/` 빈 하위 폴더가 있었으나 분석 노트 미작성 상태로 폴더만 존재해 [2026-05-08 정리 시 삭제]. 분석 노트 작성 시 폴더 다시 생성.

## 폴더 규칙

```
docs/research/cafes/
├── README.md                  ← 본 인덱스 (가입 카페 추가 시 표 갱신)
└── {cafeAlias}/
    ├── overview.md            ← 카페 메타, 게시판 트리, 등업 정책
    ├── boards.md              ← 핵심 게시판별 최근 글 표
    └── insights.md            ← 키워드 매칭, 카페 성격, 활용 전략
```

원시 a11y 스냅샷·게시판 글 목록은 `data/raw/naver-cafe/{cafeAlias}/`에 저장 (gitignore 대상).

## 다음 사이클 진입 조건

1. 우선순위 카페(BIDLAB·건설의 모든것 등)에 추가 가입 시: 새 폴더 생성 후 본 표에 행 추가
2. 등업 완료 시: 등업 전용 게시판 추가 스캔 → boards.md 업데이트, insights.md 등업 전후 비교 추가
3. 본문 추출 단계: 키워드 매칭 글의 본문을 `data/raw/naver-cafe/{cafeAlias}/article_{id}_*.json` 형태로 보관
4. 패턴 안정화 후: SQLite `cafe`, `cafe_post`, `recruit_signal` 스키마 설계 → `data-modeler` 에이전트 위임

## 윤리·운영 정책

- 작성자 닉네임은 **이니셜 + 마스킹**(`홍길동` → `홍**`)으로만 보관. 닉네임 일치가 필요하면 articleId 사용
- 본문/댓글 수집 시 PII(연락처/이메일/사업자번호) 자동 마스킹
- 호출 간 3-5초 텀 유지, 카페당 누적 페이지뷰 ≤ 10
- 댓글/좋아요/가입 글 등 **흔적 남기는 행위 일체 금지** (읽기 전용)
