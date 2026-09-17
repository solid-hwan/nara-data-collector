# 기여 가이드 (Contributing)

KONEPS_sionlab 에 기여해 주셔서 감사합니다. 이 문서는 이슈/PR 작성부터 검증까지의 절차를 정리합니다.

> English contributors: all docs are written in Korean first, but PRs and issues in English are welcome.

---

## 1. 기여할 수 있는 영역

| 영역 | 예시 |
|---|---|
| MCP 연동 개선 | 새 tool 래핑, 오류 처리 강화, 캐싱 |
| 문서화 | 사용 예제, 트러블슈팅 케이스, 영문 번역 |
| 자체 MCP 개선 (2단계·완료) | `src/koneps_mcp/` — 새 서비스·업무구분 추가, 적합도 룰 |
| 스키마 설계 (3단계) | `data/raw/` → SQLite DDL, 매핑표 |
| 테스트 | MCP 응답 스냅샷, 스키마 검증 스크립트 |

범위 밖(지금은 받지 않는 것): 웹/앱 UI, 자사 DB 조인.

적합도 스코어링(`src/koneps_mcp/scoring.py`)은 v0.3.0 에 포함됐다. 기본 가중치는
저자 회사 기준이므로, 다른 회사에 맞춘 값을 PR 로 보내는 대신 포크해서
`WEIGHTS`·`DIGITAL_AGENCIES` 를 고쳐 쓰세요. 룰 **구조** 개선(새 보너스 축,
매칭 방식)은 환영합니다.

---

## 2. 사전 준비

```bash
git clone https://github.com/<your-fork>/KONEPS_sionlab.git
cd KONEPS_sionlab
cp .env.example .env              # 본인 data.go.kr 키 입력
python3 -m json.tool < .mcp.json  # 문법 검증
bash -n scripts/run-mcp.sh        # shell 문법
```

Claude Code 사용자는 프로젝트 디렉토리에서 `claude` 실행 후 MCP 승인.
Claude Desktop 사용자는 `bash scripts/setup-claude-desktop.sh`.

---

## 3. 브랜치/커밋 규칙

- **브랜치 명**: `feat/<요약>`, `fix/<요약>`, `docs/<요약>`, `chore/<요약>`
- **커밋 메시지**: 한국어 권장. 영어도 허용. 이모지 접두사 금지. 예:
  - `추가: Koomook 계약 조회 tool 래핑`
  - `수정: run-mcp.sh PATH 보강으로 wsl.exe 경유 실행 지원`
  - `문서: Desktop 설정 가이드에 macOS 예시 추가`
- Conventional Commits(`feat:`, `fix:` …) 형식도 허용. 혼용 시 한국어가 우선.

---

## 4. PR 체크리스트

PR 제출 전 본인이 확인:

- [ ] `.mcp.json`/설정 JSON 문법 검증 (`python3 -m json.tool`)
- [ ] shell 스크립트 문법 검증 (`bash -n scripts/*.sh`)
- [ ] 새 환경변수는 `.env.example` 에 placeholder 추가
- [ ] 새 MCP tool 은 `docs/mcp-tools.md` 에 signature 기재
- [ ] API 키/토큰/개인 식별자가 diff 에 없음 (`git diff | grep -iE 'key=|token=|secret'`)
- [ ] `data/raw/*.json` 실제 응답은 커밋하지 않음 (예시는 `_meta` 만 유지)
- [ ] 한국어 변경은 `docs/` 아래 동일 폴더에 두기 (영문은 `docs/en/`)

PR 설명에 포함할 것:
1. 변경 요약 1~3줄
2. 검증 방법 (실행한 명령어)
3. 스크린샷/로그 (UI 변화 없으면 생략)

---

## 5. 이슈 리포트

### 버그
- 재현 절차 (번호 붙여서)
- 기대 결과 vs 실제 결과
- 환경: OS, `uvx --version`, Claude Code/Desktop 버전
- 관련 로그 스니펫 (API 키 마스킹)

### 기능 제안
- 해결하려는 문제
- 제안하는 접근
- 대안/선행 조사

---

## 6. 보안 이슈

취약점은 공개 이슈 대신 비공개 경로로 제보해 주세요. 자세한 절차는 [`SECURITY.md`](./SECURITY.md) 참조.

---

## 7. 행동 강령

본 프로젝트는 [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) (Contributor Covenant v2.1) 을 따릅니다.

---

## 8. 라이선스

기여하신 코드는 프로젝트 라이선스([MIT](./LICENSE))로 배포됩니다. PR 제출 시 해당 조건에 동의하는 것으로 간주합니다.
