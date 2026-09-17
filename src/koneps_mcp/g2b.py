#!/usr/bin/env python3
"""나라장터(KONEPS/G2B) 공개 API 클라이언트.

표준 라이브러리만 사용한다. 이 모듈은 조달청 OpenAPI 의 두 가지 함정을
코드로 고정하는 것이 목적이다.

1. **네임스페이스가 서비스마다 다르다.** `/ad/`, `/as/`, `/ao/` 가 공존하며
   틀리면 404 가 아니라 400 + `returnReasonCode=12` 가 온다. 키 문제로
   오해하기 쉬우므로 `SERVICES` 에 검증된 값만 둔다.
2. **업무구분마다 오퍼레이션이 따로다.** 공사 공고를 물품 오퍼레이션으로
   조회하면 정상 응답이 오지 않는다. 물품·용역 외에 공사·외자·기타공고가
   있고, 기타공고(Etc)는 나머지 넷 어디에도 잡히지 않는다.

전부 2026-09-17 실호출로 확인했다. 읽기 전용(GET)이다.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import __version__

_API_HOST = "https://apis.data.go.kr/1230000"
_TIMEOUT = 40
# 버전을 하드코딩하면 릴리스마다 드리프트한다 (실제로 0.2 로 남아 있었다).
_USER_AGENT = f"koneps-sionlab-mcp/{__version__}"


class KonepsAPIError(RuntimeError):
    """조달청 API 가 오류를 반환했거나 응답을 해석할 수 없을 때."""


# ---------------------------------------------------------------------------
# 서비스 레지스트리 — 네임스페이스는 추측하지 말고 여기서 읽는다.
# publicDataPk 는 data.go.kr 데이터셋 번호 (활용신청 페이지).
# ---------------------------------------------------------------------------
SERVICES: dict[str, dict[str, Any]] = {
    "bid": {
        "label": "입찰공고정보",
        "base": f"{_API_HOST}/ad/BidPublicInfoService",
        "public_data_pk": "15129394",
        "op": "getBidPblancListInfo{suffix}",
        # 기타공고는 물품·용역·공사·외자 어디에도 잡히지 않는 별도 축이다.
        "suffixes": ("Thng", "Servc", "Cnstwk", "Frgcpt", "Etc"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        "date_precision": "minute",
    },
    "award": {
        "label": "낙찰정보(개찰결과)",
        # 주의: /as/ 다. /ad/ 나 /ao/ 로 쓰면 400 이 온다.
        "base": f"{_API_HOST}/as/ScsbidInfoService",
        "public_data_pk": "15129397",
        "op": "getScsbidListSttus{suffix}",
        "suffixes": ("Thng", "Servc", "Cnstwk", "Frgcpt"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        "date_precision": "minute",
    },
    "prespec": {
        "label": "사전규격",
        "base": f"{_API_HOST}/ao/HrcspSsstndrdInfoService",
        "public_data_pk": "15129437",
        "op": "getPublicPrcureThngInfo{suffix}",
        "suffixes": ("Thng", "Servc", "Cnstwk", "Frgcpt"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        "date_precision": "minute",
    },
    "contract": {
        "label": "계약정보",
        "base": f"{_API_HOST}/ao/CntrctInfoService",
        "public_data_pk": "15129427",
        "op": "getCntrctInfoList{suffix}",
        "suffixes": ("Thng", "Servc", "Cnstwk", "Frgcpt"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        # 일 단위(YYYYMMDD)를 주면 resultCode=06 DATE Format 에러가 난다.
        "date_precision": "minute",
    },
    "lifecycle": {
        "label": "계약과정통합공개",
        "base": f"{_API_HOST}/ao/CntrctProcssIntgOpenService",
        "public_data_pk": "15129459",
        "op": "getCntrctProcssIntgOpen{suffix}",
        "suffixes": ("Thng", "Servc", "Cnstwk", "Frgcpt"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        "date_precision": "minute",
    },
    "request": {
        "label": "조달요청",
        "base": f"{_API_HOST}/ao/PrcrmntReqInfoService",
        "public_data_pk": "15129468",
        "op": "getPrcrmntReqInfoList{suffix}",
        # 이 서비스만 용역이 일반용역·기술용역으로 갈린다.
        "suffixes": ("Thng", "GnrlServc", "TechServc", "Cnstwk", "Frgcpt"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        "date_precision": "minute",
    },
    "private": {
        "label": "누리장터 민간입찰공고",
        "base": f"{_API_HOST}/ao/PrvtBidNtceService",
        "public_data_pk": "15129456",
        "op": "getPrvtBidPblancListInfo{suffix}",
        # 누리장터는 수요기관이 아닌 주체(아파트관리사무소·영리법인 등)의
        # 입찰이다. 나라장터와 모집단이 겹치지 않는다.
        "suffixes": ("Thng", "Servc", "Cnstwk", "Etc"),
        "date_params": ("inqryBgnDt", "inqryEndDt"),
        "date_precision": "minute",
    },
    "openstd_bid": {
        "label": "공공데이터개방표준 입찰공고",
        "base": f"{_API_HOST}/ao/PubDataOpnStdService",
        "public_data_pk": "15023680",
        "op": "getDataSetOpnStdBidPblancInfo",
        "suffixes": (),
        "date_params": ("bidNtceBgnDt", "bidNtceEndDt"),
        "date_precision": "minute",
    },
    "openstd_award": {
        "label": "공공데이터개방표준 낙찰",
        "base": f"{_API_HOST}/ao/PubDataOpnStdService",
        "public_data_pk": "15023680",
        "op": "getDataSetOpnStdScsbidInfo",
        "suffixes": (),
        "date_params": ("opengBgnDt", "opengEndDt"),
        "date_precision": "minute",
        # 이 엔드포인트만 최종낙찰 여부(sucsfYn)를 준다. 낙찰 검증에 필수.
        "has_sucsf_yn": True,
        # 2일 이상 요청하면 body 가 통째로 None 이 된다. 하루씩 순회해야 한다.
        "single_day_only": True,
    },
}

# 업무구분 한글명 → 오퍼레이션 접미사.
BUSINESS_SUFFIX: dict[str, str] = {
    "물품": "Thng",
    "용역": "Servc",
    "공사": "Cnstwk",
    "외자": "Frgcpt",
    "기타": "Etc",
    "일반용역": "GnrlServc",
    "기술용역": "TechServc",
}

# 개방표준 서비스의 bsnsDivCd. 업무구분 접미사와 별개 코드 공간이다.
OPENSTD_BIZ_CODE: dict[str, str] = {"공사": "1", "물품": "3", "용역": "5"}


def load_api_key() -> str:
    """`NARA_API_KEY` 를 읽는다.

    공공데이터포털의 '일반 인증키(Decoding)' 를 써야 한다. Encoding 키는
    `%2B`·`%2F` 가 들어 있어 이중 인코딩으로 401 이 된다.
    """
    key = (os.environ.get("NARA_API_KEY") or "").strip()
    if not key:
        raise KonepsAPIError(
            "NARA_API_KEY 가 설정되지 않았습니다. .env.example 을 참고해 .env 를 만드세요."
        )
    if key == "YOUR_DECODED_SERVICE_KEY_HERE":
        raise KonepsAPIError("NARA_API_KEY 가 placeholder 상태입니다. 실제 Decoding 키로 바꾸세요.")
    return key


def resolve_operation(service: str, business_type: str | None) -> str:
    """서비스·업무구분 조합에 맞는 오퍼레이션 이름을 만든다."""
    try:
        spec = SERVICES[service]
    except KeyError:
        raise KonepsAPIError(
            f"알 수 없는 서비스 '{service}'. 사용 가능: {', '.join(sorted(SERVICES))}"
        ) from None

    suffixes: tuple[str, ...] = spec["suffixes"]
    if not suffixes:
        return str(spec["op"])

    if business_type is None:
        raise KonepsAPIError(f"{spec['label']} 는 업무구분이 필요합니다.")

    suffix = BUSINESS_SUFFIX.get(business_type)
    if suffix is None:
        raise KonepsAPIError(
            f"알 수 없는 업무구분 '{business_type}'. 사용 가능: {', '.join(BUSINESS_SUFFIX)}"
        )
    if suffix not in suffixes:
        allowed = [name for name, sfx in BUSINESS_SUFFIX.items() if sfx in suffixes]
        raise KonepsAPIError(
            f"{spec['label']} 는 '{business_type}' 를 지원하지 않습니다. 사용 가능: {', '.join(allowed)}"
        )
    return str(spec["op"]).format(suffix=suffix)


def extract_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    """응답 헤더를 검증하고 items 와 totalCount 를 꺼낸다.

    조달청은 오류를 두 가지 봉투로 보낸다 — 정상 계열은 `response`,
    파라미터 오류는 `nkoneps.com.response.ResponseError`, 경로 오류는
    `OpenAPI_ServiceResponse` 다. 세 번째는 resultCode 가 아니라
    returnReasonCode 를 쓰므로 따로 해석한다.
    """
    gateway = payload.get("OpenAPI_ServiceResponse")
    if isinstance(gateway, dict):
        header = gateway.get("cmmMsgHeader") or {}
        reason = str(header.get("returnReasonCode") or "")
        msg = str(header.get("errMsg") or header.get("returnAuthMsg") or "")
        hint = ""
        if reason == "12":
            hint = " (경로 오류 — 서비스명·오퍼레이션명을 확인하세요. 키 문제가 아닙니다)"
        raise KonepsAPIError(f"조달청 게이트웨이 오류 {reason or '?'}: {msg or '메시지 없음'}{hint}")

    response = payload.get("response") or payload.get("nkoneps.com.response.ResponseError")
    if not isinstance(response, dict):
        raise KonepsAPIError("응답 본문 형식을 확인할 수 없습니다.")

    header = response.get("header") or {}
    code = str(header.get("resultCode") or "")
    message = str(header.get("resultMsg") or "")
    if code not in ("00", "03"):
        hint = ""
        if code == "06":
            hint = " (날짜 형식 — YYYYMMDDHHMM 분 단위로 주세요)"
        elif code == "07":
            # 개방표준 계열은 하루 범위만 받는다. 2일 이상이면 이 코드가 온다.
            hint = " (조회 범위 초과 — 하루씩 나눠 조회하세요)"
        elif code == "08":
            hint = " (필수 파라미터 누락)"
        raise KonepsAPIError(f"조달청 API 오류 {code or '?'}: {message or '메시지 없음'}{hint}")

    body = response.get("body") or {}
    if code == "03":  # 데이터 없음 — 오류가 아니다.
        return [], 0

    items: Any = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item") or [] if "item" in items else [items]
    if not isinstance(items, list):
        items = []

    total = body.get("totalCount")
    try:
        total_int = int(str(total).replace(",", "").strip()) if total not in (None, "") else None
    except ValueError:
        total_int = None
    return [item for item in items if isinstance(item, dict)], total_int


def fetch(
    service: str,
    *,
    business_type: str | None = None,
    begin: str,
    end: str,
    page_no: int = 1,
    num_of_rows: int = 100,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """한 페이지를 조회한다.

    Args:
        service: `SERVICES` 의 키.
        business_type: 물품·용역·공사·외자·기타 등. 개방표준 계열은 None.
        begin: 조회 시작 `YYYYMMDDHHMM`.
        end: 조회 종료 `YYYYMMDDHHMM`.
    """
    # 서비스 유효성은 resolve_operation 이 같은 메시지로 검사한다 (중복 제거).
    operation = resolve_operation(service, business_type)
    spec = SERVICES[service]
    begin_param, end_param = spec["date_params"]

    # 하루 범위만 받는 서비스는 호출 전에 막는다. 그냥 보내면 조달청이
    # resultCode=07 을 주는데, 호출 한도를 쓰고 나서 알게 된다.
    if spec.get("single_day_only") and begin[:8] != end[:8]:
        raise KonepsAPIError(
            f"{spec['label']} 는 하루 범위만 조회할 수 있습니다 "
            f"(요청: {begin[:8]}~{end[:8]}). 하루씩 나눠 호출하세요."
        )

    query: dict[str, Any] = {
        "serviceKey": load_api_key(),
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "type": "json",
        begin_param: begin,
        end_param: end,
    }
    # 개방표준 계열은 inqryDiv 를 받지 않는다.
    if not service.startswith("openstd"):
        query["inqryDiv"] = "1"
    if extra_params:
        query.update(
            {k: str(v) for k, v in extra_params.items() if v not in (None, "")}
        )

    url = f"{spec['base']}/{operation}?{urllib.parse.urlencode(query, safe='')}"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        # 400 본문에 게이트웨이 오류 상세가 담겨 오므로 읽어서 해석한다.
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
        except Exception:
            raise KonepsAPIError(
                f"{operation} 호출 실패: HTTP {exc.code}. 경로·파라미터를 확인하세요."
            ) from exc
    except (OSError, ValueError) as exc:
        raise KonepsAPIError(f"{operation} 호출 실패: {type(exc).__name__}") from exc

    items, total = extract_items(payload)
    return {
        "service": service,
        "service_label": spec["label"],
        "operation": operation,
        "business_type": business_type,
        "items": items,
        "total_count": total,
        "page_no": page_no,
        "num_of_rows": num_of_rows,
    }


def coverage_report() -> list[dict[str, Any]]:
    """등록된 서비스와 지원 업무구분을 표로 낸다(호출 없음)."""
    rows = []
    for name, spec in SERVICES.items():
        suffixes: tuple[str, ...] = spec["suffixes"]
        supported = [k for k, v in BUSINESS_SUFFIX.items() if v in suffixes] or ["해당없음"]
        rows.append(
            {
                "service": name,
                "label": spec["label"],
                "base_url": spec["base"],
                "business_types": supported,
                "public_data_pk": spec["public_data_pk"],
            }
        )
    return rows
