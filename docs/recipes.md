# 나라장터 데이터 MCP 활용 방법

이 문서는 이미 제공하는 기능을 업무별로 조합하는 예시입니다. 실제 API를 호출하는 명령과 외부 호출 없는 가상 예제를 구분합니다. [README](../README.md)와 [계약](contract.md)을 먼저 확인하세요.

## 1. 키 없이 공사 공고·발주계획 흐름 익히기

```bash
.venv/bin/python examples/run_examples.py --output /tmp/nara-recipes-demo
```

공사 공고와 기관 발주계획을 각각 가상 자료2건으로 수집해 `construction/`, `institution/`에 JSONL·CSV·Excel을 만듭니다. 출력의 `fixture_only`와 `excel_reopened`가 true인지 확인합니다. 고정 날짜·가상 기관코드는 실조회 설정이 아닙니다.

## 2. 특정 분야 공고 조사

`examples/construction-query.json`을 복사해 `service=bids`, `business=construction/goods/services/foreign`, 날짜와 조건을 지정합니다. 아래는 실제 API를 호출하는 흐름이므로 발급 키와 해당 서비스 이용 권한이 있어야 합니다.

```bash
.venv/bin/nara-data-mcp search --query my-query.json
.venv/bin/nara-data-mcp --job-dir ./jobs collect --job review-001 --query my-query.json
.venv/bin/nara-data-mcp --job-dir ./jobs export --job review-001 --output ./output/review-001
```

`filters`는 받은 페이지의 문자열 포함 후처리입니다. 소스 전체의 키워드 검색건수로 해석하지 않습니다. 공식 서버 필터는 `coverage`에서 허용 파라미터를 확인해 `params`에 넣습니다. 번호·차수를 찾은 뒤 상세를 원하면 query에 `identifiers`를 추가해 `detail`을 사용합니다. 모든 하위 상세를 한 번에 조회하지 않습니다.

## 3. 기관 발주계획 정리

`examples/institution-query.json`의 `SYNTHETIC-ORG`를 확인된 실제 기관코드로 바꿉니다. `start/end`는 게시기간, `params.orderBgnYm/orderEndYm`은 발주예정년월입니다. 의미가 다른 두 기간을 구분합니다. 조건을 바꾸려면 새 job ID를 사용합니다.

Excel Collection에서 조건·기간·부분수집·건수를 확인한 뒤 Overview를 업무용 목록으로 활용합니다. 공고·발주계획 자료만으로 계약 확정이나 영업 우선순위를 자동 판단하는 기능은 없습니다.

## 4. 중단 작업 이어가기

```bash
.venv/bin/nara-data-mcp --job-dir ./jobs status --job review-001
.venv/bin/nara-data-mcp --job-dir ./jobs collect --job review-001
```

같은 query를 다시 입력하지 않아도 저장된 조건으로 재개합니다. 작업 전체 예약 횟수와 실패 구간은 유지합니다. 최초 `--max-calls`가20이 아니면 재개에도 같은 값을 넣습니다. 오류 원인이 해결된 경우 `--retry-failed`를 명시할 수 있지만 호출 예산은 늘어나지 않습니다.

## 5. Python 프로그램에 내장하기 — 완전 가상 예제

다음 코드는 외부 HTTP 없이 한 행을 저장하고 Excel·JSONL을 생성합니다. 입력·응답 계약을 시험하거나 사내 분석 스크립트의 연결부를 개발할 때 사용할 수 있습니다.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from nara_data_mcp import Client, Procurement
from sionlab_procurement.export import export_records


def fixture(url, params):
    return {"response": {"header": {"resultCode": "00"}, "body": {
        "totalCount": 1,
        "items": [{"bidNtceNo": "SYNTH-001", "bidNtceOrd": "000", "bidNtceNm": "가상 공고"}]
    }}}


with TemporaryDirectory() as temporary:
    root = Path(temporary)
    service = Procurement(Client(transport=fixture, interval=0), root / "jobs")
    result = service.collect("demo", {
        "service": "bids", "business": "construction",
        "start": "2026-10-01", "end": "2026-10-01", "page_size": 1
    })
    assert result["status"] == "complete" and result["unique_count"] == 1
    export_records(result["data"], root / "export", context=result)
    saved = json.loads((root / "export/records.jsonl").read_text())
    assert saved["raw"]["bidNtceNo"] == "SYNTH-001"
    print({"fixture_only": True, "rows": result["unique_count"]})
```

실제 연결에서는 `Client(key=os.environ["DATA_GO_KR_API_KEY"])`처럼 프로세스 환경의 값을 명시 전달하고, 사용자 요청 범위와 예산을 지정합니다. 키를 코드 리터럴로 쓰지 않습니다.

## 6. 다른 오픈소스 도구와 연결

JSONL의 raw·normalized·missing_reasons를 Python 표준 `json`으로 읽어 자체 집계에 사용하거나 CSV·Excel을 스프레드시트 도구에서 엽니다. 이 저장소가 분석 도구·스케줄러·데이터베이스 서버를 추가 설치하지는 않습니다. 반복 실행은 사용자의 스케줄러에서 한 작업씩 수행하고 상태를 확인해야 합니다. 같은 작업 ID를 반복한다고 최신 자료를 계속 동기화하는 것은 아닙니다.

MCP 연결은 선택입니다. 호환 클라이언트에서 `nara_coverage`로 범위를 읽고 작은 검색·수집 요청을 조합할 수 있습니다. 결과를 요약할 때 원문 건수·읽은 건수·부분수집과 확인되지 않은 범위를 함께 표시합니다.
