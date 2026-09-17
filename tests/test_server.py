#!/usr/bin/env python3
"""MCP tool 계층 테스트 — `g2b.fetch` 를 스텁으로 바꿔 네트워크를 쓰지 않는다.

`g2b.py`(33개)와 `scoring.py`(25개)는 덮여 있었지만 **그 사이를 잇는 tool
계층은 0개**였다. 특히 v0.3.0 의 `max_pages` 순회와 `rank_by_fit` 연결이
테스트 없이 나갔다.

개인정보 스크러빙도 여기서 고정한다 — 이건 회귀하면 되돌릴 수 없는
종류의 버그다.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from koneps_mcp import g2b, scoring, server
except ModuleNotFoundError as exc:  # pragma: no cover - mcp/pydantic 미설치
    raise unittest.SkipTest(f"MCP 의존성 없음: {exc}") from exc


def run(coro):
    return asyncio.run(coro)


def _page(items, total=100, page_no=1):
    return {
        "service": "bid",
        "service_label": "입찰공고정보",
        "operation": "getBidPblancListInfoServc",
        "business_type": "용역",
        "items": items,
        "total_count": total,
        "page_no": page_no,
        "num_of_rows": len(items),
    }


def _row(name="AI 기반 문서인식 시스템 구축", **extra):
    row = {"bidNtceNo": "R26BK01", "bidNtceNm": name}
    row.update(extra)
    return row


class MultiPageTest(unittest.TestCase):
    """max_pages 순회 — v0.3.0 핵심 기능인데 테스트가 없었다."""

    def test_single_page_by_default(self):
        with mock.patch.object(g2b, "fetch", return_value=_page([_row()] * 2)) as f:
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359", num_of_rows=2)))
        self.assertEqual(f.call_count, 1)
        self.assertEqual(out["pages_read"], 1)

    def test_walks_requested_pages_with_increasing_page_no(self):
        with mock.patch.object(g2b, "fetch", side_effect=[
            _page([_row()] * 2), _page([_row()] * 2), _page([_row()] * 2),
        ]) as f:
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                num_of_rows=2, max_pages=3)))
        self.assertEqual(f.call_count, 3)
        self.assertEqual([c.kwargs["page_no"] for c in f.call_args_list], [1, 2, 3])
        self.assertEqual(out["returned"], 6, "페이지별 행이 누적돼야 한다")
        self.assertEqual(out["pages_read"], 3)

    def test_stops_early_on_short_page(self):
        """요청보다 적게 오면 마지막 페이지다 — 더 호출하면 한도만 쓴다."""
        with mock.patch.object(g2b, "fetch", side_effect=[
            _page([_row()] * 3), _page([_row()]),  # 2번째가 짧다
        ]) as f:
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                num_of_rows=3, max_pages=5)))
        self.assertEqual(f.call_count, 2, "짧은 페이지 후 멈춰야 한다")
        self.assertEqual(out["pages_read"], 2)
        self.assertEqual(out["returned"], 4)

    def test_stops_when_total_count_reached(self):
        """total 이 페이지 크기의 배수면 빈 페이지를 더 부르지 않는다.

        그 추가 호출이 한도 초과로 실패하면 이미 완성된 결과까지
        status=error 로 폐기된다 — 실측으로 확인했다.
        """
        with mock.patch.object(g2b, "fetch", side_effect=[
            _page([_row()] * 2, total=2),
            g2b.KonepsAPIError("한도 초과"),
        ]) as f:
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                num_of_rows=2, max_pages=3)))
        self.assertEqual(f.call_count, 1)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["returned"], 2)

    def test_page_no_is_clamped_to_api_limit(self):
        """page_no + max_pages 가 1000 을 넘으면 받지 않는 페이지를 조회한다."""
        with mock.patch.object(g2b, "fetch",
                               return_value=_page([_row()] * 2, total=99999)) as f:
            run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                num_of_rows=2, page_no=1000, max_pages=5)))
        self.assertEqual([c.kwargs["page_no"] for c in f.call_args_list], [1000])

    def test_collected_is_reported_separately_from_returned(self):
        """"모았습니다" 건수는 필터 이전 값이어야 한다."""
        rows = [_row("AI 플랫폼"), _row("도로 포장")]
        with mock.patch.object(g2b, "fetch", return_value=_page(rows, total=2)):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                num_of_rows=2, max_pages=2, keyword="플랫폼")))
        self.assertEqual(out["collected"], 2)
        self.assertEqual(out["returned"], 1)

    def test_page_offset_respects_explicit_page_no(self):
        with mock.patch.object(g2b, "fetch", side_effect=[
            _page([_row()] * 2), _page([_row()] * 2),
        ]) as f:
            run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                num_of_rows=2, page_no=5, max_pages=2)))
        self.assertEqual([c.kwargs["page_no"] for c in f.call_args_list], [5, 6])


class ScrubTest(unittest.TestCase):
    """개인정보 스크러빙 — 회귀하면 회수 불가능하다."""

    CONTACTS = {
        "ntceInsttOfclNm": "김담당",
        "ntceInsttOfclTel": "TEL-REDACTED",
        "ntceInsttOfclEmailAdrs": "a@b.go.kr",
        "ofclNm": "이담당",
    }

    def test_contacts_removed_by_default(self):
        with mock.patch.object(g2b, "fetch",
                               return_value=_page([_row(**self.CONTACTS)])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        item = out["items"][0]
        for field in self.CONTACTS:
            self.assertNotIn(field, item, f"{field} 가 새어나갔다")

    def test_request_alone_cannot_reveal_contacts(self):
        """tool 입력만으로 개인정보 보호를 끌 수 없어야 한다.

        모델이나 원격 클라이언트가 include_contacts=true 를 넣을 수 있으므로,
        그것만으로 켜지면 공개 배포의 경계가 되지 못한다.
        """
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KONEPS_ALLOW_CONTACTS", None)
            with mock.patch.object(g2b, "fetch",
                                   return_value=_page([_row(**self.CONTACTS)])):
                out = run(server.koneps_search(server.SearchInput(
                    service="bid", business_type="용역",
                    begin="202609160000", end="202609162359",
                    include_contacts=True)))
        self.assertNotIn("ntceInsttOfclTel", out["items"][0])
        self.assertTrue(any("거부" in n for n in out["notes"]))

    def test_operator_env_plus_request_reveals_contacts(self):
        with mock.patch.dict(os.environ, {"KONEPS_ALLOW_CONTACTS": "1"}):
            with mock.patch.object(g2b, "fetch",
                                   return_value=_page([_row(**self.CONTACTS)])):
                out = run(server.koneps_search(server.SearchInput(
                    service="bid", business_type="용역",
                    begin="202609160000", end="202609162359",
                    include_contacts=True)))
        self.assertIn("ntceInsttOfclTel", out["items"][0])

    def test_operator_env_alone_does_not_reveal(self):
        """운영자가 허용해도 요청하지 않으면 제거한다."""
        with mock.patch.dict(os.environ, {"KONEPS_ALLOW_CONTACTS": "1"}):
            with mock.patch.object(g2b, "fetch",
                                   return_value=_page([_row(**self.CONTACTS)])):
                out = run(server.koneps_search(server.SearchInput(
                    service="bid", business_type="용역",
                    begin="202609160000", end="202609162359")))
        self.assertNotIn("ntceInsttOfclTel", out["items"][0])

    def test_nested_contacts_are_scrubbed(self):
        """최상위 키만 보면 contacts[] 가 통과하는데 노트는 '제외했다'고 한다."""
        row = _row(contacts=[{"tel": "T", "email": "e@x.kr", "name": "김담당"}])
        with mock.patch.object(g2b, "fetch", return_value=_page([row])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        self.assertNotIn("contacts", out["items"][0])

    def test_contact_key_variants_are_scrubbed(self):
        """대소문자·구분자 차이와 미등록 별칭도 막는다."""
        row = _row(**{"NtceInstt_Ofcl_Tel": "T", "mngrPhone": "P",
                      "officerEmail": "e@x.kr"})
        with mock.patch.object(g2b, "fetch", return_value=_page([row])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        item = out["items"][0]
        for k in ("NtceInstt_Ofcl_Tel", "mngrPhone", "officerEmail"):
            self.assertNotIn(k, item, f"{k} 가 통과했다")

    def test_note_explains_scrubbing(self):
        with mock.patch.object(g2b, "fetch", return_value=_page([_row()])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        self.assertTrue(any("연락처" in n for n in out["notes"]))

    def test_existing_title_key_is_not_clobbered(self):
        with mock.patch.object(g2b, "fetch",
                               return_value=_page([_row(title="원래 제목")])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        self.assertEqual(out["items"][0]["title"], "원래 제목")

    def test_title_is_injected_from_service_specific_field(self):
        """누리장터는 ntceNm 을 쓴다."""
        row = {"bidNtceNo": "R26BK01", "ntceNm": "석면조사 용역"}
        with mock.patch.object(g2b, "fetch", return_value=_page([row])):
            out = run(server.koneps_search(server.SearchInput(
                service="private", business_type="용역",
                begin="202609160000", end="202609162359")))
        self.assertEqual(out["items"][0]["title"], "석면조사 용역")


class RankingTest(unittest.TestCase):
    def test_not_ranked_by_default(self):
        with mock.patch.object(g2b, "fetch", return_value=_page([_row()])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        self.assertFalse(out["ranked"])
        self.assertNotIn("_match", out["items"][0])

    def test_rank_by_fit_sorts_and_attaches_match(self):
        rows = [_row("도로 포장 공사"), _row("AI 기반 문서인식 시스템 구축")]
        with mock.patch.object(g2b, "fetch", return_value=_page(rows)):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359", rank_by_fit=True)))
        self.assertTrue(out["ranked"])
        scores = [i["_match"]["score"] for i in out["items"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreater(scores[0], 0)

    def test_min_fit_score_filters(self):
        rows = [_row("도로 포장 공사"), _row("OCR 고도화")]
        with mock.patch.object(g2b, "fetch", return_value=_page(rows)):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359",
                rank_by_fit=True, min_fit_score=1.0)))
        self.assertEqual(out["returned"], 1)

    def test_ranking_happens_after_scrubbing(self):
        """점수는 사업명·기관·금액만 보므로 스크러빙 후에도 같아야 한다."""
        row = _row("OCR 고도화", ntceInsttOfclTel="TEL-REDACTED")
        with mock.patch.object(g2b, "fetch", return_value=_page([row])):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359", rank_by_fit=True)))
        self.assertNotIn("ntceInsttOfclTel", out["items"][0])
        self.assertGreater(out["items"][0]["_match"]["score"], 0)


class KeywordFilterTest(unittest.TestCase):
    def test_filters_rows_and_emits_note(self):
        rows = [_row("AI 플랫폼 구축"), _row("도로 포장 공사")]
        with mock.patch.object(g2b, "fetch", return_value=_page(rows, total=2)):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359", keyword="플랫폼")))
        self.assertEqual(out["returned"], 1)
        self.assertEqual(out["total_count"], 2, "total_count 는 필터 이전 값")
        self.assertTrue(any("키워드" in n for n in out["notes"]))

    def test_filter_uses_all_title_fields(self):
        """bidNtceNm 만 보면 누리장터·사전규격 결과가 조용히 0건이 된다."""
        rows = [{"ntceNm": "교통영향평가 용역"}, {"prdctClsfcNoNm": "교통 신호기"}]
        with mock.patch.object(g2b, "fetch", return_value=_page(rows)):
            out = run(server.koneps_search(server.SearchInput(
                service="private", business_type="용역",
                begin="202609160000", end="202609162359", keyword="교통")))
        self.assertEqual(out["returned"], 2)


class ErrorPathTest(unittest.TestCase):
    def test_api_error_becomes_structured_response(self):
        """예외를 그대로 전파하면 MCP 클라이언트가 원인을 알 수 없다."""
        with mock.patch.object(g2b, "fetch",
                               side_effect=g2b.KonepsAPIError("경로 오류")):
            out = run(server.koneps_search(server.SearchInput(
                service="bid", business_type="용역",
                begin="202609160000", end="202609162359")))
        self.assertEqual(out["status"], "error")
        self.assertIn("경로 오류", out["message"])
        self.assertTrue(out["next_action"])


class OpenStdTest(unittest.TestCase):
    def test_business_type_becomes_bsns_div_cd(self):
        with mock.patch.object(g2b, "fetch", return_value=_page([])) as f:
            run(server.koneps_search(server.SearchInput(
                service="openstd_award", business_type="용역",
                begin="202609150000", end="202609152359")))
        kwargs = f.call_args.kwargs
        self.assertEqual(kwargs["extra_params"], {"bsnsDivCd": "5"})
        self.assertIsNone(kwargs["business_type"],
                          "개방표준은 접미사를 쓰지 않는다")


class SchemaTest(unittest.TestCase):
    def test_rejects_unknown_field(self):
        with self.assertRaises(Exception):
            server.SearchInput(service="bid", buisness_type="용역",
                               begin="202609160000", end="202609162359")

    def test_rejects_day_precision_dates(self):
        with self.assertRaises(Exception):
            server.SearchInput(service="bid", business_type="용역",
                               begin="20260916", end="20260916")

    def test_enforces_limits(self):
        for kwargs in ({"num_of_rows": 999}, {"max_pages": 99},
                       {"page_no": 0}, {"min_fit_score": -1}):
            with self.assertRaises(Exception, msg=f"{kwargs} 가 통과됐다"):
                server.SearchInput(service="bid", business_type="용역",
                                   begin="202609160000", end="202609162359",
                                   **kwargs)


class MetaToolTest(unittest.TestCase):
    def test_coverage_lists_every_service(self):
        out = run(server.koneps_coverage())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["services"]), len(g2b.SERVICES))

    def test_rules_reports_profile_source(self):
        out = run(server.koneps_rules())
        self.assertEqual(out["status"], "ok")
        self.assertIn("sionlab-profile", out["source"])


class TitleFieldSyncTest(unittest.TestCase):
    def test_server_and_scoring_share_one_definition(self):
        """두 모듈이 같은 객체를 봐야 한다 — 복사하면 드리프트한다."""
        self.assertIs(server._TITLE_FIELDS, scoring.TITLE_FIELDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
