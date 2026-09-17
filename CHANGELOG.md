# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-09-17

물품·용역 외 업무구분까지 커버리지 확장 + 엔드포인트 현행화.

### Added
- **자체 MCP 서버 `koneps-sionlab`** (`src/koneps_mcp/`) — 표준 라이브러리 구현, 읽기 전용
  - `koneps_search` — 9개 서비스 × 업무구분 전 축
  - `koneps_coverage` — 가능 조합·활용신청 번호 (API 호출 없음)
- **기타공고(Etc)** — 물품·용역·공사·외자 어디에도 잡히지 않는 별도 축
- **외자(Frgcpt)** — 입찰공고·낙찰 모두
- **사전규격** — 발주 3~6개월 전 신호
- **조달요청** — 이 서비스만 용역이 일반용역/기술용역으로 분리
- **계약과정통합공개** — 발주계획→사전규격→낙찰→계약 연결
- **누리장터 민간입찰** — 아파트관리사무소·영리법인 등 수요기관 외 주체
- 단위 테스트 20개 (`tests/test_g2b.py`, API 호출 없음) — 저장소 최초
- CI: Python 문법 검사, 단위 테스트, 개인정보 누출 게이트

### Changed
- 엔드포인트 경로 현행화. `BidPublicInfoService04` 는 HTTP 400 으로 폐기됐고
  `/ad/BidPublicInfoService` 가 현행이다. 서비스별로 `/ad/`·`/as/`·`/ao/` 가 갈린다
- 스크립트 6개의 저장소 경로 하드코딩 제거 — 다른 사용자가 클론해 실행 가능
- 담당자 연락처는 tool 응답에서 기본 제외 (`include_contacts` 로만 포함)

### Fixed
- 삭제된 문서를 가리키던 참조 13곳
- `data/processed`·`reports`·`analysis` 및 회사 메타데이터 인라인 스크립트 3개를
  `.gitignore` 에 추가 — 담당자 실명·전화·사업자등록번호가 공개 대상이었다

### Security
- 신규 클론에 개인정보 파일 0건 확인 (37파일·316KB)

## [0.1.0] — 2026-04-24

최초 공개 (Initial open-source release).

### Added
- 나라장터 MCP 2종 프로젝트 스코프 설정 (`.mcp.json`)
  - `nara-jangteo` (Datajang/nara-mcp-server) — 키워드 검색, 부서 추천, RFP 추출
  - `data-go-mcp.pps-narajangteo` (Koomook) — 입찰공고/낙찰/계약 원시 조회
- `.env` 기반 API 키 관리 래퍼 `scripts/run-mcp.sh`
  - `.mcp.json` 에 키 0개 — 단일 소스(`.env`)에서 주입
  - `wsl.exe -e bash` 경유 호출 대비 PATH 보강
- Claude Desktop 자동 설정 스크립트 `scripts/setup-claude-desktop.sh`
  - macOS / Windows / WSL 감지, 기존 설정 병합(덮어쓰기 방지), 타임스탬프 백업
  - JSON 문법 검증 내장
- 에이전트 팀 5종 (`.claude/agents/`)
  - `orchestrator`, `mcp-operator`(MCP tool 9개 권한), `data-modeler`, `verifier`, `docs-writer`
- 문서
  - `CLAUDE.md` — 아키텍처 / 설계 결정 / 운영 규칙
  - `README.md` — Quick Start, Desktop/Code 경로 분기
  - `docs/mcp-tools.md` — 실측 기반 tool 카탈로그 (signature 포함)
  - `docs/claude-desktop-setup.md` — Desktop 설치/트러블슈팅
  - `data/raw/README.md` — 응답 캐시 파일 명명 규칙 + `_meta` 스키마

### Verified
- Claude Code 서브에이전트(`mcp-operator`) → 실제 MCP 호출로 `Regular=82, Prespec=50` 수신
- Claude Desktop stdio 시뮬레이션 → `tools/list` 3개 + `tools/call` 성공 (입찰공고 119건 검색)

### Known Issues
- `data-go-mcp.pps-narajangteo.get_bid_detail` — 업스트림 버그로 실패. 우회: `search_bid_announcements` 사용
- 사전규격 API — data.go.kr 에서 별도 활용신청 필요할 수 있음 (같은 키로 1차 시도 후 403 시 신청)

---

[Unreleased]: https://github.com/kkhwan1/KONEPS_sionlab/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kkhwan1/KONEPS_sionlab/releases/tag/v0.1.0
