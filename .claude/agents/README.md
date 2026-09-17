# .claude/agents — 서브에이전트 카탈로그

이 폴더에 정의된 5개 서브에이전트는 메인 Claude(Opus)가 작업을 분해하여 위임하는 대상이다.
각 에이전트는 **MCP tool 권한이 다르다** — `mcp-operator` 만 MCP 호출 권한을 가진다.

---

## 카탈로그

| 파일 | 역할 | 모델 | MCP 권한 | 주요 참조 경로 |
|---|---|---|---|---|
| [`orchestrator.md`](orchestrator.md) | 요청 분해 → 에이전트 라우팅 (코드 작성 안 함) | 상위 모델 | ❌ | 라우팅만 |
| [`mcp-operator.md`](mcp-operator.md) | MCP tool 실제 호출, 응답 품질 점검 | 기본 모델 | ✅ 12개 (**koneps-sionlab 3** + nara 3 + data-go 4 + meta 2) | `data/raw/{source}/{tool}/`, `.env` |
| [`data-modeler.md`](data-modeler.md) | MCP 응답 JSON → 정규화 스키마 설계 | 기본 모델 | ❌ | `data/raw/` 읽기, `db/schema.sql` 산출 |
| [`verifier.md`](verifier.md) | 완료 주장 전 증거 수집 / 설정 검증 | 기본 모델 | ❌ | `.mcp.json`, `.env`, `data/raw/` |
| [`docs-writer.md`](docs-writer.md) | README/런북/스키마 문서 유지 | 기본 모델 | ❌ | `README.md`, `docs/*.md` |

> 모델 지정은 각 에이전트 파일의 frontmatter 를 따른다(환경에 따라 다름). 본 프로젝트는
> `mcp-operator` 만 MCP 권한을 가지는 **권한 분리 원칙**을 사용한다.

---

## 호출 패턴

### 직접 호출 (메인 → 에이전트)
간단한 단일 작업은 메인이 직접 `Agent` 도구로 호출:
```
Agent(subagent_type="mcp-operator", prompt="search_successful_bids 7일치 ...")
Agent(subagent_type="verifier", prompt="data/raw/ 마지막 6개 파일 _meta 검증")
```

### 오케스트레이션 (orchestrator 경유)
2개 이상 에이전트가 필요한 다단계 작업:
```
Agent(subagent_type="orchestrator", prompt="...")
  → orchestrator 가 mcp-operator + data-modeler + docs-writer 에 분배
```

### 동시성
- 서브에이전트 동시 한도: **2개** (CLAUDE.md 규약)
- 3개 이상 필요 시: 2개 먼저 + 결과 받은 후 1개 추가 (2+1 패턴)
- 동시 한도 환경변수: `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY=6` (settings.json)

---

## 변경 시 주의사항

1. **frontmatter 의 `tools:` 변경 후엔 Claude Code 재시작 필수** — 권한이 다시 로드된다.
2. `mcp-operator` 의 MCP tool 목록은 `.mcp.json` 의 등록 서버와 일치해야 한다. 새 MCP 서버 추가 시 양쪽 동시 갱신.
3. 에이전트 본문에서 참조하는 경로(예: `data/raw/`)가 실제 폴더 구조와 일치하는지 [`PROJECT_MAP.md`](../../PROJECT_MAP.md) 와 대조.

---

## 관련 문서

- [`../../CLAUDE.md`](../../CLAUDE.md) — 전체 작업 규칙
- [`../../PROJECT_MAP.md`](../../PROJECT_MAP.md) — 프로젝트 인덱스
- [`../../docs/mcp-tools.md`](../../docs/mcp-tools.md) — MCP tool 시그니처
