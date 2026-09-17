# KONEPS_sionlab

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![validate](https://github.com/kkhwan1/KONEPS_sionlab/actions/workflows/validate.yml/badge.svg)](https://github.com/kkhwan1/KONEPS_sionlab/actions/workflows/validate.yml)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-6B4FBB)](https://modelcontextprotocol.io)
[![Release](https://img.shields.io/github/v/release/kkhwan1/KONEPS_sionlab)](https://github.com/kkhwan1/KONEPS_sionlab/releases)

> 🇰🇷 **나라장터(KONEPS/G2B) 공공 조달 데이터**를 Claude 로 자연어 질의할 수 있게 해주는 **MCP 연결 워크스페이스**.
> Claude Code / Claude Desktop 양쪽에서 동일하게 작동하며, API 키는 `.env` 한 곳에서만 관리합니다.

> **English** · Query Korean government procurement data via MCP. Works with both Claude Code and Claude Desktop. API keys stay in a local `.env`; the `.mcp.json` is key-free.

**작성자 · Author**: KKHWAN · ✉ [lee.kkhwan@gmail.com](mailto:lee.kkhwan@gmail.com)

<sub>🔎 **키워드** · 나라장터 · 조달청 · 국가종합전자조달 · 공공조달 · 공공데이터포털 · 입찰공고 · 낙찰정보 · 계약정보 · KONEPS · G2B · data.go.kr · MCP · Model Context Protocol · Claude · Claude Code · Claude Desktop · Korea public procurement · Korean government procurement API</sub>

---

## 📑 목차
1. [이게 뭐예요?](#-이게-뭐예요)
2. [누가 쓰면 좋은가](#-누가-쓰면-좋은가)
3. [작동 구조](#-작동-구조)
4. [빠른 시작 (3분)](#-빠른-시작-3분)
5. [공공데이터포털에서 API 키 받기](#-공공데이터포털에서-api-키-받기)
6. [Claude Code 에서 쓰기](#-claude-code-에서-쓰기)
7. [Claude Desktop 에서 쓰기](#-claude-desktop-에서-쓰기)
8. [제공되는 MCP Tool](#-제공되는-mcp-tool)
9. [프로젝트 구조](#-프로젝트-구조)
10. [에이전트 팀](#-에이전트-팀-claude-code-전용)
11. [트러블슈팅](#-트러블슈팅)
12. [로드맵](#-로드맵)
13. [기여/라이선스](#-기여--라이선스)

---

## 🎯 이게 뭐예요?

**한 줄 설명** — Claude 대화창에 *"AI 관련 입찰공고 찾아줘"* 라고 입력하면, Claude 가 **나라장터 공식 API** 를 호출해 실시간으로 공고 목록을 가져오는 환경입니다.

**기존 방식**:
```
공공데이터포털 → API 문서 읽기 → 코드 작성 → 파라미터 디버깅 → 응답 파싱 ...
```

**이 프로젝트로**:
```
Claude 대화창: "나라장터에서 'AI' 관련 공고 찾아줘"
              ↓ (MCP 경유 자동 호출)
              ← 공고번호, 기관, 예산, 마감일 포함한 목록 반환
```

---

## 👥 누가 쓰면 좋은가

| 사용자 유형 | 도구 | 얻는 가치 |
|---|---|---|
| **개발자/엔지니어** | Claude Code | MCP + 에이전트 팀 + 스키마 설계 + 검증 파이프라인 풀스택 |
| **비개발 실무자** (기획/영업/입찰 담당) | Claude Desktop | 대화창에서 자연어 한 줄로 공고 검색/요약 |
| **분석가** | Desktop + Excel | MCP 응답을 복사해 가공 |
| **팀 리드** | 양쪽 모두 | Code 로 데이터 파이프라인 구축 → Desktop 으로 팀원 배포 |

---

## 🏗️ 작동 구조

### 전체 아키텍처

```
┌───────────────────────────────────────────────────────────────┐
│  사용자 대화창                                                 │
│  "나라장터에서 AI 입찰공고 찾아줘"                              │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Claude (Code 또는 Desktop)                                    │
│  - 요청 의도 파악                                              │
│  - 적절한 MCP tool 선택 (get_bids_by_keyword)                  │
└──────────────────────────┬────────────────────────────────────┘
                           │ JSON-RPC over stdio
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  scripts/run-mcp.sh (래퍼)                                     │
│  - .env 에서 API 키 로드                                       │
│  - uvx 로 MCP 서버 on-demand 기동                              │
└──────────────────────────┬────────────────────────────────────┘
                           │
          ┌────────────────┴───────────────┐
          ▼                                ▼
┌───────────────────────┐    ┌───────────────────────────────┐
│  nara-jangteo         │    │  data-go-mcp.pps-narajangteo  │
│  (Datajang)           │    │  (Koomook)                    │
│  • 키워드 검색         │    │  • 입찰공고 원시             │
│  • 부서 추천           │    │  • 낙찰 정보                 │
│  • RFP 파일 추출       │    │  • 계약 정보                 │
└──────────────────────┬┘    └──────────┬────────────────────┘
                       │                │
                       └────┬───────────┘
                            ▼
              ┌─────────────────────────────┐
              │  data.go.kr 공공데이터포털   │
              │  (조달청 나라장터 공식 API)  │
              └─────────────────────────────┘
```

### 4개 핵심 설계 결정

1. **`.mcp.json` 에 API 키 0개**
   래퍼 스크립트(`scripts/run-mcp.sh`)가 `.env` 에서 키를 읽어 런타임에 주입. 키 교체는 `.env` 한 곳만 수정.

2. **프로젝트 스코프 한정**
   글로벌 `~/.claude.json` 을 절대 건드리지 않음. 다른 프로젝트에 영향 없음.

3. **`uvx` on-demand**
   MCP 서버를 글로벌 설치하지 않음. 세션 시작 시 PyPI 에서 pull. 캐시된 뒤엔 즉시 기동.

4. **에이전트 팀 분리**
   메인 Claude 는 직접 호출, `mcp-operator` 서브에이전트는 대량/반복 호출 담당. 다른 에이전트는 MCP 접근 불가로 격리.

---

## ⚡ 빠른 시작 (3분)

### 사전 요구사항
- `uvx` 0.10+ — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Claude Code CLI **또는** Claude Desktop 앱
- `data.go.kr` 인증키 ([받는 법 ↓](#-공공데이터포털에서-api-키-받기))

### 3줄 설치
```bash
git clone https://github.com/kkhwan1/KONEPS_sionlab.git
cd KONEPS_sionlab
cp .env.example .env   # .env 열어서 본인 키 붙여넣기
```

### 각자 환경에 맞게
```bash
# Claude Code 사용자
claude                                # 프로젝트 MCP 승인 프롬프트 수락

# Claude Desktop 사용자 (자동 설치)
bash scripts/setup-claude-desktop.sh  # Desktop 재시작 필요
```

끝. Claude 에 *"나라장터에서 AI 검색해줘"* 입력하면 작동합니다.

---

## 🔑 공공데이터포털에서 API 키 받기

### 왜 필요한가
나라장터 데이터는 **공공데이터포털(`data.go.kr`)** 을 통해 제공됩니다. 무료이지만 **사용자 식별용 인증키** 가 필요합니다.

### 한눈에 보는 절차

```
① 포털 회원가입 → ② API 페이지 [활용신청] 클릭 → ③ 자동승인 즉시 → ④ 마이페이지에서 키 복사
```

### 화면으로 따라가기

**① 공공데이터포털 메인** — <https://www.data.go.kr/>

우상단 **회원가입** → 본인인증 → 가입 완료.

**② 나라장터 API 페이지** — <https://www.data.go.kr/data/15129394/openapi.do>

확인할 메타 정보:

| 항목 | 값 | 의미 |
|---|---|---|
| 비용 | **무료** | 💰 돈 안 듦 |
| 심의유형 | **자동승인** | ⚡ 즉시 승인 |
| 트래픽 | 개발계정 **1,000/일** | 초기 충분 |

**③ 우상단 파란 [활용신청] 버튼 클릭**

신청서에 활용목적 한 줄 작성(예: "조달 데이터 분석 MCP 도구") → 제출 → **자동승인**.

**④ 마이페이지에서 키 확인**

`마이페이지 → 오픈API → 개발계정 → 신청한 서비스 클릭` 에서 **"일반 인증키 (Decoding)"** 복사.

> ⚠️ **반드시 Decoding 키를 쓰세요.** Encoding 키는 `%2B`, `%2F` 가 들어있어 이중 인코딩으로 401 에러가 납니다.

**⑤ 프로젝트 `.env` 에 붙여넣기**
```bash
NARA_API_KEY=abc/def+ghi==...     # 복사한 Decoding 키
NARA_PRESPEC_API_KEY=abc/def+...  # 동일 키로 우선 시도
chmod 600 .env                    # 권한 제한
```

> **서비스마다 활용신청이 따로 필요합니다.** 입찰공고정보서비스 키로 사전규격·낙찰정보까지
> 되는 경우가 있지만 보장되지 않습니다. 같은 키로 먼저 시도하고, 인증 오류가 나면 해당
> 서비스를 개별 신청하세요. 아래 [트러블슈팅](#-트러블슈팅)의 엔드포인트 표를 함께 보세요.

---

## 💻 Claude Code 에서 쓰기

### 실행
```bash
cd KONEPS_sionlab
claude
```
첫 기동 시 *"Trust this project's MCP servers?"* 프롬프트가 뜹니다. **Yes** 선택.

### 사용 예시
```
> 나라장터에서 "AI" 관련 최근 7일 입찰공고 찾아줘

> "한국연구재단"에서 공고한 최근 용역 입찰 목록 정리
  → 공고번호, 예산, 마감일만 표로

> 다음 PDF 를 RFP 로 분석해 핵심 요구사항 추출:
  [제안요청서]AI기반 벤처펀드 모니터링 시스템 구축.pdf
```

### 에이전트 팀 활용
대량 데이터 수집이나 스키마 설계처럼 복잡한 작업은 에이전트에 위임:
```
> orchestrator 에게 위임: 최근 한 달간 "플랫폼" 키워드 공고 전부 수집 후
  기관별 예산 합계 리포트
```

---

## 🖥️ Claude Desktop 에서 쓰기

### 자동 설치 (권장)
```bash
bash scripts/setup-claude-desktop.sh
```
- OS 자동 감지 (macOS/Windows/WSL)
- 기존 MCP 서버 설정은 **병합** (덮어쓰지 않음)
- 타임스탬프 백업 자동 생성

이후 **Claude Desktop 완전 종료 → 재시작**.

### 사용 예시
Desktop 대화창에서 자연어로 요청:
```
나라장터에서 이번 주 공고 중에 "데이터 플랫폼" 관련 3개만 요약해줘
```

### 한계점
Desktop 에는 서브에이전트 개념이 없습니다. 대량 수집·스키마 설계 같은 복잡한 워크플로우는 Claude Code 를 사용하세요.

설정 자동 병합은 `scripts/setup-claude-desktop.sh` 가 처리합니다 (macOS·Windows·WSL 자동 감지, 기존 설정 병합, 타임스탬프 백업).

---

## 🛠️ 제공되는 MCP Tool

### `koneps-sionlab` (이 저장소 자체 구현 · v0.2.0)

서드파티 MCP 두 개가 **물품·용역 중심**이라 놓치는 축을 직접 조회합니다.
`src/koneps_mcp/` 의 표준 라이브러리 구현이고, 읽기 전용(GET)입니다.

| Tool | 용도 |
|---|---|
| `koneps_search` | 9개 서비스 × 업무구분 전 축 조회 |
| `koneps_coverage` | 서비스·업무구분 가능 조합과 활용신청 번호 (API 호출 없음) |

**이번에 넓힌 커버리지** — 아래는 전부 2026-09-17 실호출로 확인했습니다.

| 서비스 | 업무구분 | 왜 필요한가 |
|---|---|---|
| 입찰공고 | 물품·용역·**공사·외자·기타** | **기타공고**는 나머지 넷 어디에도 잡히지 않는 별도 축이다. 민간위탁 수탁기관 모집 같은 건이 여기 있다 |
| 낙찰(개찰결과) | 물품·용역·**공사·외자** | |
| **사전규격** | 물품·용역·공사·외자 | 발주 3~6개월 전 신호. 공고가 뜨기 전에 보인다 |
| **조달요청** | 물품·공사·외자·**일반용역·기술용역** | 이 서비스만 용역이 둘로 갈린다 |
| 계약정보 | 물품·용역·공사·외자 | |
| 계약과정통합공개 | 물품·용역·공사·외자 | 발주계획→사전규격→낙찰→계약 연결 |
| **누리장터 민간입찰** | 물품·용역·공사·**기타** | 아파트관리사무소·영리법인 등 **수요기관이 아닌 주체**의 입찰. 나라장터와 모집단이 겹치지 않는다 |
| 공공데이터개방표준 | (bsnsDivCd 로 구분) | 낙찰 조회는 이 계열만 최종낙찰 여부(`sucsfYn`)를 준다 |

```
"나라장터 기타공고 중에 어제 올라온 것 보여줘"
"용역 사전규격 최근 3일치 — 아직 공고 안 뜬 건"
"누리장터 민간입찰에 용역 뭐 있어?"
```

> **담당자 연락처는 기본적으로 응답에서 제외합니다.** 나라장터 응답에는
> 담당자 실명·전화·이메일이 포함되는데, 대화 로그에 남으면 회수할 수 없습니다.
> 필요하면 `include_contacts: true` 를 명시하거나 공고 원문 링크에서 확인하세요.

### `nara-jangteo` (Datajang 제공)
| Tool | 용도 |
|---|---|
| `get_bids_by_keyword` | 키워드로 최근 7일 입찰공고 + 사전규격 동시 검색 |
| `recommend_bids_for_dept` | 부서 프로필에 맞춰 공고 추천 (최대 60건) |
| `analyze_bid_detail` | HWP/PDF/DOCX 첨부파일에서 RFP 텍스트 추출 |

### `data-go-mcp.pps-narajangteo` (Koomook 제공)
| Tool | 용도 |
|---|---|
| `search_bid_announcements` | 입찰공고 원시 조회 (최대 1개월) |
| `get_bid_detail` | 공고번호로 상세 조회 ⚠️ *업스트림 버그, 현재 실패* |
| `search_successful_bids` | 낙찰정보 조회 (용역/물품/공사 구분) |
| `search_contracts` | 계약정보 조회 (기관/기간 필터) |

실제 시그니처/파라미터: [`docs/mcp-tools.md`](./docs/mcp-tools.md)

---

## 📂 프로젝트 구조

> 📍 **전체 인덱스는 [`PROJECT_MAP.md`](PROJECT_MAP.md) 참조** — 각 폴더는 자신의 README를 가진다.

```
KONEPS_sionlab/
│
├── PROJECT_MAP.md             ← 🆕 전체 폴더/데이터 흐름 한 장 인덱스
├── .mcp.json                  ← Claude Code 가 자동 로드 (키 0개)
├── .env.example               ← 환경변수 템플릿 (git 포함)
├── .env                       ← 실제 키 (git 제외, 직접 생성)
│
├── scripts/                   ← 🆕 README 추가
│   ├── README.md              ← 스크립트 카탈로그/입출력
│   ├── run-mcp.sh             ← MCP 기동 래퍼
│   ├── setup-claude-desktop.sh ← Desktop 설정 자동 병합기
│   ├── keyword_search.py      ← 키워드 매칭 (9개 카테고리)
│   ├── winner_match.py        ← 기관 매칭
│   ├── match_phase3.py        ← 부서별 점수
│   └── winner_collab_score.py ← 협업 후보 스코어링
│
├── .claude/
│   └── agents/                ← 에이전트 팀 (5개) + README
│       └── README.md          ← 🆕 에이전트 카탈로그
│
├── docs/                      ← 🆕 README 추가
│   ├── README.md              ← 문서 인덱스
│   ├── mcp-tools.md           ← tool 카탈로그
│   ├── claude-desktop-config.template.json
│   ├── sionlab-profile.md     ← Sion Lab 회사 프로필
│   └── research/              ← 외부 리서치 노트
│       ├── README.md
│       ├── naver-cafe-narajangteo-survey.md
│       └── cafes/README.md    ← 카페별 분석 인덱스
│
├── data/
│   ├── raw/                   ← MCP 원시 응답 (git 제외)
│   │   ├── README.md          ← 명명 규칙
│   │   ├── nara-jangteo/      ← 🆕 README + 3 tool 폴더
│   │   ├── data-go-mcp/       ← 🆕 README + 4 tool 폴더
│   │   └── naver-cafe/        ← 🆕 README + 카페별 폴더
│   ├── processed/             ← 🆕 README + 가공 CSV/MD
│   │   └── README.md          ← 9개 산출물 카탈로그
│   └── reports/               ← 영업 리포트 (사람 큐레이션)
│       └── README.md
│
├── db/                        ← (2단계) SQLite 스키마 예정
│
├── .github/
│   ├── workflows/validate.yml ← CI: JSON/shell 검증, 키 누출 점검
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── CLAUDE.md                  ← Claude Code 프로젝트 지침
├── README.md                  ← 이 파일
├── LICENSE                    ← MIT
├── CONTRIBUTING.md            ← 기여 가이드
├── SECURITY.md                ← 보안 정책
├── CODE_OF_CONDUCT.md         ← 행동 강령
└── CHANGELOG.md               ← 버전 변경 이력
```

---

## 🤖 에이전트 팀 (Claude Code 전용)

`.claude/agents/` 에 정의된 5개 서브에이전트:

| 에이전트 | 역할 | MCP tool 권한 |
|---|---|---|
| `orchestrator` | 사용자 요청 분해/라우팅 | ❌ |
| `mcp-operator` | **실제 MCP 호출 담당** | ✅ 9개 tool |
| `data-modeler` | MCP 응답 → SQLite DDL 설계 | ❌ |
| `verifier` | 완료 주장 전 증거 수집 | ❌ |
| `docs-writer` | 문서/런북 유지 | ❌ |

메인 Claude 가 사용자 요청을 받으면 → `orchestrator` 에게 작업 분해 위임 → `mcp-operator` 가 MCP 호출 → `verifier` 가 응답 검증 → 결과 통합.

세부 운영 규칙: [`CLAUDE.md`](./CLAUDE.md)

---

## 🩺 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| **401/403 응답** | `data.go.kr` 활용신청 승인 대기(1~2시간) 또는 `.env` 에 키 미입력. Encoding 키 대신 Decoding 키 사용 확인 |
| **사전규격 403** | `NARA_PRESPEC_API_KEY` — 해당 API 별도 활용신청 필요할 수 있음 |
| **`uvx` hang** | 네트워크 또는 `UV_LINK_MODE=copy` 누락. `uvx --refresh` 로 재시도 |
| **tool 목록에 MCP 없음** | `.mcp.json` 문법 오류 또는 Claude Code/Desktop 재시작 안 됨. `python3 -m json.tool < .mcp.json` 로 검증 |
| **서브에이전트 "tool not available"** | `.claude/agents/{name}.md` frontmatter `tools:` 에 MCP tool 누락. 수정 후 Claude Code 세션 재시작 |
| **`get_bid_detail` 실패** | 업스트림 버그. `search_bid_announcements` 로 대체 조회 |
| **일일 호출 한도 초과** | 개발계정 1,000/일. `data/raw/` 캐시 먼저 확인 또는 운영계정 승인 |

### ⚠️ 엔드포인트 마이그레이션 (2026-09-17 실측)

조달청이 입찰공고정보서비스 경로를 버전 접미사(`...Service02`, `...Service04`) 방식에서
`/ad/` 네임스페이스로 옮겼습니다. **구 경로는 응답하지 않습니다.**

| 경로 | 실측 결과 |
|---|---|
| `…/1230000/BidPublicInfoService04/getBidPblancListInfoServc` | ❌ **HTTP 400 — 폐기됨** |
| `…/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc` | ✅ 200 `resultCode=00` |
| `…/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch` | ✅ 200 — 공고명·기관·금액 검색 계열 |
| `…/1230000/ad/BidPublicInfoService/getBidPblancListInfoEtc` | ✅ 200 — **기타공고** |
| `…/1230000/ao/HrcspSsstndrdInfoService/getPublicPrcureThngInfoServc` | ✅ 200 — 사전규격 (`/ao/` 주의) |
| `…/1230000/ao/CntrctProcssIntgOpenService/getCntrctProcssIntgOpenServc` | ✅ 200 — 계약과정통합 |
| `…/1230000/ao/PubDataOpnStdService/getDataSetOpnStdScsbidInfo` | ✅ 200 — 낙찰 (개방표준, `sucsfYn` 포함) |

서비스 계열에 따라 `/ad/` 와 `/ao/` 가 갈립니다. 임의로 바꿔 쓰면 404 가 아니라 **400** 이 옵니다.

**오류 응답 두 종류를 구분하세요** — 원인이 완전히 다릅니다.

| 응답 본문 | 의미 | 조치 |
|---|---|---|
| `OpenAPI_ServiceResponse.cmmMsgHeader` 에 `NO_OPENAPI_SERVICE_ERROR` / `returnReasonCode=12` | **경로가 틀렸다** (서비스명·오퍼레이션명 오타, 폐기된 버전) | 경로를 공식 명세에서 재확인. 키 문제가 아님 |
| `nkoneps.com.response.ResponseError` 에 `resultCode=08 필수값 입력 에러` | 경로는 맞고 **필수 파라미터가 빠졌다** | 서비스별 필수 파라미터(`inqryDiv`, 기간 필드명) 확인 |
| `resultCode=03` | 정상 응답이나 **데이터 없음** | 오류가 아님. 기간·조건을 넓힐 것 |

### ⚠️ 업스트림 의존성 상태 (2026-09-17 확인)

이 저장소는 서드파티 MCP 서버 2개를 `uvx` 로 실행합니다. 코드가 아니라 **배선**이므로
업스트림 상태가 그대로 영향을 줍니다.

| 패키지 | 최신 버전 | 최근 릴리스 | 상태 |
|---|---|---|---|
| `nara-mcp-server` | 1.3.3 | 2026-04-09 | 유지 중 |
| `data-go-mcp.pps-narajangteo` | 0.1.1 | **2025-09-15** | ⚠️ 1년 이상 릴리스 없음. PyPI 프로젝트 URL이 `yourusername` 플레이스홀더 |

- `scripts/run-mcp.sh` 는 `data-go-mcp.pps-narajangteo@latest` 를 씁니다. 업스트림이 예고 없이
  바뀌면 즉시 영향을 받으므로, 재현성이 필요하면 버전을 고정하세요.
- **`mcp<2` 상한은 유지해야 합니다.** 두 업스트림 모두 `mcp>=1.x` 로 상한이 없어 `uvx` 가
  `mcp` 2.x(2026-09-07 기준 2.2.0)를 끌어오는데, mcp 2.0 이 `mcp.server.fastmcp` 경로를
  제거해 기동에 실패합니다.

---

## 🗺️ 로드맵

| 단계 | 상태 | 내용 |
|---|---|---|
| **1단계 — MCP 연결** | ✅ 완료 (v0.1.0) | 공개 MCP 2개 안정화 + Desktop 지원 |
| **2단계 — 스키마/ETL** | 🚧 계획 | `data/raw/` → SQLite DDL + 정규화 로더 |
| **3단계 — 자체 MCP** | 📋 구상 | `sionlab-mcp`: 비즈니스 로직 + 자사 DB 조인 |

---

## 🤝 기여 / 라이선스

- **기여 환영**: [CONTRIBUTING.md](./CONTRIBUTING.md)
- **보안 이슈**: [SECURITY.md](./SECURITY.md) (공개 이슈 대신 비공개 제보)
- **행동 강령**: [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)
- **변경 이력**: [CHANGELOG.md](./CHANGELOG.md)
- **라이선스**: [MIT](./LICENSE)

### 크레딧
- [Datajang/narajangteo_mcp_server](https://github.com/Datajang/narajangteo_mcp_server) — `nara-jangteo` MCP 원본
- [Koomook/data-go-mcp-servers](https://github.com/Koomook/data-go-mcp-servers) — `data-go-mcp.pps-narajangteo` MCP 원본
- [공공데이터포털 / 조달청](https://www.data.go.kr/) — 나라장터 API 제공

### 스크린샷 출처
본 README 의 포털 스크린샷은 [공공데이터포털](https://www.data.go.kr/) 2026-04-24 버전에서 캡처한 것이며, **교육 목적 이용허락 범위 내에서 사용**합니다. 포털 UI 변경 시 오래될 수 있습니다.
