# 기존 도구와 새 인터페이스 대응

기존 도구 이름은 사용자가 기능 위치를 찾기 위한 식별자 참조입니다. 기존 구현을 호출하거나 외부 코드·문서를 복제한 것이 아닙니다. 연결 설정은 자동으로 바꾸지 않습니다.

| 기존 도구명 | 새 호출 방향 | 차이·제약 |
|---|---|---|
| g2b_search_bids / search_bid_announcements / get_bids_by_keyword | sionlab_search(service=bids) 또는 sionlab_collect | 검색 1페이지; specs를 함께 원하면 별도로 조회 |
| g2b_get_bid_detail / get_bid_detail | sionlab_detail(service=bids, identifiers) | 번호·차수 일치행; 상세 하위항목은 operation별 별도 요청 |
| g2b_search_awards | sionlab_search(service=openings) | 개찰 의미를 명시; 최종낙찰 추정 없음 |
| g2b_get_award_status / search_successful_bids | sionlab_search(service=awards) | 최종낙찰 소스 조회; 예비가격은 해당 operation 직접 선택 |
| g2b_search_contracts / search_contracts | sionlab_search(service=contracts) | 계약 식별자·원문 금액 문자열 보존 |
| g2b_search_pre_specs | sionlab_search(service=specs) | 별도 서비스 호출 |
| g2b_search_plans | sionlab_search(service=plans) | 발주년월·게시기간·기관조건 명시 |
| g2b_search_procurement_requests | sionlab_search(service=requests) | 요청번호를 그대로 보존 |
| g2b_search_prices | sionlab_search(service=prices, operation) | 11개 공식 가격 오퍼레이션 명시 선택; 참고가격 |
| g2b_standard_search | sionlab_search(service=standard, operation) | 표준 전용 날짜명·필수조건 적용 |
| g2b_track_process | sionlab_search(service=process, params) | 시작 번호 필수; 없는 단계를 생성하지 않음 |
| g2b_debug | sionlab_coverage / 키 없는 search 오류 | 키값·키 일부를 반환하지 않음 |
| recommend_bids_for_dept | filters와 서버 params를 사용한 search/collect | 기존 부서 프로필·추천 모델 재사용 없음 |
| analyze_bid_detail | 직접 대응 기능 없음 | 첨부 HWP/PDF/DOCX 본문 분석은 이 제품 범위 밖 |

기존 자동 추천이나 첨부파일 분석까지 다섯 MCP 도구로 제공한다고 표시하지 않습니다. 새 통합 인터페이스의 범위는 공식 조달 데이터 조회·수집과 작업상태 관리입니다.

## v0.3.1 공개본에서 v0.4.0으로

이 저장소의 기존 공개본은 [v0.3.1 태그](https://github.com/solid-hwan/KONEPS_sionlab/tree/v0.3.1)에 그대로 남습니다. 이전 커밋 이력을 다시 쓰지 않습니다. 새 버전의 Python 패키지명은 `sionlab-procurement-mcp`, 모듈명은 `sionlab_procurement`입니다. 기존 `.env`·수집자료·실행 환경을 지우거나 새 버전과 섞지 마세요.

| 기존 자체 MCP | 새 제품 | 전환 시 주의 |
|---|---|---|
| koneps_search | sionlab_search / sionlab_collect | 옛 SearchInput을 그대로 전달하지 않음. service/business/start/end로 지정 |
| koneps_coverage | sionlab_coverage | 공식 등록 범위와 실조회 범위를 구분 |
| koneps_rules | README·docs/contract.md | 같은 이름의 도구는 없음 |
| NARA_API_KEY / .env 자동읽기 | DATA_GO_KR_API_KEY 프로세스 환경 | 디코딩 키를 직접 주입, .env 자동탐색 없음 |
| 기존 .mcp.json·scripts/run-own-mcp.sh | examples/mcp-config.json의 새 모듈 명령 | 사용 클라이언트의 기존 항목을 백업한 뒤 명시 교체 |
| 기타공고 업무구분 | 명시 operation=getBidPblancListInfoEtc | business=etc 별칭은 제공하지 않음 |
| 적합도 정렬·추천 | 직접 대응 없음 | filters는 읽은 페이지 필터이며 추천 점수가 아님 |
| 첨부 분석·통합 상세 | 직접 대응 없음 / 하위 operation 별도 | RFP 파일 분석이나 면허·지역 자동병합을 제공한다고 표시하지 않음 |

1. 기존 설치를 보존하고 새 디렉터리에 v0.4.0을 설치합니다.
2. 키 없이 `.venv/bin/python -m sionlab_procurement coverage`와 가상 예제를 확인합니다.
3. [MCP 설정 예제](../examples/mcp-config.json)의 Python·jobs 절대경로를 바꿉니다. 실제 키는 로컬 환경에만 넣고 저장소에 커밋하지 않습니다.
4. 클라이언트의 기존 MCP 항목을 새 명령으로 교체하고 초기화·5개 도구 목록을 확인합니다. 원래 항목을 함께 켜두면 이름이 비슷한 도구를 혼용할 수 있습니다.
5. 적은 page_size로 검색→상세→수집→상태를 확인합니다. `ok=true`여도 `partial`을 확인합니다.
6. 이전 동작이 필요하면 별도 v0.3.1 설치와 보관한 기존 클라이언트 설정으로 돌아갑니다. 두 버전의 작업 DB를 서로 호환된다고 가정하지 않습니다.

`get_bids_by_keyword`의 공고+사전규격 동시검색은 새 버전에서 service=bids/specs 두 번으로 나눕니다. 기존 추천·첨부 분석은 서드파티 연결이 제공하던 기능이며 새 제품 ZIP에 포함하지 않습니다. 설치 의존성·코드·지원 범위의 독립성을 우선한 변경입니다.
