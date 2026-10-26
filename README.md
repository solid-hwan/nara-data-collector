# SIONLAB Procurement MCP 0.4.0

기존 [KONEPS_sionlab v0.3.1](https://github.com/solid-hwan/KONEPS_sionlab/tree/v0.3.1)을 잇는 독립 패키지입니다. **도구명·설정이 바뀌는 전환 릴리스**이므로 기존 사용자는 [전환 안내](docs/migration.md)를 먼저 확인하세요.

공공 조달자료의 한 페이지 검색과, 기간을 나누어 저장하는 재개 가능한 수집 도구입니다. 공사 공고 조사와 기관 발주계획 정리에 사용할 수 있습니다. Python 3.11 이상이 필요합니다.

```bash
python3 setup-lab.py
.venv/bin/python -m sionlab_procurement --help
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python examples/run_examples.py --output /tmp/sionlab-procurement-examples
```

[사용 계약](docs/contract.md) · [서비스 지원 범위](docs/coverage.md) · [기존 도구 대응](docs/migration.md) · [예제](examples/README.md) · [시험 결과](docs/verification.md) · [외부 라이브러리 고지](NOTICE.md)

소스·문서·가상 예제는 SIONLAB이 요구사항과 공식 API 명세를 기준으로 새로 작성했습니다. 기존 제품 코드·문구·수집 프로필·시험을 가져오지 않았습니다. MIT 라이선스의 저작권·허락 고지는 재배포할 때 유지해야 합니다.

## 실행

`DATA_GO_KR_API_KEY`에 공공데이터포털에서 발급한 **디코딩 키**를 프로세스 환경으로 명시 주입합니다. 기존 제품의 인증 파일이나 MCP 연결은 자동 탐색·변경하지 않습니다.

```bash
sionlab-procurement coverage
sionlab-procurement search --query examples/construction-query.json
sionlab-procurement collect --job construction-2026 --query examples/construction-query.json
sionlab-procurement status --job construction-2026
sionlab-procurement collect --job construction-2026
sionlab-procurement serve
```

`serve`는 MCP stdio 서버입니다. 등록 도구는 `sionlab_search`, `sionlab_detail`, `sionlab_collect`, `sionlab_coverage`, `sionlab_job_status` 다섯 개입니다. [연결 설정 양식](examples/mcp-config.json)은 직접 설치한 절대 경로로 바꾸어 사용합니다.

검색·상세는 한 페이지만 읽습니다. `partial=true`는 전체를 확인하지 못했다는 뜻입니다. 수집은 작업 전체 최대 20회, 순차 호출하며 같은 작업을 재개해도 호출 한도를 초기화하지 않습니다. 예산 소진 작업을 자동 연장하지 않습니다. 기간 분할, 페이지·필터 전후 건수, 중복 제거, 저장 위치와 실패 구간을 응답에 구분합니다.

개찰 결과는 최종 낙찰자가 아닐 수 있습니다. 담당자 이름·전화·이메일 및 연락처를 포함할 수 있는 복합 목록 필드는 저장과 반환 전에 제외합니다. 실제 거래 판단에는 공식 원문과 최신 공고를 확인해야 합니다. 원천 API의 데이터가 수집 도중 바뀌면 완전한 시점 스냅샷을 보장할 수 없습니다.

이 버전은 Linux에서 검증합니다. Windows 잠금 구현은 포함하되 실행 검증 여부는 시험 문서를 따릅니다. 원격 게시·업로드·사용 중인 연결 교체는 이 패키지 설치에 포함되지 않습니다.

## 업무용 Excel

```bash
.venv/bin/sionlab-procurement --job-dir /tmp/my-jobs export --job construction-2026 --output /tmp/my-export
```

`records.xlsx`는 공고명·번호·차수·기관·원문 링크가 있는 **Overview**로 열립니다. **Collection**에는 조회 조건·전체 건수·저장 건수·다음 위치·부분수집 사유·UTC 시각이 있습니다. API 키는 포함하지 않습니다. **records / long_values**는 전체 원문 복원용으로 유지합니다. 보기의 빈칸은 값 없음이며 긴 값은 보기만 축약합니다. 표의 원문 링크를 클릭해 공고를 확인할 수 있습니다.

정상 호출한도 중단은 `ok=true, status=paused, partial=true, reason=call_budget_exhausted`입니다. MCP `isError=false`, CLI 종료코드0이지만 전체 수집 완료는 아닙니다. 인증·통신·저장 실패는 여전히 오류입니다. 같은 작업의 호출한도를 자동으로 늘리지 않습니다.

## 설치·지원

```bash
git clone https://github.com/solid-hwan/KONEPS_sionlab.git
cd KONEPS_sionlab
python3 setup-lab.py
```

저장소 설치와 GitHub 릴리스 ZIP을 지원합니다. PyPI 등록을 전제로 한 설치 명령은 제공하지 않습니다. 운영 중인 MCP 설정은 자동 변경하지 않습니다. 재현 가능한 버그는 입력 조건(키 제외)·버전·reason으로 Issues에 남겨 주세요.
