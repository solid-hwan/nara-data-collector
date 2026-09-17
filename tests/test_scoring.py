#!/usr/bin/env python3
"""적합도 점수 테스트 — API 호출 없음.

핵심은 **영문 약어 오탐**이다. "AI" 를 부분문자열로 찾으면 KAIST·AIoT 가
AI 사업으로 올라온다(2026-09-17 실측: KAIST 해외연수가 상위 6위).
반대로 한글은 부분문자열이어야 한다 — 경계를 강제하면
"통합문서자동화사업" 을 놓친다. 이 두 요구가 충돌하므로 고정해 둔다.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from koneps_mcp import scoring  # noqa: E402


class AcronymBoundaryTest(unittest.TestCase):
    def test_ai_does_not_match_inside_other_words(self):
        """KAIST·AIoT 는 AI 사업이 아니다."""
        for title in ("KAIST 최고경영자과정 63기 미국 해외연수 위탁 용역",
                      "AIoT 스마트플러그 서비스 관리 용역"):
            result = scoring.score_row({"bidNtceNm": title})
            self.assertEqual(result["score"], 0.0, f"오탐: {title}")
            self.assertEqual(result["matched"], [])

    def test_ai_matches_when_adjacent_to_korean(self):
        """'AI디지털기반' 은 진짜 AI 사업이다 — 한글 인접은 통과."""
        result = scoring.score_row({"bidNtceNm": "2026년 AI디지털기반 수업혁신"})
        self.assertIn("AI", result["matched"])

    def test_ai_matches_standalone(self):
        result = scoring.score_row({"bidNtceNm": "AI 기반 민원 상담"})
        self.assertIn("AI", result["matched"])

    def test_korean_terms_match_as_substring(self):
        """한글은 경계가 없어 부분문자열이어야 한다."""
        result = scoring.score_row({"bidNtceNm": "통합문서자동화사업 구축"})
        self.assertIn("문서자동화", result["matched"])

    def test_case_insensitive(self):
        result = scoring.score_row({"bidNtceNm": "한국어 ocr 엔진 고도화"})
        self.assertIn("OCR", result["matched"])


class WeightTest(unittest.TestCase):
    def test_group_counts_once_only(self):
        """동의어가 여러 번 나와도 그룹당 1회. 제목 긴 공고가 유리해지면 안 된다."""
        once = scoring.score_row({"bidNtceNm": "AI 시스템"})
        many = scoring.score_row({"bidNtceNm": "AI 인공지능 기반 AI 인공지능 AI"})
        self.assertEqual(once["matched"].count("AI"), 1)
        self.assertEqual(len(many["matched"]), 1)

    def test_multiple_groups_stack(self):
        result = scoring.score_row({"bidNtceNm": "AI 기반 문서인식 시스템 구축"})
        # AI 2.0 + 문서인식 2.5 + 시스템 구축 1.5
        self.assertAlmostEqual(result["score"], 6.0)

    def test_ocr_is_highest_single_keyword(self):
        """profile 상 OCR 이 핵심 차별화(3.0)다."""
        top_weight = max(weight for weight, _ in scoring.WEIGHTS)
        self.assertEqual(top_weight, 3.0)
        top_terms = [t for weight, terms in scoring.WEIGHTS
                     if weight == top_weight for t in terms]
        self.assertIn("OCR", top_terms)


class BonusTest(unittest.TestCase):
    def test_digital_agency_bonus(self):
        result = scoring.score_row(
            {"bidNtceNm": "문서 자동화", "ntceInsttNm": "한국지능정보사회진흥원"})
        self.assertTrue(any("발주처" in r for r in result["reasons"]))

    def test_education_office_counts_as_digital_agency(self):
        result = scoring.score_row(
            {"bidNtceNm": "AI 수업", "ntceInsttNm": "충청남도교육청"})
        self.assertTrue(any("교육청" in r for r in result["reasons"]))

    def test_budget_in_range_gets_bonus(self):
        result = scoring.score_row({"bidNtceNm": "OCR", "asignBdgtAmt": "117700000"})
        self.assertTrue(any("적정 규모" in r for r in result["reasons"]))

    def test_bonus_requires_a_keyword_match(self):
        """역량과 무관한 공고에 보너스만으로 점수를 주면 안 된다.

        실측(2026-09-17): 이 조건이 없으면 "남창고등학교 급식용 부식 구입"이
        교육청(+1.0)+적정예산(+1.0)=2.0 으로 물품 1위가 됐다.
        profile 규칙은 "키워드 가중치 합 + 보너스"이므로 보너스는 수정자다.
        """
        result = scoring.score_row({
            "bidNtceNm": "남창고등학교 급식용 부식 구입",
            "ntceInsttNm": "울산광역시교육청",
            "asignBdgtAmt": "80000000",
        })
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["reasons"], [])

    def test_large_si_penalty_applies_without_keyword(self):
        """감점은 반대다 — 역량이 맞아도 규모가 크면 내려야 한다."""
        result = scoring.score_row({"bidNtceNm": "도로 공사", "asignBdgtAmt": "7000000000"})
        self.assertLess(result["score"], 0)

    def test_large_si_is_penalised(self):
        """60억 이상은 1인 기업 단독 수주가 비현실적이다."""
        result = scoring.score_row({"bidNtceNm": "OCR 구축", "asignBdgtAmt": "7000000000"})
        self.assertTrue(any("대형 SI" in r for r in result["reasons"]))
        self.assertLess(result["score"], 3.0)

    def test_amount_with_commas_parses(self):
        result = scoring.score_row({"bidNtceNm": "OCR", "asignBdgtAmt": "117,700,000"})
        self.assertEqual(result["amount"], 117_700_000)

    def test_falls_back_to_presmpt_prce(self):
        """금액 필드는 서비스마다 다르다."""
        result = scoring.score_row({"bidNtceNm": "OCR", "presmptPrce": "80000000"})
        self.assertEqual(result["amount"], 80_000_000)

    def test_missing_amount_is_not_an_error(self):
        result = scoring.score_row({"bidNtceNm": "OCR"})
        self.assertIsNone(result["amount"])


class RankTest(unittest.TestCase):
    def test_sorts_descending_and_keeps_zero_score(self):
        """0점도 버리지 않는다 — 표현이 다른 공고를 놓치지 않기 위해."""
        rows = [
            {"bidNtceNm": "도로 포장 공사"},
            {"bidNtceNm": "AI 기반 문서인식 시스템 구축"},
            {"bidNtceNm": "인공지능 챗봇"},
        ]
        ranked = scoring.rank(rows)
        self.assertEqual(len(ranked), 3, "0점도 남아야 한다")
        scores = [r["_match"]["score"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("문서인식", ranked[0]["_match"]["matched"])

    def test_min_score_filters_when_asked(self):
        rows = [{"bidNtceNm": "도로 포장"}, {"bidNtceNm": "OCR 고도화"}]
        ranked = scoring.rank(rows, min_score=1.0)
        self.assertEqual(len(ranked), 1)

    def test_original_fields_are_preserved(self):
        ranked = scoring.rank([{"bidNtceNm": "OCR", "bidNtceNo": "R26BK01"}])
        self.assertEqual(ranked[0]["bidNtceNo"], "R26BK01")

    def test_nuri_market_title_field_is_scored(self):
        """누리장터는 ntceNm 을 쓴다. 점수 계산도 이 필드를 봐야 한다."""
        result = scoring.score_row({"ntceNm": "OCR 기반 문서 자동화 용역"})
        self.assertGreater(result["score"], 0)


class ExplainTest(unittest.TestCase):
    def test_explain_reports_the_profile_source(self):
        rules = scoring.explain_rules()
        self.assertIn("sionlab-profile", rules["source"])
        self.assertEqual(len(rules["keywords"]), len(scoring.WEIGHTS))
        self.assertEqual(rules["budget_bonus"]["range_krw"],
                         [scoring.BUDGET_MIN, scoring.BUDGET_MAX])


if __name__ == "__main__":
    unittest.main(verbosity=2)
