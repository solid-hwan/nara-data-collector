# PROJECT_MAP

> **이 프로젝트가 처음이신가요?** 이 파일을 먼저 읽으세요. 폴더 트리 + 데이터 흐름 + 진입점 한 장 요약입니다.

---

## 한 줄 요약

나라장터(KONEPS/G2B) 데이터를 **MCP**로 수집(`data/raw/`) → 파이썬으로 가공(`data/processed/`) → 영업 리포트(`data/reports/`) 로 변환하는 파이프라인.

---

## 폴더 트리 (요약)

```
KONEPS_sionlab/
├── README.md                     프로젝트 개요 / 셋업 / 사용법
├── CLAUDE.md                     Claude Code 작업 규칙 (시스템 프롬프트)
├── PROJECT_MAP.md                ← 지금 이 파일
│
├── .claude/agents/               서브에이전트 5개 (README 참조)
├── scripts/                      파이썬 4 + 셸 2 (README 참조)
├── docs/                         사람이 읽는 문서 (README 참조)
│
├── data/
│   ├── raw/                      MCP 원시 응답 (가공 전, JSON)
│   ├── processed/                스크립트 산출 CSV/MD
│   └── reports/                  사람이 읽는 영업 리포트
│
├── .mcp.json                     MCP 서버 등록 (키 0개)
├── .env                          API 키 (gitignore, 600 권한)
└── scripts/run-mcp.sh            MCP 기동 래퍼
```

세부는 각 폴더의 `README.md` 참조.

---

## 데이터 흐름

```
┌──────────────────────┐
│ data.go.kr 공공데이터 │
└──────────┬───────────┘
           │
           ▼
   ┌───────────────┐         ┌─────────────────┐
   │ MCP 서버 2개   │◀────────│ scripts/run-mcp │
   │ (uvx on-demand)│         │ (.env 로드)      │
   └───────┬───────┘         └─────────────────┘
           │ JSON-RPC
           ▼
   ┌───────────────┐
   │ Claude Code   │
   │ mcp-operator  │
   │ 에이전트       │
   └───────┬───────┘
           │ 응답 저장
           ▼
   ┌──────────────────────────────────────┐
   │ data/raw/{source}/{tool}/*.json       │  [수집층]
   │ (가공 전, _meta 포함)                  │
   └────────────────┬─────────────────────┘
                    │
                    ▼  scripts/*.py 처리
   ┌──────────────────────────────────────┐
   │ data/processed/*.csv, *.md            │  [가공층]
   │ (매칭 점수, 풀 풀, 컨택 리스트)         │
   └────────────────┬─────────────────────┘
                    │
                    ▼  사람이 큐레이션
   ┌──────────────────────────────────────┐
   │ data/reports/*.md                     │  [리포트층]
   │ (영업용 큐레이션 마크다운)              │
   └──────────────────────────────────────┘
```

---

## 진입점 (목적별)

| 하고 싶은 일 | 어디부터 보면 되는가 |
|---|---|
| 프로젝트 첫 셋업 | [`README.md`](README.md) §"빠른 시작" |
| 작업 규칙·아키텍처 이해 | [`CLAUDE.md`](CLAUDE.md) |
| **이번 주 영업 후보 보기** | `data/reports/` — 로컬 전용(개인정보 포함, 비공개) |
| **낙찰 데이터 원본 직접 보기** | [`data/raw/README.md`](data/raw/README.md) |
| 가공된 CSV 받기 | `data/processed/` — 로컬 전용. `scripts/` 재실행으로 생성 |
| MCP tool 시그니처 | [`docs/mcp-tools.md`](docs/mcp-tools.md) |
| 새 키워드/기관 추가 | [`scripts/README.md`](scripts/README.md) |
| 에이전트 호출 방식 | [`.claude/agents/README.md`](.claude/agents/README.md) |
| 카페 서베이 | [`docs/research/README.md`](docs/research/README.md) |

---

## 데이터 보존 원칙

- **원시 응답은 절대 덮어쓰지 않는다**: `data/raw/` 는 append-only. 파일명에 timestamp.
- **가공 결과는 재현 가능해야 한다**: `data/processed/` 의 모든 CSV는 `scripts/` 의 어떤 명령으로 만들었는지 README에 기록.
- **리포트는 사람이 큐레이션**: `data/reports/` 는 자동 생성물 + 사람의 판단 혼합. README 에 작성자 의도 명시.

---

## 다음 단계 (CLAUDE.md "Out of Scope" 참조)

이번 정리 단계에서는 **하지 않은 것들**:
- 자체 DB 스키마 설계 (`db/schema.sql`)
- 웹 뷰어 (사용자 본 목표 — 별도 단계)
- 자체 MCP / 비즈니스 로직

본 인덱스 + 각 폴더 README가 정착하면, 그 위에 웹 뷰어를 얹는다.
