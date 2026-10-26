# 나라장터 데이터 MCP — 에이전트 작업 안내

Codex·Claude Code 등 AI 코딩 도구와 사람이 같은 계약을 따르기 위한 지침이다. 상세 개발 절차는 [CONTRIBUTING.md](CONTRIBUTING.md), 데이터 계약은 [docs/contract.md](docs/contract.md), 전환은 [docs/migration.md](docs/migration.md)를 따른다.

## 작업 전 확인

1. [README.md](README.md)에서 설치·지원 환경·제품 범위를 읽는다.
2. 현재 요청이 조사·설명인지 파일 수정인지 구분하고, 수정 전 `git status --short`와 관련 diff를 확인한다. 다른 사람의 변경·작업 DB·인증·실행 중 프로세스를 보존한다.
3. 관련 소스·호출부·시험과 입출력 계약을 필요한 범위만 읽는다. 변경 목적·영향·검증 방법을 정한다.
4. 실제 키·개인정보·고객 자료를 코드·시험·문서·로그에 넣지 않는다. 가상 HTML/JSON과 `.invalid` 도메인 등 분명한 예제를 사용한다.

이 문서는 공개 저장소의 작업 기준이다. 특정 편집기·AI 서비스·운영 MCP·개인 경로·전용 기록 도구가 필요하지 않다. 설치된 도구와 사용자의 명시 범위를 우선하며 새 전역 설정·자동화·외부 게시를 임의로 추가하지 않는다.

## 개발 환경과 시험

```bash
python3 setup-lab.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

설치는 프로젝트 `.venv`에 한정한다. 코드 변경 후 설치된 패키지로 시험하려면 `setup-lab.py`를 다시 실행하거나 다음과 같이 로컬 소스를 재설치한다. 전역 패키지는 변경하지 않는다.

```bash
.venv/bin/python -m pip install --no-build-isolation --no-deps .
```

pip가 없는 uv 환경은 `uv pip install --python .venv/bin/python --no-build-isolation --no-deps .`을 사용한다. `.venv`에 이전 복사본이 설치된 채 소스만 수정하면 옛 코드를 시험할 수 있으므로 import 경로·버전을 확인한다. 리소스가 제한된 환경에서는 시험을 직렬로 실행하고 불필요하게 중복 실행하지 않는다.

자동 시험은 외부 실서비스를 호출하지 않는다. 실조회가 요청되었을 때만 대상·입력·최대 호출수·저장 위치를 명확히 한 뒤 수행한다. 인증·차단·할당량 문제를 우회하거나 0건으로 숨기지 않는다.

## 공통 변경 원칙

- 변경한 동작을 재현하는 회귀시험을 먼저 좁혀 실행하고 관련 전체 시험을 마친다. 문구 수정은 내용·링크·명령을 검증한다.
- 수집 결과와 상태가 다르면 원문·카운터·checkpoint의 관계부터 확인한다. 없는 값은 null과 사유로 표시하고 추정값으로 메우지 않는다.
- 저장 형식·공개 호출·종료코드 변경은 호환 영향·전환 경로·회귀시험을 함께 설계한다. 오래된 태그·검증 기록을 새 결과처럼 고치지 않는다.
- 실패 응답은 통제된 reason으로 반환한다. 요청 URL·헤더·키·쿠키가 예외·로그·stdout에 노출되지 않게 한다.
- 불필요한 의존성·코드 재정렬·광범위한 리팩터링을 섞지 않는다. 의존성을 바꿀 경우 pyproject와 lock 및 NOTICE의 실제 일치를 확인한다.
- 사용자 요청 없이 커밋·push·릴리스·업로드·운영 데이터 변경을 하지 않는다. 승인된 범위는 중복 확인 없이 수행한다.

## 완료 보고와 공개 점검

구체적인 변경·수행한 명령과 결과·미실행 범위를 간결하게 보고한다. 설치 성공, 로컬 회귀 통과, 외부 서비스 동작을 구분한다. 새 환경에서 소스 설치·CLI 도움말·가상 예제를 검증하며 라이선스·필수 고지를 포함한다. `.env`·작업 DB·실제 수집 원문·가상환경·개인 설정을 릴리스에 넣지 않는다. 공개 작업이 요청되면 태그·원격 커밋·CI·첨부 파일을 재조회한다.

## 코드 지도

| 경로 | 역할·변경 시 함께 볼 부분 |
|---|---|
| src/nara_data_mcp/ | 새 공개 Python 진입점, 기존 구현을 다시 작성하지 않음 |
| src/sionlab_procurement/cli.py | JSON CLI·종료코드·작업 경로 |
| src/sionlab_procurement/server.py | stdio 초기화·도구 스키마·신구 도구명 연결 |
| src/sionlab_procurement/client.py | 키 전달·공식 API 요청·응답·오류·민감 필드 제거 |
| src/sionlab_procurement/registry.py / official_operations.json | 공식 오퍼레이션·서비스·기간 정책 |
| src/sionlab_procurement/service.py | 입력 검증·정규화·단일 페이지 검색·상세 |
| src/sionlab_procurement/jobs.py | 잠금·호출 예약·SQLite 트랜잭션·재개 |
| src/sionlab_procurement/export.py | JSONL/CSV/XLSX·보기·장문 원문 보존 |
| tests/ | 입력·중단복구·Excel·MCP 프로세스·호환 회귀 |
| examples/ | 건설 공고·기관 발주계획 가상 자료·실행 코드 |

## 반드시 유지할 계약

- 공개명·명령 `nara-data-mcp`, 모듈 `nara_data_mcp`, 제작자·저작권 SIONLAB을 사용한다. 내부 `sionlab_procurement` 경로는 호환 인터페이스다.
- 기존 `sionlab-procurement` 명령·Python 모듈과 다섯 `sionlab_*` MCP 호출을 유지한다. 도구 목록에는 `nara_search/detail/collect/coverage/job_status`만 표시한다.
- `search/detail`은 한 페이지다. `collect`의 전체 최대20회 예산은 요청 직전 예약하고 같은 작업 재개로 초기화하지 않는다. 조건·예산 변경을 같은 작업에 적용하지 않는다.
- 페이지의 원문 저장과 다음 위치 갱신은 원자적이어야 한다. 저장 전후 중단 시험·동시 실행 잠금·중복 제거 기준을 함께 점검한다.
- 개찰 순위를 최종낙찰로 바꾸지 않는다. 담당자 구조화 필드 제거·금액 및 식별자 문자열·null 사유를 유지한다.
- 정상 호출한도 중단은 성공한 부분수집이다. `ok=true`, `partial=true`, `status=paused`와 실제 실패를 구분하고 MCP isError·CLI 종료코드가 일치하게 한다.
- `records/long_values`와 JSON 원문 계약·기존 SQLite 작업·SIONLAB_JOB_DIR를 유지한다. 보기 시트 추가가 원문 복원을 깨뜨리지 않게 한다.
- stdio stdout에는 MCP 메시지만 쓴다. 디버그 출력을 섞거나 임의 shell/HTTP 서버 기능을 추가하지 않는다.

## 자주 하는 수정의 검증 범위

| 수정 | 필요한 검증 |
|---|---|
| MCP 이름·스키마·진입점 | test_naming.py + 실제 stdio 초기화·목록·신구 호출 |
| 새 공식 오퍼레이션 | 공식 명세 확인·허용 파라미터·기간 정책·가상 정상/오류 응답·지원표 |
| 저장·재개 | test_contracts.py의 예산·실패·프로세스 중단·잠금 |
| Excel·정규화 | test_exports.py / test_release.py의 긴 값·수식문자·원문 대조 |
| 안내·설치 | README 명령·상대 링크·새 환경 설치·가상 예제 |

새 오퍼레이션 등록만으로 실API 검증 완료라고 표시하지 않는다. 일반 검색에 특수 상세 조건을 무조건 재사용하지 말고 operation별 공식 입력을 확인한다.
