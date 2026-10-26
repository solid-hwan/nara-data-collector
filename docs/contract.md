# 입출력·저장 계약

검색은 단일 페이지의 관찰 결과입니다. 전체 수집은 `sionlab_collect`로 별도 요청하며 작업 전체 호출 예산을 적용합니다.

## MCP와 Python

| MCP 도구 | Python 메서드 | 핵심 입력 |
|---|---|---|
| sionlab_search | Procurement.search | service, business, operation, start/end, params, page, page_size, filters |
| sionlab_detail | Procurement.detail | service, identifiers + search 입력 |
| sionlab_collect | Procurement.collect | job_id, query, max_calls=20, retry_failed=false |
| sionlab_coverage | Procurement.coverage | 없음 |
| sionlab_job_status | Procurement.job_status | job_id, include_data=false |

`service`는 bids/openings/awards/contracts/specs/plans/requests/prices/process/standard/private/private_awards입니다. `business`는 construction/goods/services/foreign이며 해당 공식 오퍼레이션이 없으면 호출하지 않습니다. 기본 업무는 construction입니다. `operation`에 공식 식별자를 지정하면 기본 선택을 대체합니다. `sionlab_coverage`는 사용할 수 있는 이름과 파라미터 목록을 반환합니다.

`start/end`는 포함 범위인 YYYY-MM-DD입니다. 검색은 일반 7일, 표준 입찰·계약 28일, 표준 개찰 7일을 넘으면 거부합니다. 수집은 같은 정책으로 날짜 구간을 나누고 각 구간에서 페이지 1부터 순회합니다. 날짜 없는 가격·계약과정 조회는 하나의 페이지 구간으로 취급합니다. 원시 날짜 파라미터를 사용하는 검색도 범위를 검사하며, 수집의 자동 기간 분할에는 start/end를 사용합니다.

발주계획 기본 조회는 게시일시(start/end)와 발주예정년월(params.orderBgnYm/orderEndYm)을 **각각** 입력합니다. 두 기간의 의미가 달라 자동으로 같은 달로 바꾸지 않습니다. 공식 발주계획 1.1 참고문서의 조건부 필수 항목을 반영했습니다. 기관 조건도 params.orderInsttCd 등 공식 필드로 명시합니다.

표준 입찰은 bidNtceBgnDt/bidNtceEndDt, 표준 개찰은 opengBgnDt/opengEndDt와 필수 bsnsDivCd, 표준 계약은 cntrctCnclsBgnDate/cntrctCnclsEndDate를 전송합니다. 표준 계약 날짜는 YYYYMMDD입니다. 표준 서비스에 일반 inqryBgnDt/inqryEndDt를 잘못 전달하지 않습니다.

상세는 입력 식별자와 일치하는 행을 한 페이지 안에서 찾습니다. 공고번호·차수는 문자열로 보존합니다. 입찰은 번호조회 구분 2를 적용하며, 그 외 서비스는 공식 조회구분을 `params.inqryDiv`로 명시합니다. 상세 하위항목(기초금액·면허·지역·변경이력)을 자동으로 모두 호출하지 않습니다. 원하는 `operation`을 각각 지정하고 `partial`과 `detail_complete`를 확인합니다.

`filters`는 수신한 행의 지정 필드에 문자열 포함 조건을 적용합니다. 원천 전체 검색건수와 필터 후 전체 건수를 혼동하지 않도록 `total_after_filter=null`과 이유를 반환합니다. 소스가 지원하는 서버 필터는 `params`로 입력합니다. 알 수 없는 파라미터·인증값·페이지 예약 필드는 거부합니다.

## 응답 의미

| 필드 | 의미 |
|---|---|
| ok/reason | 성공 여부와 통제된 오류 코드. 예외 URL·인증값은 반환하지 않음 |
| data | 성공 시 raw/normalized/missing_reasons 배열, 실패 시 null |
| source_total_count | 소스가 보고한 필터 전 총수. 불명 또는 아직 읽지 않은 구간 존재 시 null |
| read_count | 검색: 실제 받은 행수. 수집: 저장 완료된 페이지의 읽은 행수 합계, 중복 포함 |
| filtered_count | 읽은 행에서 후처리 필터 통과 수, 중복 포함 |
| unique_count | SQLite에 저장된 고유 원문 레코드 수 |
| partial/failed_segments | 전체 미완료 여부 및 실패한 기간·페이지·이유 |
| calls_reserved/max_calls | 중단으로 결과가 불명인 요청까지 포함한 작업 전체 예약 수와 상한 |
| checkpoint | 다음에 읽을 구간과 페이지 |
| source_totals_by_segment | 구간별 소스 건수. 미조회 구간은 null |

`raw`는 JSON 수신값 중 담당자 관련 구조화 필드를 제외한 자료입니다. 정규화는 식별자·제목·결과 의미만 분리하며 금액이나 순번을 부동소수점으로 바꾸지 않습니다. 제목이 없으면 null과 source_field_missing을 제공합니다. 자유형 본문에 임의로 포함된 개인정보까지 의미적으로 판별하는 기능은 없으므로 공유 전 검토가 필요합니다.

개찰용 오퍼레이션은 `opening_results_not_final_award`, 최종낙찰 목록은 `final_award_source`로 표시합니다. 순위 1만으로 낙찰 확정을 생성하지 않습니다. 데이터 누락·인증·통신 오류는 정상 0건으로 전환하지 않습니다. 수집 실패 시 반환되는 저장 건수는 이미 커밋한 행의 확정 수이며 실패 응답의 미확인 건수를 포함하지 않습니다.

## 저장·중단·재개

한 job_id는 하나의 SQLite 파일과 불변 query에 대응합니다. params·기관·기간·필터·페이지 크기를 바꾸면 query_mismatch_use_new_job_id입니다. query를 생략하면 저장된 조건으로 재개합니다. DB와 함께 `.lock` 파일을 사용하며 실행 중 동시 접근은 job_busy로 거부합니다.

호출 한도는 네트워크 요청 **직전** 예약하여 커밋합니다. 응답을 받은 뒤 레코드·페이지 완료·다음 커서를 한 트랜잭션으로 저장합니다. 저장 직전 종료되면 같은 페이지를 재조회하며, 저장 직후 종료되면 다음 위치부터 이어갑니다. 두 경우 모두 동일 원문 중복 저장을 막습니다. 요청 후 저장 전 종료는 이미 사용된 호출인지 알 수 없으므로 예약 수를 돌려주지 않습니다.

모든 공식 하위목록의 고유성은 하나의 공고번호로 단정할 수 없습니다. service+operation+연락처 제외 **원문 전체**의 해시로 같은 레코드만 합칩니다. 계약 차수·동일 공고의 서로 다른 참가업체·변경된 원문은 별도 보존합니다. API가 수집 중 데이터를 삽입·삭제하면 페이지 오프셋이 이동할 수 있습니다. 총수 변화·반복 페이지·중간 빈/짧은 페이지는 중단하지만, 소스가 변하지 않았다는 완전한 보장은 없습니다.

기본 20회는 재개를 포함한 평생 상한입니다(1~20 선택 가능). 소진된 같은 job_id는 더 호출하지 않습니다. 더 넓은 기간은 사용자가 기간을 나누어 별도 작업을 만들어야 하며 자동 예산 우회는 하지 않습니다. 다른 budget으로 같은 작업을 재개하는 것도 거부합니다. 인증·권한·할당량·차단은 즉시 멈추고 자동 재시도하지 않습니다. 원인이 해결되었을 때만 `retry_failed=true`를 명시합니다. CLI는 `--retry-failed`입니다.

## 출력

`export`는 저장한 작업을 JSONL·CSV·XLSX로 출력합니다. JSONL이 원문 대조용 정본입니다. CSV와 Excel의 열은 record_index/raw/normalized/missing_reasons로 고정하고 내부 필드명을 JSON에 보존하므로 열 이름 충돌이 없습니다. XLSX는 문자열 셀로 작성하여 수식을 실행하지 않으며, 큰 금액·중첩 값도 JSON 문자열 안에 정확히 남습니다. 32,000자를 넘는 셀은 long_values 시트에 순서대로 분할하여 무음 절단하지 않습니다. 시트명은 고정되어 시트명 충돌을 만들지 않습니다.

## 0.4.0 상태와 Excel 보기

`ok`는 요청 처리 성공 여부이며 수집 완료 여부가 아닙니다. 정상 호출한도 소진은 `ok=true`, `status=paused`, `partial=true`입니다. 실제 실패·차단은 `ok=false`를 유지합니다. 상태조회에서 `created_at`·`updated_at`은 UTC ISO 시각이며 이전 작업에 없으면 null입니다.

Excel 첫 시트 Overview는 읽기용이고 Collection은 작업 조건·상태·원천 전체수·내보낸 행수·시각을 표시합니다. 기존 records/long_values와 JSONL은 복원 계약을 유지합니다. 직접 `export_records(records, path)`를 호출해 작업 맥락을 주지 않았으면 partial은 null, scope_reason은 collection_context_not_provided입니다. CLI export는 저장 상태를 자동 전달합니다.
