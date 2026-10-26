# 서비스 지원 범위

공식 서비스 명세를 등록한 범위와 실제 성공을 확인한 범위는 다릅니다. 2026-10-24 현재 이 패키지는 아래 11개 공식 서비스의 144개 오퍼레이션을 공통 어댑터에 등록했습니다. 입력명 검증·공통 응답 파싱은 구현했으나 모든 오퍼레이션의 특수 업무조건을 실API로 검증한 것은 아닙니다.

| 분류 | service | 등록 오퍼레이션 | 실제 조회 검증 | 공식 근거 |
|---|---|---:|---|---|
| 입찰공고 | `bids` | 25 | `getBidPblancListInfoCnstwk` 각 1건 | [공식 명세](https://www.data.go.kr/data/15129394/openapi.do) |
| 개찰·최종낙찰 | `awards` | 23 | `getOpengResultListInfoCnstwk` 각 1건 | [공식 명세](https://www.data.go.kr/data/15129397/openapi.do) |
| 계약 | `contracts` | 21 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129427/openapi.do) |
| 사전규격 | `specs` | 20 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129437/openapi.do) |
| 발주계획 | `plans` | 8 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129462/openapi.do) |
| 조달요청 | `requests` | 12 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129468/openapi.do) |
| 계약과정 | `process` | 4 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129459/openapi.do) |
| 표준조회 | `standard` | 3 | `getDataSetOpnStdBidPblancInfo` 각 1건, `getDataSetOpnStdCntrctInfo` 각 1건 | [공식 명세](https://www.data.go.kr/data/15058815/openapi.do) |
| 민간개찰·낙찰 | `private_awards` | 7 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129458/openapi.do) |
| 가격 | `prices` | 11 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129415/openapi.do) |
| 민간입찰 | `private` | 10 | 미확인 | [공식 명세](https://www.data.go.kr/data/15129456/openapi.do) |

`openings`는 공식 awards 서비스 안에서 개찰용 기본 오퍼레이션을 선택하는 별칭입니다. 민간입찰과 민간개찰은 서로 다른 공식 서비스이며 따로 등록했습니다.

## 실제 소량 조회

조회일 조건: 2026-10-23 KST. 실행: 2026-10-24T08:08:08.105471+00:00. 실제 네 번 요청, 요청당 한 행입니다. 인증은 기존 값을 메모리로 명시 주입했으며 공유본에는 인증·실측 원문을 포함하지 않습니다.

| 오퍼레이션 | 원천 전체수 | 읽은 수 | 부분조회 |
|---|---:|---:|---|
| `getDataSetOpnStdBidPblancInfo` | 1580 | 1 | true |
| `getOpengResultListInfoCnstwk` | 516 | 1 | true |
| `getDataSetOpnStdCntrctInfo` | 4612 | 1 | true |
| `getBidPblancListInfoCnstwk` | 546 | 1 | true |

[검증 JSON](live-verification.json)의 증거는 이 네 오퍼레이션의 당시 단일 페이지 응답만을 뜻합니다. 전체 공고 수집, 다른 업무구분, 전체 API 이용 권한, 기관 조건 필터의 실제 정확성은 확인하지 않았습니다. 호출 이후 저장·입력 검증의 보강은 로컬 회귀로 시험했고 실제 API를 추가 호출하지 않았습니다.

## 등록 오퍼레이션

아래는 공식 기술 식별자 목록입니다. 기능에 맞는 파라미터 이름은 `sionlab-procurement coverage`의 parameters 또는 패키지 official_operations.json으로 확인합니다. 기본 목록 이외 상세·변경·의견·예비가격 등 하위 오퍼레이션은 명시 선택해야 합니다. 등록 사실만으로 성공·완전성을 보증하지 않습니다.

### 입찰공고

- `getBidPblancListInfoCnstwk`
- `getBidPblancListInfoServc`
- `getBidPblancListInfoFrgcpt`
- `getBidPblancListInfoThng`
- `getBidPblancListInfoThngBsisAmount`
- `getBidPblancListInfoEtcPPSSrch`
- `getBidPblancListPPIFnlRfpIssAtchFileInfo`
- `getBidPblancListBidPrceCalclAInfo`
- `getBidPblancListEvaluationIndstrytyMfrcInfo`
- `getBidPblancListInfoEtc`
- `getBidPblancListInfoEorderAtchFileInfo`
- `getBidPblancListInfoFrgcptPurchsObjPrdct`
- `getBidPblancListInfoServcPurchsObjPrdct`
- `getBidPblancListInfoThngPurchsObjPrdct`
- `getBidPblancListInfoPrtcptPsblRgn`
- `getBidPblancListInfoLicenseLimit`
- `getBidPblancListInfoCnstwkBsisAmount`
- `getBidPblancListInfoThngPPSSrch`
- `getBidPblancListInfoFrgcptPPSSrch`
- `getBidPblancListInfoServcPPSSrch`
- `getBidPblancListInfoCnstwkPPSSrch`
- `getBidPblancListInfoChgHstryServc`
- `getBidPblancListInfoChgHstryCnstwk`
- `getBidPblancListInfoChgHstryThng`
- `getBidPblancListInfoServcBsisAmount`

### 개찰·최종낙찰

- `getScsbidListSttusThng`
- `getOpengResultListInfoFrgcptPPSSrch`
- `getOpengResultListInfoServcPPSSrch`
- `getOpengResultListInfoCnstwkPPSSrch`
- `getOpengResultListInfoThngPPSSrch`
- `getScsbidListSttusFrgcptPPSSrch`
- `getScsbidListSttusServcPPSSrch`
- `getScsbidListSttusCnstwkPPSSrch`
- `getScsbidListSttusThngPPSSrch`
- `getOpengResultListInfoRebid`
- `getOpengResultListInfoFailing`
- `getScsbidListSttusCnstwk`
- `getScsbidListSttusServc`
- `getScsbidListSttusFrgcpt`
- `getOpengResultListInfoThng`
- `getOpengResultListInfoCnstwk`
- `getOpengResultListInfoServc`
- `getOpengResultListInfoFrgcpt`
- `getOpengResultListInfoThngPreparPcDetail`
- `getOpengResultListInfoCnstwkPreparPcDetail`
- `getOpengResultListInfoServcPreparPcDetail`
- `getOpengResultListInfoFrgcptPreparPcDetail`
- `getOpengResultListInfoOpengCompt`

### 계약

- `getCntrctInfoListThng`
- `getCntrctInfoListFrgcptDltHstry`
- `getCntrctInfoListFrgcptChgHstry`
- `getCntrctInfoListFrgcptPPSSrch`
- `getCntrctInfoListFrgcptDetail`
- `getCntrctInfoListFrgcpt`
- `getCntrctInfoListServcDltHstry`
- `getCntrctInfoListServcChgHstry`
- `getCntrctInfoListThngDetail`
- `getCntrctInfoListServcPPSSrch`
- `getCntrctInfoListTechServcServcInfo`
- `getCntrctInfoListGnrlServcServcInfo`
- `getCntrctInfoListServc`
- `getCntrctInfoListCnstwkDltHstry`
- `getCntrctInfoListCnstwkChgHstry`
- `getCntrctInfoListCnstwkPPSSrch`
- `getCntrctInfoListCnstwkServcInfo`
- `getCntrctInfoListCnstwk`
- `getCntrctInfoListThngDltHstry`
- `getCntrctInfoListThngChgHstry`
- `getCntrctInfoListThngPPSSrch`

### 사전규격

- `getPublicPrcureThngInfoThng`
- `getPublicPrcureThngOpinionInfoCnstwk`
- `getPublicPrcureThngOpinionInfoServc`
- `getPublicPrcureThngOpinionInfoFrgcpt`
- `getPublicPrcureThngOpinionInfoThng`
- `getPublicPrcureThngInfoCnstwkPPSSrch`
- `getPublicPrcureThngInfoServcPPSSrch`
- `getPublicPrcureThngInfoFrgcptPPSSrch`
- `getPublicPrcureThngInfoThngPPSSrch`
- `getThngDetailMetaInfoCnstwk`
- `getInsttAcctoThngListInfoCnstwk`
- `getInsttAcctoThngListInfoThng`
- `getPublicPrcureThngInfoCnstwk`
- `getThngDetailMetaInfoServc`
- `getInsttAcctoThngListInfoServc`
- `getThngDetailMetaInfoThng`
- `getPublicPrcureThngInfoFrgcpt`
- `getInsttAcctoThngListInfoFrgcpt`
- `getThngDetailMetaInfoFrgcpt`
- `getPublicPrcureThngInfoServc`

### 발주계획

- `getOrderPlanSttusListThng`
- `getOrderPlanSttusListCnstwk`
- `getOrderPlanSttusListServc`
- `getOrderPlanSttusListFrgcpt`
- `getOrderPlanSttusListThngPPSSrch`
- `getOrderPlanSttusListCnstwkPPSSrch`
- `getOrderPlanSttusListServcPPSSrch`
- `getOrderPlanSttusListFrgcptPPSSrch`

### 조달요청

- `getPrcrmntReqInfoListThng`
- `getPrcrmntReqInfoListFrgcptPPSSrch`
- `getPrcrmntReqInfoListFrgcptDetail`
- `getPrcrmntReqInfoListFrgcpt`
- `getPrcrmntReqInfoListTechServcPPSSrch`
- `getPrcrmntReqInfoListTechServc`
- `getPrcrmntReqInfoListGnrlServcPPSSrch`
- `getPrcrmntReqInfoListGnrlServc`
- `getPrcrmntReqInfoListCnstwkPPSSrch`
- `getPrcrmntReqInfoListCnstwk`
- `getPrcrmntReqInfoListThngPPSSrch`
- `getPrcrmntReqInfoListThngDetail`

### 계약과정

- `getCntrctProcssIntgOpenFrgcpt`
- `getCntrctProcssIntgOpenThng`
- `getCntrctProcssIntgOpenServc`
- `getCntrctProcssIntgOpenCnstwk`

### 표준조회

- `getDataSetOpnStdBidPblancInfo`
- `getDataSetOpnStdScsbidInfo`
- `getDataSetOpnStdCntrctInfo`

### 민간개찰·낙찰

- `getPrvtScsbidListSttus`
- `getPrvtOpengResultListInfo`
- `getPrvtScsbidListSttusPPSSrch`
- `getPrvtOpengResultListInfoPPSSrch`
- `getPrvtOpengResultListInfoOpengCompt`
- `getPrvtOpengResultListInfoFailing`
- `getPrvtOpengResultListInfoRebid`

### 가격

- `getPriceInfoListFcltyCmmnMtrilEngrk`
- `getPriceInfoListFcltyCmmnMtrilBildng`
- `getPriceInfoListFcltyCmmnMtrilMchnEqp`
- `getPriceInfoListFcltyCmmnMtrilElctyIrmc`
- `getPriceInfoListMrktCnstrctPcEngrk`
- `getPriceInfoListMrktCnstrctPcBildng`
- `getPriceInfoListMrktCnstrctPcMchnEqp`
- `getCnsttyClsfcInfoList`
- `getStdMarkUprcinfoList`
- `getPriceInfoListFcltyCmmnMtrilTotal`
- `getNetRsceinfoList`

### 민간입찰

- `getPrvtBidPblancListInfoServc`
- `getPrvtBidPblancListInfoThng`
- `getPrvtBidPblancListInfoCnstwk`
- `getPrvtBidPblancListInfoEtc`
- `getPrvtBidPblancListInfoLicenseLimit`
- `getPrvtBidPblancListInfoPrtcptPsblRgn`
- `getPrvtBidPblancListInfoServcPPSSrch`
- `getPrvtBidPblancListInfoThngPPSSrch`
- `getPrvtBidPblancListInfoCnstwkPPSSrch`
- `getPrvtBidPblancListInfoEtcPPSSrch`

## 명세 해석과 미확인 조건

- 일반 날짜 구간은 보수적으로 최대 7일로 나눕니다. 표준 입찰·계약의 공식 최대 1개월을 넘지 않도록 28일, 표준 개찰은 공식 1주일을 적용합니다.
- 발주계획의 공식 1.1 참고문서에서 기본 조회의 발주년월·게시기간 조건부 필수를 추가 확인했습니다. 웹 Swagger의 required=false만으로 이 조건을 없애지 않았습니다.
- 가격은 참고자료이며 실거래 단가가 아닙니다. 기본 가격 조회에는 날짜 파라미터가 없습니다. 날짜가 필요한 추가 가격 오퍼레이션은 공식 원시 파라미터를 명시합니다.
- 계약과정은 시작 식별자에 연결된 자료를 조회합니다. 모든 단계가 원천에 존재한다는 보장을 하지 않습니다.
- 각종 상세 하위항목의 금액·면허·지역·첨부파일·복수예비가격을 하나의 결과로 자동 병합하지 않습니다. 원천 자료의 의미와 입력 조건은 공식 명세에서 확인해야 합니다.
- 모든 service별 기본 라우팅은 가상 응답으로 시험하며, 나머지 144개 등록명은 식별자/스키마 대응을 검사합니다. 이것을 144개 실API 성공으로 표시하지 않습니다.
