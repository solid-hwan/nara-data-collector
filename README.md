# 나라장터 데이터 MCP 0.5.0

**공고·발주계획 검색과 수집**을 위한 MIT 라이선스 Python 도구입니다. 공개 제품명은 나라장터 데이터 MCP, 저장소·패키지·명령은 `nara-data-mcp`입니다. 제작자·저작권자는 SIONLAB입니다.

Python CLI만으로 검색·저장·Excel 출력을 사용할 수 있습니다. MCP를 지원하는 AI 클라이언트와 연결할 수도 있습니다. 특정 AI 서비스, 시온랩 계정, 개인 작업 공간 없이 독립 실행하며, 실제 조달 API 조회에는 사용자가 발급받은 공공데이터포털 키와 해당 API 이용 권한이 필요합니다.

[빠른 시작](#빠른-시작) · [MCP 연결](#mcp-연결) · [활용 방법](docs/recipes.md) · [입출력 계약](docs/contract.md) · [지원 범위](docs/coverage.md) · [전환 안내](docs/migration.md) · [기여하기](CONTRIBUTING.md)

## 어떤 일에 쓰나요

| 목적 | 사용 흐름 | 결과 해석 |
|---|---|---|
| 공사·물품·용역 공고 조사 | search → detail | 조건에 맞는 한 페이지·식별자 일치행 확인 |
| 기관 발주계획 정리 | plans 조건 작성 → collect → export | 게시기간과 발주예정년월을 각각 지정 |
| 기간별 조달자료 보관 | collect → status → 같은 job 재개 | 저장 건수·실패 구간·남은 위치 확인 |
| 개찰·최종낙찰 자료 비교 | openings와 awards를 별도로 조회 | 개찰 순위 1을 최종낙찰로 추정하지 않음 |
| 내부 분석·보고 자동화 | Python 또는 JSON CLI → JSONL/CSV/Excel | 원문과 정규화값·누락 사유 보존 |
| AI 도구 연동 | MCP stdio → 다섯 도구 호출 | 같은 Python 서비스·저장 계약 사용 |

추천 점수, 첨부 HWP/PDF 분석, 로그인·입찰 제출, 모든 하위 상세의 자동 병합은 제공하지 않습니다. [서비스 지원표](docs/coverage.md)는 등록된 공식 명세와 과거 실조회 검증을 구분합니다.

## 빠른 시작

Python 3.11 이상이 필요합니다. 아래 명령은 Linux/macOS 셸 기준이며 CI는 Ubuntu의 Python 3.11·3.12를 사용합니다. Windows 잠금 코드는 포함하지만 네이티브 Windows 전체 흐름은 미검증입니다. WSL에서는 아래 명령을 사용할 수 있습니다.

```bash
git clone https://github.com/solid-hwan/nara-data-mcp.git
cd nara-data-mcp
python3 setup-lab.py
.venv/bin/nara-data-mcp --help
.venv/bin/python -m nara_data_mcp coverage
.venv/bin/python examples/run_examples.py --output /tmp/nara-data-mcp-demo
```

`setup-lab.py`는 이 폴더의 `.venv`만 준비합니다. 의존성 설치에는 네트워크가 필요하지만 `coverage`와 가상 예제는 API 키·외부 조달 호출 없이 실행됩니다. 가상 예제는 공사 공고와 기관 발주계획 두 사례의 JSONL·CSV·Excel을 생성하고 원문을 다시 읽어 대조합니다. 예제 출력은 새 임시 폴더를 사용하세요.

[Releases](https://github.com/solid-hwan/nara-data-mcp/releases)에서 검증 ZIP을 받아 압축을 푼 후 `python3 setup-lab.py`를 실행해도 됩니다. PyPI 배포는 하지 않으므로 `pip install nara-data-mcp`를 설치 방법으로 안내하지 않습니다.

기존 가상환경을 직접 관리하는 경우:

```bash
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps .
```

## 실제 검색·수집·내보내기

`DATA_GO_KR_API_KEY`에 발급받은 **디코딩 키**를 프로세스 환경으로 주입합니다. `.env`나 다른 제품의 인증 파일은 자동으로 읽지 않습니다. 실제 키를 명령 이력·문서·저장소에 넣지 말고 사용하는 셸 또는 클라이언트의 비밀정보 관리 기능으로 전달하세요.

`examples/construction-query.json`을 `my-query.json`으로 복사해 날짜·업무구분·조건을 고칩니다. 예제 날짜는 고정된 가상 시나리오이며, 기관 예제의 `SYNTHETIC-ORG`는 실제 기관코드가 아닙니다.

```bash
.venv/bin/nara-data-mcp search --query my-query.json
.venv/bin/nara-data-mcp --job-dir ./jobs collect --job notices-001 --query my-query.json
.venv/bin/nara-data-mcp --job-dir ./jobs status --job notices-001
.venv/bin/nara-data-mcp --job-dir ./jobs collect --job notices-001
.venv/bin/nara-data-mcp --job-dir ./jobs export --job notices-001 --output ./output/notices-001
```

`--job-dir`는 하위 명령보다 앞에 둡니다. 기본 경로는 `jobs`, 기존 환경변수 `SIONLAB_JOB_DIR`도 유지합니다. `--max-calls`를 기본값20과 다르게 설정했다면 재개할 때도 동일한 값을 지정해야 합니다. 실제 실패 원인이 해결된 경우에만 `--retry-failed`를 명시합니다.

| 명령 | 의미 |
|---|---|
| coverage | 공식 오퍼레이션·허용 입력명·검증 범위, 키 불필요 |
| search / detail | 한 페이지 검색 / 식별자 일치행, JSON query 파일 입력 |
| collect | 기간 분할·페이지별 저장·동일 조건 재개, job 전체 최대20회 |
| status | 저장 위치·건수·실패·checkpoint, `--include-data`로 저장행 포함 |
| export | 저장 작업을 records.jsonl / records.csv / records.xlsx로 출력 |
| serve | MCP stdio 서버, stdout은 프로토콜 전용 |

출력은 JSON입니다. `ok=true`는 요청 처리 성공이지 전체 수집 완료가 아닙니다. `partial`, `status`, `reason`, `source_total_count`, `unique_count`를 함께 확인합니다. 정상 예산 소진은 `status=paused`, `partial=true`, `reason=call_budget_exhausted`, CLI 종료코드0입니다. 실제 실패는 종료코드1입니다. 예산은 같은 작업 재개 시 초기화되지 않습니다.

## MCP 연결

[설정 예제](examples/mcp-config.json)의 Python·작업 경로를 본인 설치의 절대 경로로 바꿉니다. 서버 등록 메뉴나 설정 파일 위치는 사용하는 MCP 클라이언트의 안내를 따릅니다.

```json
{
  "mcpServers": {
    "nara-data-mcp": {
      "command": "/ABSOLUTE/PATH/nara-data-mcp/.venv/bin/python",
      "args": ["-m", "nara_data_mcp", "--job-dir", "/ABSOLUTE/PATH/jobs", "serve"],
      "env": {"DATA_GO_KR_API_KEY": "REPLACE_LOCALLY_WITH_DECODED_KEY"}
    }
  }
}
```

| 표시되는 도구 | 목적 |
|---|---|
| nara_search | 공공 조달자료 한 페이지 검색 |
| nara_detail | 번호·차수 등 식별자 일치행 조회 |
| nara_collect | SQLite에 수집·중단 위치 재개 |
| nara_coverage | 지원 오퍼레이션·파라미터·한계 확인 |
| nara_job_status | 작업 상태·저장 건수·선택 저장행 확인 |

서버는 stdio만 제공하며 HTTP 서비스로 열지 않습니다. 클라이언트 연결 후 초기화와 도구 목록을 확인하세요. 운영 중인 MCP 설정을 자동 변경하지 않습니다.

## Excel과 원문 활용

`records.xlsx`는 공고명·번호·차수·기관·원문 링크를 표시하는 **Overview**로 열립니다. **Collection**에는 조회조건·건수·다음 위치·부분수집 사유·UTC 시각이 있습니다. **records / long_values**는 전체 원문 복원용입니다. 장문은 분할 보관하며 수식 모양 값과 큰 금액은 문자열로 유지합니다. 원문 대조 정본은 JSONL입니다.

담당자 이름·전화·이메일 등 구조화된 연락처 필드는 저장·반환 전에 제외합니다. 자유형 본문에 포함된 개인정보까지 자동 판별하지는 않으므로 외부 공유 전 확인하세요. 데이터 이용 권한은 코드의 MIT 라이선스와 별개입니다.

## Python에서 재사용

```python
from nara_data_mcp import Client, Procurement

service = Procurement(Client(), job_dir="./jobs")
coverage = service.coverage()  # 인증·외부 호출 없음
```

실제 조회는 `Client(key=...)`에 환경에서 읽은 키를 명시 전달합니다. 테스트에서는 `Client(transport=fixture, interval=0)`로 외부 호출을 대체합니다. 내부 구현 경로 `sionlab_procurement.*`도 유지합니다. [활용·확장 예제](docs/recipes.md)를 참고하세요.

## 호환과 업그레이드

0.5.0은 명칭 변경판입니다. 기존 `sionlab-procurement`, `python -m sionlab_procurement`, MCP `sionlab_search/detail/collect/coverage/job_status` 호출을 유지합니다. MCP 목록에는 새 이름만 표시합니다. 0.4.0 작업 DB·예산·Excel 형식은 그대로 이어 씁니다.

기존 패키지와 파일이 겹치므로 새 가상환경에 설치하고 같은 작업 폴더를 지정하는 방법을 권장합니다. 더 오래된 KONEPS 제품의 추천·첨부 분석·설정은 별도 계약입니다. [전환 안내](docs/migration.md)와 보존된 [v0.3.1](https://github.com/solid-hwan/nara-data-mcp/tree/v0.3.1)을 확인하세요.

## 개발·문제 해결

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

자동 시험은 가상 API·프로세스·로컬 파일을 사용하며 실제 조달 API를 호출하지 않습니다. [과거 검증 기록](docs/verification.md)은 당시 버전의 근거입니다. 현재 시험 결과는 GitHub Actions와 해당 릴리스 안내에서 확인합니다.

| 증상 | 확인할 내용 |
|---|---|
| missing_api_key | 키가 해당 프로세스에 전달됐는지 확인, 값은 출력하지 않음 |
| query_mismatch_use_new_job_id | 기존 작업 조건 변경 여부, 바꾼 조건은 새 job 사용 |
| budget_mismatch_use_original_max_calls | 최초 --max-calls와 동일한 값 사용 |
| call_budget_exhausted | 작업 전체 호출 상한 도달, 자동 연장하지 않음 |
| job_busy | 같은 작업 실행이 끝날 때까지 대기, 실행 중 DB·잠금 삭제 금지 |
| 차단·API 오류 | 권한·할당량·공식 입력 조건 확인, 오류를 정상0건으로 처리하지 않음 |

기여자는 [CONTRIBUTING.md](CONTRIBUTING.md), AI 코딩 도구는 [AGENTS.md](AGENTS.md)와 [CLAUDE.md](CLAUDE.md)를 먼저 읽습니다. 버그 제보는 OS·Python·제품 버전·키를 제거한 입력·reason·기대 결과를 포함해 [Issues](https://github.com/solid-hwan/nara-data-mcp/issues)에 남겨 주세요.

[MIT LICENSE](LICENSE) · [외부 의존성 고지](NOTICE.md) · [변경 이력](CHANGELOG.md). 코드 수정·재배포·상업적 활용 시 저작권·허락 고지를 유지하세요.
