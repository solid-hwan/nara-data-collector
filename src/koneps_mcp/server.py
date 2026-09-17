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
import os
from enum import Enum
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from . import g2b, scoring

# 응답에 포함된 담당자 연락처는 개인정보다. tool 응답에서 제외한다 —
# 대화 로그·파일로 흘러 들어가면 회수할 수 없다. 공고 원문 링크로 갈음한다.
#
# 한계: 이 목록은 실제 응답에서 관찰한 필드명을 모은 것이고 구조적으로
# 완전하지 않다. 조달청이 새 이름의 연락처 필드를 추가하거나 새 서비스를
# 붙이면 그대로 통과한다. **서비스를 추가할 때 이 목록도 함께 갱신할 것.**
# 정규식 기반 탐지는 오탐이 많아 채택하지 않았다.
_CONTACT_FIELDS = frozenset(
    {
        "ntceInsttOfclNm", "ntceInsttOfclTel", "ntceInsttOfclEmailAdrs",
        "dmndInsttOfclNm", "dmndInsttOfclTel", "dmndInsttOfclEmailAdrs",
        "fnlSucsfCorpOfclNm", "fnlSucsfCorpContactTel", "fnlSucsfCorpCeoNm",
        "bidprcCorpCeoNm", "scsbidCorpCeoNm", "corpCeoNm", "ofclNm", "ofclTel",
        # 일반 이름 — RFP 본문 추출 계열이 contacts[] 로 이런 키를 쓴다.
        # 이 서버가 직접 만들지는 않지만 필드명이 흔해 방어적으로 넣는다.
        "tel", "email", "telNo", "emailAdrs", "phone", "mobile",
    }
)


# 연락처 노출은 **운영자 환경변수**로만 허용한다.
# tool 입력만으로 켤 수 있으면 모델이나 원격 클라이언트가 스스로 개인정보
# 보호를 끌 수 있어 공개 배포의 경계가 되지 못한다. 서버를 띄우는 사람이
# KONEPS_ALLOW_CONTACTS=1 을 명시해야 include_contacts 가 효력을 갖는다.
def _contacts_allowed_by_operator() -> bool:
    return (os.environ.get("KONEPS_ALLOW_CONTACTS") or "").strip().lower() in (
        "1", "true", "yes",
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
            "남지 않게 한다. **서버 환경변수 KONEPS_ALLOW_CONTACTS=1 이 설정된 "
            "경우에만 효력이 있다** — 이 값만으로는 켜지지 않는다. 실제 연락이 "
            "필요하면 공고 원문 링크로 확인하세요."
        ),
    )
    rank_by_fit: bool = Field(
        default=False,
        description=(
            "적합도 점수로 정렬할지. docs/sionlab-profile.md 의 키워드 가중치 + "
            "기관·예산 보너스 + 대형 SI 감점을 적용하고 각 건에 _match(점수·근거)를 "
            "붙인다. 점수는 필터가 아니라 정렬 신호이므로 낮은 점수도 반환한다."
        ),
    )
    min_fit_score: float = Field(
        default=0.0,
        ge=0.0,
        le=20.0,
        description=(
            "rank_by_fit 과 함께 쓸 때, 이 점수 미만인 건을 제외한다. 기본 0 은 "
            "전부 반환(정렬만) — 표현이 다른 공고를 하드 컷오프로 놓치지 않기 "
            "위해서다. 상위만 보려면 2.0 정도부터 시작하세요."
        ),
    )
    # page_no + max_pages 가 1000 을 넘으면 조달청이 받지 않는 페이지를 조회한다.
    max_pages: int = Field(
        default=1,
        ge=1,
        le=10,
        description=(
            "순회할 페이지 수. 기본 1 — 하루 공고가 500건을 넘는 업무구분이 있어 "
            "1페이지만 보면 추천 모집단이 잘린다. 일일 호출 한도(오퍼레이션당 "
            "1,000건)를 쓰므로 필요한 만큼만 늘리세요."
        ),
    )


mcp = FastMCP("koneps-sionlab")

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


# 키 비교용 정규화 집합 — 대소문자·구분자 차이를 흡수한다.
_CONTACT_KEYS_NORMALIZED = frozenset(
    f.lower().replace("_", "") for f in _CONTACT_FIELDS
)

# 이름에 이 조각이 들어가면 연락처로 본다. 조달청이 새 이름의 필드를
# 추가하거나(_CONTACT_FIELDS 는 관찰 기반 목록이라 완전하지 않다) RFP 추출
# 계열이 contacts[] 를 끼워 보낼 때를 위한 2차 방어선이다.
_CONTACT_NAME_HINTS = ("ofcl", "tel", "phone", "mobile", "email", "ceonm", "contact")


def _is_contact_key(key: str) -> bool:
    normalized = key.lower().replace("_", "")
    if normalized in _CONTACT_KEYS_NORMALIZED:
        return True
    return any(hint in normalized for hint in _CONTACT_NAME_HINTS)


def _scrub(value: Any, include_contacts: bool) -> Any:
    """연락처 필드를 재귀적으로 제거한다.

    최상위 키만 보면 `contacts: [{"tel": ...}]` 같은 중첩 구조가 그대로
    통과하는데, 응답에는 "연락처를 제외했다"고 안내돼 사용자가 안전하다고
    오해한다. dict·list 를 끝까지 내려가며 제거한다.
    """
    if include_contacts:
        return value
    if isinstance(value, dict):
        return {
            k: _scrub(v, include_contacts)
            for k, v in value.items()
            if not _is_contact_key(k)
        }
    if isinstance(value, list):
        return [_scrub(v, include_contacts) for v in value]
    return value


# 사업명 필드 정본은 scoring.TITLE_FIELDS 다. 여기서 다시 선언하면 점수
# 계산과 키워드 필터가 서로 다른 필드를 보게 된다.
_TITLE_FIELDS = scoring.TITLE_FIELDS


def _match_keyword(row: dict[str, Any], keyword: str) -> bool:
    needle = keyword.lower()
    for field in _TITLE_FIELDS:
        value = row.get(field)
        if value and needle in str(value).lower():
            return True
    return False


def title_of(row: dict[str, Any]) -> str | None:
    """서비스별 사업명 필드를 하나로 정규화해 준다."""
    for field in _TITLE_FIELDS:
        value = row.get(field)
        if value:
            return str(value)
    return None


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

    result = None
    rows: list[dict[str, Any]] = []
    pages_read = 0
    collected = 0  # 필터 이전 누적 건수 — returned 와 구분해 보고한다
    try:
        # page_no 상한(1000)을 넘지 않도록 자른다.
        pages_to_read = min(params.max_pages, max(1, 1001 - params.page_no))
        for offset in range(pages_to_read):
            page = await asyncio.to_thread(
                g2b.fetch,
                params.service.value,
                business_type=business,
                begin=params.begin,
                end=params.end,
                page_no=params.page_no + offset,
                num_of_rows=params.num_of_rows,
                extra_params=extra or None,
            )
            if result is None:
                result = page
            pages_read += 1
            rows.extend(page["items"])
            collected += len(page["items"])
            # 마지막 페이지 — 요청한 만큼 안 왔으면 더 없다.
            if len(page["items"]) < params.num_of_rows:
                break
            # total_count 를 다 받았으면 멈춘다. 이 검사가 없으면 전체 건수가
            # 페이지 크기의 배수일 때(예: total=20, 20건씩) 빈 다음 페이지를
            # 한 번 더 호출하고, 그 호출이 한도 초과로 실패하면 **이미 완성된
            # 결과까지 status=error 로 폐기된다**.
            total = result.get("total_count")
            if isinstance(total, int) and (params.page_no - 1) * params.num_of_rows + collected >= total:
                break
    except g2b.KonepsAPIError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "next_action": "koneps_coverage 로 서비스·업무구분 조합을 확인한 뒤 다시 조회하세요.",
        }

    if result is None:
        # max_pages >= 1 이라 도달하지 않지만, assert 로 두면 python -O 에서
        # 사라지고 아래 8개 subscript 가 TypeError 로 터진다. 이 함수의 다른
        # 모든 경로는 구조화된 오류를 반환하므로 여기도 맞춘다.
        return {
            "status": "error",
            "message": "조회 결과를 얻지 못했습니다.",
            "next_action": "기간·서비스·업무구분을 확인한 뒤 다시 조회하세요.",
        }
    filtered_by_keyword = False
    if params.keyword:
        rows = [r for r in rows if _match_keyword(r, params.keyword)]
        filtered_by_keyword = True

    # 사업명 필드가 서비스마다 달라 호출자가 매번 다른 키를 찾아야 했다.
    # 정규화한 title 을 덧붙인다 (원본 필드는 그대로 둔다).
    # 요청이 켜도 운영자가 허용하지 않으면 스크러빙한다.
    reveal_contacts = params.include_contacts and _contacts_allowed_by_operator()
    scrubbed = []
    for row in rows:
        item = _scrub(row, reveal_contacts)
        title = title_of(row)
        if title and "title" not in item:
            item = {"title": title, **item}
        scrubbed.append(item)
    rows = scrubbed

    # 적합도 정렬은 스크러빙 뒤에 한다 — 점수 계산은 사업명·기관명·금액만 보므로
    # 연락처가 빠져도 결과가 달라지지 않는다.
    if params.rank_by_fit:
        rows = scoring.rank(rows, min_score=params.min_fit_score)

    notes = []
    if params.rank_by_fit:
        notes.append(
            "적합도 점수 내림차순입니다. 각 건의 _match 에 점수·매칭 키워드·"
            "보너스 근거가 있습니다. 룰 정본은 docs/sionlab-profile.md 이며 "
            "koneps_rules 로 확인할 수 있습니다."
        )
    if params.max_pages > 1:
        notes.append(
            f"{pages_read}페이지를 순회해 {collected}건을 모았습니다"
            f" (필터 후 {len(rows)}건)."
        )
    if filtered_by_keyword:
        notes.append(
            "목록 조회의 서버측 키워드 필터는 무시되는 경우가 있어 "
            "현재 페이지 결과를 클라이언트에서 다시 걸렀습니다. "
            "total_count 는 필터 이전 값입니다."
        )
    if not reveal_contacts:
        if params.include_contacts:
            notes.append(
                "연락처 포함 요청은 거부했습니다 — 서버에 "
                "KONEPS_ALLOW_CONTACTS=1 이 설정돼 있지 않습니다."
            )
        else:
            notes.append(
                "담당자 연락처 필드는 제외했습니다 (중첩 구조까지 재귀 제거)."
            )

    return {
        "status": "ok",
        "service": result["service"],
        "service_label": result["service_label"],
        "operation": result["operation"],
        "business_type": result["business_type"],
        "total_count": result["total_count"],
        "returned": len(rows),
        "page_no": result["page_no"],
        "pages_read": pages_read,
        "collected": collected,
        "ranked": params.rank_by_fit,
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


@mcp.tool(
    name="koneps_rules",
    annotations={"title": "적합도 점수 룰 확인", **_READ_ONLY},
)
async def koneps_rules() -> dict[str, Any]:
    """`rank_by_fit` 이 쓰는 점수 룰을 반환한다 (API 호출 없음).

    키워드 가중치·기관 보너스·예산 구간·대형 SI 감점 기준을 그대로 보여준다.
    룰 정본은 ``docs/sionlab-profile.md`` 이고 이 모듈이 유일한 구현이다.
    자기 회사에 맞게 쓰려면 ``src/koneps_mcp/scoring.py`` 의 ``WEIGHTS`` 와
    ``DIGITAL_AGENCIES`` 를 고치세요.
    """
    return {"status": "ok", **scoring.explain_rules()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
