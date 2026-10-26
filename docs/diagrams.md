# 나라장터 데이터 수집기 — 개발자용 상세 흐름

[처음 사용하는 분을 위한 안내](../README.md#한눈에-보는-사용-흐름)에서는 네 단계로 사용 방법을 설명합니다. 아래 도표는 코드를 연결하거나 수정할 때 참고하는 처리 순서입니다.

## 한눈에 보는 사용 흐름

공고 조사·기관 발주계획 정리·기간별 자료 보관을 같은 도구로 처리합니다. 검색 결과는 JSON으로 읽고, 저장한 작업은 CLI로 Excel·CSV·JSONL을 내보냅니다.

```mermaid
flowchart TD
    A["공고 조사 · 발주계획 정리 · 조달자료 보관"] --> B["조회 조건 작성: 서비스 · 기간 · 기관"]
    B --> C["CLI 또는 Python으로 실행"]
    B --> D["선택: MCP 클라이언트에서 요청"]
    C --> E["나라장터 데이터 수집기"]
    D --> E
    E --> F["search / detail: 한 페이지 JSON"]
    E --> G["collect: 기간별 수집 · SQLite 저장"]
    G --> H["status / collect: 상태 확인 · 같은 작업 재개"]
    G --> I["CLI export"]
    I --> J["Excel: 업무 목록 · 원문 링크"]
    I --> K["JSONL / CSV: 분석 코드 · 다른 도구 연결"]
```

### 수집·재개·Excel 저장 순서

```mermaid
sequenceDiagram
    autonumber
    actor U as 사용자 / MCP 클라이언트
    participant T as 나라장터 데이터 수집기
    participant A as 공식 조달 API
    participant D as SQLite 작업 DB
    participant F as Excel / JSONL / CSV
    U->>T: collect(job_id, 조회 조건)
    T->>D: 작업 조건 · 체크포인트 · 사용 예산 확인
    loop 남은 구간과 호출 예산이 있는 동안
        T->>D: 요청 전에 호출 1회 예약
        T->>A: 공식 오퍼레이션 한 페이지 요청
        A-->>T: 원문 · 원천 건수 또는 오류
        T->>T: 응답 검증 · 연락처 필드 제외
        T->>D: 성공 시 원문과 다음 위치를 함께 저장
    end
    alt 모든 구간 저장 완료
        T-->>U: complete · 저장 건수
    else 호출 예산 소진
        T-->>U: paused · partial=true · 저장 위치
    else 실제 API 실패 또는 차단
        T-->>U: failed 또는 blocked · 오류 사유
    end
    opt 사용자가 같은 작업 재개
        U->>T: collect(같은 job_id)
        T->>D: 저장된 조건 · 남은 위치 · 예산 조회
        Note over T,D: 작업 전체 최대20회 유지 · 소진 예산 자동 연장 없음
    end
    U->>T: CLI export --job 작업ID
    T->>D: 저장 원문 · 상태 읽기
    T->>F: 보기용 시트와 원문 복원 자료 출력
    F-->>U: 업무 검토 · 원문 대조 · 후속 분석
```

실패 작업은 원인을 해결한 뒤 `retry_failed`를 명시해야 합니다. `complete`도 수집 도중 원천이 변하지 않았다는 보증은 아닙니다. MCP는 검색·수집·상태 도구를 제공하며 파일 내보내기는 CLI 또는 Python API를 사용합니다. [시나리오별 활용](recipes.md)에서 실행 명령을 확인하세요.

