#!/usr/bin/env python3
"""나라장터 자체 MCP 서버 — 물품·용역 외 업무구분까지 커버.

서드파티 MCP 두 개가 다루지 않는 축을 직접 조회한다.

- 물품·용역만 보던 범위를 **공사·외자·기타공고**까지 넓혔다.
- **사전규격**(발주 3~6개월 전 신호), **조달요청**, **계약과정통합공개**를 추가했다.
- **누리장터 민간입찰**(아파트관리사무소·영리법인 등 수요기관 외 주체)을 추가했다.

모든 tool 은 읽기 전용 GET 이다. 데이터를 수정하거나 외부에 연락하지 않는다.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from . import g2b

# 응답에 포함된 담당자 연락처는 개인정보다. tool 응답에서 제외한다 —
# 대화 로그·파일로 흘러 들어가면 회수할 수 없다. 공고 원문 링크로 갈음한다.
_CONTACT_FIELDS = frozenset(
    {
        "ntceInsttOfclNm", "ntceInsttOfclTel", "ntceInsttOfclEmailAdrs",
        "dmndInsttOfclNm", "dmndInsttOfclTel", "dmndInsttOfclEmailAdrs",
        "fnlSucsfCorpOfclNm", "fnlSucsfCorpContactTel", "fnlSucsfCorpCeoNm",
        "bidprcCorpCeoNm", "scsbidCorpCeoNm", "corpCeoNm", "ofclNm", "ofclTel",
    }
)


class Service(str, Enum):
    BID = "bid"
    AWARD = "award"
    PRESPEC = "prespec"
    CONTRACT = "contract"
    LIFECYCLE = "lifecycle"
    REQUEST = "request"
    PRIVATE = "private"
    OPENSTD_BID = "openstd_bid"
    OPENSTD_AWARD = "openstd_award"


class BusinessType(str, Enum):
    GOODS = "물품"
    SERVICE = "용역"
    CONSTRUCTION = "공사"
    FOREIGN = "외자"
    ETC = "기타"
    GENERAL_SERVICE = "일반용역"
    TECH_SERVICE = "기술용역"


class SearchInput(BaseModel):
    """나라장터 공개 API 조회 입력."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    service: Service = Field(
        default=Service.BID,
        description=(
            "조회할 서비스. bid=입찰공고, award=낙찰/개찰결과, prespec=사전규격, "
            "contract=계약정보, lifecycle=계약과정통합, request=조달요청, "
            "private=누리장터 민간입찰, openstd_*=공공데이터개방표준"
        ),
    )
    business_type: BusinessType | None = Field(
        default=None,
        description=(
            "업무구분. 물품·용역·공사·외자·기타 중 하나. 기타공고는 나머지 넷 "
            "어디에도 잡히지 않는 별도 축이다. request 서비스만 일반용역/기술용역으로 "
            "갈린다. openstd_* 계열은 비워 둔다."
        ),
    )
    begin: str = Field(
        ...,
        description="조회 시작 YYYYMMDDHHMM (분 단위). 예: 202609160000",
        pattern=r"^\d{12}$",
    )
    end: str = Field(
        ...,
        description="조회 종료 YYYYMMDDHHMM (분 단위). 예: 202609162359",
        pattern=r"^\d{12}$",
    )
    keyword: str | None = Field(
        default=None,
        description="공고명 부분일치 필터. 서버가 무시하는 경우가 있어 클라이언트에서도 걸러낸다.",
        max_length=100,
    )
    page_no: int = Field(default=1, ge=1, le=1000)
    num_of_rows: int = Field(default=20, ge=1, le=100)
    include_contacts: bool = Field(
        default=False,
        description=(
            "담당자 이름·전화·이메일을 포함할지. 기본 False — 개인정보가 대화 로그에 "
            "남지 않게 한다. 실제 연락이 필요하면 공고 원문 링크로 확인하세요."
        ),
    )


mcp = FastMCP("koneps-sionlab")

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def _scrub(row: dict[str, Any], include_contacts: bool) -> dict[str, Any]:
    if include_contacts:
        return row
    return {k: v for k, v in row.items() if k not in _CONTACT_FIELDS}


def _match_keyword(row: dict[str, Any], keyword: str) -> bool:
    needle = keyword.lower()
    for field in ("bidNtceNm", "prdctClsfcNoNm", "cntrctNm", "reqNm", "prdctNm"):
        value = row.get(field)
        if value and needle in str(value).lower():
            return True
    return False


@mcp.tool(
    name="koneps_search",
    annotations={"title": "나라장터 공개 API 조회 (전 업무구분)", **_READ_ONLY},
)
async def koneps_search(params: SearchInput) -> dict[str, Any]:
    """나라장터 공개 API 를 업무구분별로 조회한다.

    물품·용역에 한정되지 않는다. 공사·외자·기타공고, 사전규격, 조달요청,
    계약과정통합, 누리장터 민간입찰까지 같은 인터페이스로 조회한다.

    서비스마다 지원하는 업무구분이 다르므로 잘못된 조합은 호출 전에 막는다.
    어떤 조합이 가능한지는 ``koneps_coverage`` 로 확인하세요.
    """
    extra: dict[str, Any] = {}
    if params.service is Service.OPENSTD_AWARD and params.business_type:
        code = g2b.OPENSTD_BIZ_CODE.get(params.business_type.value)
        if code:
            extra["bsnsDivCd"] = code

    business = params.business_type.value if params.business_type else None
    # 개방표준 계열은 업무구분 접미사를 쓰지 않는다 (bsnsDivCd 로 거른다).
    if params.service in (Service.OPENSTD_BID, Service.OPENSTD_AWARD):
        business = None

    try:
        result = await asyncio.to_thread(
            g2b.fetch,
            params.service.value,
            business_type=business,
            begin=params.begin,
            end=params.end,
            page_no=params.page_no,
            num_of_rows=params.num_of_rows,
            extra_params=extra or None,
        )
    except g2b.KonepsAPIError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "next_action": "koneps_coverage 로 서비스·업무구분 조합을 확인한 뒤 다시 조회하세요.",
        }

    rows = result["items"]
    filtered_by_keyword = False
    if params.keyword:
        rows = [r for r in rows if _match_keyword(r, params.keyword)]
        filtered_by_keyword = True

    rows = [_scrub(r, params.include_contacts) for r in rows]

    notes = []
    if filtered_by_keyword:
        notes.append(
            "목록 조회의 서버측 키워드 필터는 무시되는 경우가 있어 "
            "현재 페이지 결과를 클라이언트에서 다시 걸렀습니다. "
            "total_count 는 필터 이전 값입니다."
        )
    if not params.include_contacts:
        notes.append("담당자 연락처 필드는 제외했습니다 (include_contacts=true 로 포함).")

    return {
        "status": "ok",
        "service": result["service"],
        "service_label": result["service_label"],
        "operation": result["operation"],
        "business_type": result["business_type"],
        "total_count": result["total_count"],
        "returned": len(rows),
        "page_no": result["page_no"],
        "items": rows,
        "notes": notes,
    }


@mcp.tool(
    name="koneps_coverage",
    annotations={"title": "지원 서비스·업무구분 목록", **_READ_ONLY},
)
async def koneps_coverage() -> dict[str, Any]:
    """조회 가능한 서비스와 업무구분 조합을 반환한다 (API 호출 없음).

    어떤 서비스가 어떤 업무구분을 받는지, 각 서비스의 data.go.kr 활용신청
    번호(public_data_pk)가 무엇인지 알려준다. 서비스별로 활용신청이 따로
    필요하므로 인증 오류가 날 때 이 번호로 신청 상태를 확인하세요.
    """
    return {
        "status": "ok",
        "services": g2b.coverage_report(),
        "notes": [
            "네임스페이스가 서비스마다 다르다 (/ad/, /as/, /ao/). 임의로 바꾸면 "
            "404 가 아니라 400 + returnReasonCode=12 가 온다.",
            "기타공고(Etc)는 물품·용역·공사·외자 어디에도 잡히지 않는 별도 축이다.",
            "누리장터는 수요기관이 아닌 주체(아파트관리사무소·영리법인 등)의 "
            "입찰이라 나라장터와 모집단이 겹치지 않는다.",
            "날짜는 전부 YYYYMMDDHHMM 분 단위다. 계약정보에 일 단위를 주면 "
            "resultCode=06 DATE Format 에러가 난다.",
            "서비스마다 활용신청이 따로 필요하다. 개발계정은 오퍼레이션당 1,000건/일.",
        ],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
