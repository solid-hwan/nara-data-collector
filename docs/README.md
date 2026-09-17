# docs/ — 사람이 읽는 문서

코드/데이터가 아닌 **사람을 위한 문서**가 있다. 운영 가이드, MCP tool 시그니처, 회사 프로필, 외부 리서치 노트.

---

## 카탈로그

| 파일/폴더 | 목적 | 누가 읽나 |
|---|---|---|
| [`mcp-tools.md`](mcp-tools.md) | 등록된 MCP tool 7개의 시그니처/제약/예제 | MCP 호출 직전 시그니처 확인 |
| [`claude-desktop-config.template.json`](claude-desktop-config.template.json) | Desktop config 템플릿 (`setup-claude-desktop.sh` 가 사용) | 자동 병합용 |
| [`sionlab-profile.md`](sionlab-profile.md) | Sion Lab 회사 프로필 (제품 라인, 보유 기술, 매칭 키워드) | 입찰 매칭 룰 작성 시 |
| [`research/`](research/) | 외부 리서치 노트 (네이버 카페 서베이 등) | 리서치 인덱스는 [`research/README.md`](research/README.md) |

> 2026-09-17: `data-portal-guide.md`·`claude-desktop-setup.md`·`images/` 를 제거했다.
> 키 발급 절차(Decoding 키 경고 포함)와 Desktop 셋업은 루트 [`README.md`](../README.md) 에
> 이미 같은 내용이 있어 이중 관리 대상이었다. 엔드포인트 마이그레이션·오류코드 판별은
> [README 트러블슈팅](../README.md#-트러블슈팅) 이 정본이다.

---

## 어떤 문서를 언제 보나

- **새 컨트리뷰터** → [`mcp-tools.md`](mcp-tools.md) + [`sionlab-profile.md`](sionlab-profile.md)
- **API 키 문제 · 엔드포인트 400** → [`../README.md#-트러블슈팅`](../README.md#-트러블슈팅)
- **Desktop 환경 셋업** → [`../README.md`](../README.md) + `scripts/setup-claude-desktop.sh`
- **카페/외부 데이터 수집 정책** → [`research/`](research/)

---

## 관련 문서

- [`../PROJECT_MAP.md`](../PROJECT_MAP.md) — 프로젝트 전체 인덱스
- [`../README.md`](../README.md) — 프로젝트 개요
- [`../CLAUDE.md`](../CLAUDE.md) — Claude Code 작업 규칙
