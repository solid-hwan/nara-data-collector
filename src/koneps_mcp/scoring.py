#!/usr/bin/env python3
"""입찰공고 적합도 점수 — `docs/sionlab-profile.md` 의 룰을 코드로 옮긴 것.

## 왜 이 파일이 있나

추천 룰이 문서에만 있고 `scripts/` 3곳에 서로 다르게 복제돼 있었다.
2026-09-17 측정:

| 키워드 | profile(정본) | keyword_search | match_phase3 | winner_match |
|---|---|---|---|---|
| OCR | 3.0 | 3.0 | 3.0 | 3.0 |
| 문서자동화 | 2.5 | 2.5 | 2.5 | **3.0** |
| AI | 2.0 | 2.5 | 2.0 | **2.5** |
| ERP | 1.5 | 2.0 | 1.5 | **2.0** |
| 산업안전 | 1.5 | 없음 | 1.5 | **없음** |
| RAG·LLM | 없음 | 없음 | 없음 | **3.5** |

어느 쪽도 "정본"이라 부를 수 없는 상태였다. 이 모듈의 `WEIGHTS` 가 profile
문서와 1:1 대응하며, **MCP 서버(`rank_by_fit`)가 쓰는 유일한 구현**이다.
문서를 고치면 여기도 고친다.

주의: `scripts/` 의 세 스크립트는 아직 자체 사본을 갖고 있고 이 모듈을
import 하지 않는다. 일회성 배치용이라 통합은 별도 과제로 남겼다 — MCP
경로로 들어오는 추천은 전부 이 모듈을 지난다.

## 설계 결정

- **점수는 필터가 아니라 신호다.** 낮은 점수도 반환하되 정렬만 한다.
  하드 컷오프를 두면 표현이 다른 공고(예: "지능형 문서처리")를 놓친다.
- **그룹 내 최대 1회만 가산한다.** "AI 인공지능 기반 AI 시스템" 이 3배를
  받으면 제목만 긴 공고가 상위에 온다.
- **대형 SI 감점**은 1인~소규모 기업의 단독 수주 가능성을 반영한다.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# docs/sionlab-profile.md "입찰 매칭 키워드 (가중치)" 표와 1:1 대응.
# 같은 그룹 안에서는 한 번만 가산한다 (동의어 중복 방지).
# ---------------------------------------------------------------------------
WEIGHTS: tuple[tuple[float, tuple[str, ...]], ...] = (
    (3.0, ("OCR", "광학문자인식")),
    (2.5, ("문서인식", "문서 자동화", "문서자동화", "문서지능화")),
    (2.0, ("AI", "인공지능")),
    (2.0, ("데이터 자동화", "데이터자동화", "업무자동화", "업무 자동화", "RPA")),
    (1.8, ("API", "데이터 연계", "오픈API", "오픈 API")),
    (1.5, ("ERP", "CRM", "시스템 구축", "시스템구축")),
    (1.5, ("산업안전", "안전컨설팅", "안전관리")),
    (1.2, ("이미지 인식", "이미지인식", "컴퓨터비전", "컴퓨터 비전")),
)

# 디지털 친화 발주처 (+1.0). profile 의 "기관 보너스" 항목.
DIGITAL_AGENCIES: tuple[str, ...] = (
    "한국지능정보사회진흥원", "NIA",
    "한국인터넷진흥원", "KISA",
    "우정사업본부", "국세청", "조달청",
    "교육청",  # 시·도 교육청 전체
)

AGENCY_BONUS = 1.0
BUDGET_BONUS = 1.0
LARGE_SI_PENALTY = -2.0

# profile "회사 규모상 5천만~5억원대 사업 적합".
BUDGET_MIN = 50_000_000
BUDGET_MAX = 500_000_000
# "60억원 이상 대형 SI 는 단독 수주 비현실적 → 점수 하향".
LARGE_SI_THRESHOLD = 6_000_000_000

# 금액이 담기는 필드는 서비스마다 다르다.
_AMOUNT_FIELDS = (
    "asignBdgtAmt",   # 배정예산
    "presmptPrce",    # 추정가격
    "bdgtAmt",
    "sumAmt",
)

# 사업명이 담기는 필드는 서비스마다 다르다. 이 튜플이 **정본**이며
# server.py 가 import 해서 쓴다 — 양쪽에 복사하면 서비스를 추가할 때 한쪽만
# 고쳐 드리프트한다(누리장터 ntceNm 에서 실제로 겪었다).
TITLE_FIELDS = (
    "bidNtceNm",      # 입찰공고·낙찰
    "ntceNm",         # 누리장터 민간입찰
    "prdctClsfcNoNm", # 사전규격 품명
    "prdctNm",
    "cntrctNm",       # 계약
    "reqNm",          # 조달요청
    "bsnsNm",
)
_TITLE_FIELDS = TITLE_FIELDS  # 하위 호환
_AGENCY_FIELDS = ("ntceInsttNm", "dmndInsttNm", "dminsttNm")


def _text(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    return " ".join(str(row.get(f) or "") for f in fields)


def _term_matcher(term: str) -> re.Pattern[str]:
    """용어에 맞는 정규식을 만든다.

    짧은 영문 약어는 **단어 경계**가 필요하다. 단순 부분문자열로 찾으면
    (2026-09-17 실측):
      - "AI" → "K**AI**ST 최고경영자과정 미국 해외연수" 가 2.0점
      - "AI" → "**AI**oT 스마트플러그" 가 AI 사업으로 오인
    반대로 한글은 경계가 없어 부분문자열이어야 한다 — "문서자동화" 를
    `\\b문서자동화\\b` 로 찾으면 "통합문서자동화사업" 을 놓친다.

    경계 판정은 영문·숫자만 인접을 막는다. "AI기반"(한글 인접)은 통과시키고
    "KAIST"·"AIoT"(영문 인접)는 막는 것이 목적이다.
    """
    if term.isascii() and len(term) <= 4:
        return re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
    return re.compile(re.escape(term), re.IGNORECASE)


# 모듈 로드 시 한 번만 컴파일한다 (행마다 재컴파일하면 수백 건에서 느려진다).
_COMPILED: tuple[tuple[float, tuple[tuple[str, re.Pattern[str]], ...]], ...] = tuple(
    (weight, tuple((t, _term_matcher(t)) for t in terms)) for weight, terms in WEIGHTS
)


def _amount(row: dict[str, Any]) -> int | None:
    for field in _AMOUNT_FIELDS:
        raw = row.get(field)
        if raw in (None, ""):
            continue
        try:
            return int(float(str(raw).replace(",", "").strip()))
        except ValueError:
            continue
    return None


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    """한 공고의 적합도를 계산한다.

    Returns:
        ``{"score": float, "matched": [...], "reasons": [...]}``
        ``matched`` 는 어떤 키워드가 걸렸는지, ``reasons`` 는 보너스·감점 근거다.
        점수만 주면 왜 상위인지 설명할 수 없어 둘 다 반환한다.
    """
    haystack = _text(row, _TITLE_FIELDS)

    score = 0.0
    matched: list[str] = []
    for weight, terms in _COMPILED:
        for term, pattern in terms:
            if pattern.search(haystack):
                score += weight
                matched.append(term)
                break  # 그룹당 1회

    reasons: list[str] = []
    amount = _amount(row)

    # 보너스는 **역량 키워드가 하나라도 걸린 건에만** 적용한다.
    # profile 규칙이 "키워드 가중치 합 + 기관/예산 보너스"이므로 보너스는
    # 가산 수정자이고 단독 자격 근거가 아니다. 이 조건이 없으면
    # (2026-09-17 실측) "남창고등학교 급식용 부식 구입"이 교육청(+1.0) +
    # 적정예산(+1.0) = 2.0 으로 물품 1위가 된다 — 역량과 무관한데도.
    if matched:
        agency = _text(row, _AGENCY_FIELDS)
        hit_agency = next((a for a in DIGITAL_AGENCIES if a in agency), None)
        if hit_agency:
            score += AGENCY_BONUS
            reasons.append(f"디지털 친화 발주처(+{AGENCY_BONUS}): {hit_agency}")

        if amount is not None and BUDGET_MIN <= amount <= BUDGET_MAX:
            score += BUDGET_BONUS
            reasons.append(f"적정 규모(+{BUDGET_BONUS}): {amount:,}원")

    # 대형 SI 감점은 키워드와 무관하게 적용한다 — 역량이 맞아도 단독 수주가
    # 비현실적이라는 신호이므로 상위로 올라오는 것을 막는 것이 목적이다.
    if amount is not None and amount >= LARGE_SI_THRESHOLD:
        score += LARGE_SI_PENALTY
        reasons.append(f"대형 SI({LARGE_SI_PENALTY}): {amount:,}원 — 단독 수주 비현실적")

    return {
        "score": round(score, 2),
        "matched": matched,
        "reasons": reasons,
        "amount": amount,
    }


def rank(rows: list[dict[str, Any]], *, min_score: float = 0.0) -> list[dict[str, Any]]:
    """점수 내림차순으로 정렬한다.

    ``min_score`` 기본값은 0 — 점수가 없는 건도 뒤에 남긴다. 하드 컷오프는
    표현이 다른 공고를 놓치므로 호출자가 명시할 때만 적용한다.
    """
    scored = []
    for row in rows:
        result = score_row(row)
        if result["score"] < min_score:
            continue
        scored.append({**row, "_match": result})
    scored.sort(key=lambda r: r["_match"]["score"], reverse=True)
    return scored


def explain_rules() -> dict[str, Any]:
    """적용 중인 룰을 그대로 반환한다 (호출 없음)."""
    return {
        "source": "docs/sionlab-profile.md",
        "keywords": [
            {"weight": w, "terms": list(t)} for w, t in WEIGHTS
        ],
        "agency_bonus": {"value": AGENCY_BONUS, "agencies": list(DIGITAL_AGENCIES)},
        "budget_bonus": {
            "value": BUDGET_BONUS,
            "range_krw": [BUDGET_MIN, BUDGET_MAX],
        },
        "large_si_penalty": {
            "value": LARGE_SI_PENALTY,
            "threshold_krw": LARGE_SI_THRESHOLD,
        },
        "notes": [
            "같은 키워드 그룹 안에서는 한 번만 가산한다 (동의어 중복 방지).",
            "점수는 필터가 아니라 정렬 신호다. 낮은 점수도 반환한다.",
            "금액 필드는 서비스마다 다르다 — asignBdgtAmt·presmptPrce 순으로 찾는다.",
        ],
    }
