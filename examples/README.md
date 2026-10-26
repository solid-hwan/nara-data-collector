# 가상 업무 예제

두 예제는 실제 기관·고객·공고·입찰금액과 관계없는 자료입니다. 인증 없이 메모리의 가상 API 응답을 사용합니다.

```bash
.venv/bin/python examples/run_examples.py --output /tmp/nara-data-mcp-demo
```

| 예제 | 입력 | 예상 결과 | Excel |
|---|---|---|---|
| 건설사 공고 조사 | [조회조건](construction-query.json), synthetic-data.json의 construction | 전체 3행을 2페이지로 읽고 제목 보수 조건 2행 저장 | [샘플](samples/construction/records.xlsx) |
| 기관 발주계획 조사 | [조회조건](institution-query.json), synthetic-data.json의 institution | 원문 2행 저장, 20자리 금액도 문자열로 보존 | [샘플](samples/institution/records.xlsx) |

각 결과 폴더에는 JSONL, CSV, XLSX, manifest.json, result.json이 있습니다. 실행 스크립트는 Excel을 다시 열어 원문 JSON과 행수를 대조합니다. 샘플 결과는 정적 첨부이며 실행할 때는 새 output 경로를 사용하세요.

건설사 예제는 후보 공고 목록을 좁히는 흐름입니다. 참가자격·첨부 문서·수정공고 전체를 확인한 결과가 아니므로 적격 여부를 판단하지 않습니다. 기관 예제는 발주예정년월과 게시기간을 서로 다른 입력으로 보존합니다. `SYNTHETIC-ORG`는 실API에 사용할 기관코드가 아닙니다.

실제 조회를 실행하려면 명시적으로 인증을 주입하고 날짜·기관코드를 원하는 공식 값으로 바꾸어 CLI search/collect를 실행합니다. 기존 MCP 설정이나 인증 파일을 자동 검색하지 않습니다. API 권한·데이터 존재 여부·페이지 전체 수집은 가상 예제로 증명하지 않습니다.
