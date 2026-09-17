#!/usr/bin/env python3
"""koneps_mcp.g2b 단위 테스트 — API 를 호출하지 않는다.

여기서 검증하는 것은 '호출 전에 막아야 하는 것'과 '응답 해석'이다.
조달청 API 는 잘못된 조합에도 200 을 주거나 엉뚱한 400 을 주므로,
경로·업무구분 조합과 오류 봉투 해석을 고정해 둔다.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from koneps_mcp import g2b  # noqa: E402


class ServiceRegistryTest(unittest.TestCase):
    def test_namespaces_are_not_uniform(self):
        """/ad/·/as/·/ao/ 가 실제로 갈려 있어야 한다.

        하나로 통일하려는 '정리' 리팩터가 들어오면 이 테스트가 막는다.
        낙찰정보를 /ad/ 로 부르면 400 이 온다 (2026-09-17 실측).
        """
        self.assertIn("/ad/BidPublicInfoService", g2b.SERVICES["bid"]["base"])
        self.assertIn("/as/ScsbidInfoService", g2b.SERVICES["award"]["base"])
        self.assertIn("/ao/HrcspSsstndrdInfoService", g2b.SERVICES["prespec"]["base"])

    def test_bid_service_covers_etc_and_foreign(self):
        """기타공고·외자가 빠지면 물품·용역만 보던 과거로 되돌아간다."""
        suffixes = g2b.SERVICES["bid"]["suffixes"]
        self.assertIn("Etc", suffixes)
        self.assertIn("Frgcpt", suffixes)
        self.assertIn("Cnstwk", suffixes)

    def test_award_service_has_no_etc(self):
        """낙찰정보에는 기타공고 오퍼레이션이 없다 — 있다고 가정하면 400 이다."""
        self.assertNotIn("Etc", g2b.SERVICES["award"]["suffixes"])

    def test_request_service_splits_service_type(self):
        """조달요청만 용역이 일반/기술로 갈린다."""
        suffixes = g2b.SERVICES["request"]["suffixes"]
        self.assertIn("GnrlServc", suffixes)
        self.assertIn("TechServc", suffixes)
        self.assertNotIn("Servc", suffixes)

    def test_openstd_award_is_marked_single_day(self):
        """2일 이상 요청하면 body 가 None 이 되는 함정을 메타데이터로 고정한다."""
        self.assertTrue(g2b.SERVICES["openstd_award"]["single_day_only"])
        self.assertTrue(g2b.SERVICES["openstd_award"]["has_sucsf_yn"])


class ResolveOperationTest(unittest.TestCase):
    def test_resolves_each_business_type(self):
        cases = {
            "물품": "getBidPblancListInfoThng",
            "용역": "getBidPblancListInfoServc",
            "공사": "getBidPblancListInfoCnstwk",
            "외자": "getBidPblancListInfoFrgcpt",
            "기타": "getBidPblancListInfoEtc",
        }
        for business, expected in cases.items():
            self.assertEqual(g2b.resolve_operation("bid", business), expected)

    def test_unsupported_combination_is_rejected(self):
        """낙찰정보+기타 는 실제로 없는 조합이다. 호출 전에 막아야 한다."""
        with self.assertRaises(g2b.KonepsAPIError) as ctx:
            g2b.resolve_operation("award", "기타")
        self.assertIn("기타", str(ctx.exception))

    def test_unknown_business_type_is_rejected(self):
        with self.assertRaises(g2b.KonepsAPIError):
            g2b.resolve_operation("bid", "리스")

    def test_unknown_service_is_rejected(self):
        with self.assertRaises(g2b.KonepsAPIError):
            g2b.resolve_operation("nope", "용역")

    def test_openstd_needs_no_business_type(self):
        self.assertEqual(
            g2b.resolve_operation("openstd_award", None),
            "getDataSetOpnStdScsbidInfo",
        )


class ExtractItemsTest(unittest.TestCase):
    def test_normal_response(self):
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "정상"},
                "body": {"items": [{"bidNtceNo": "R26BK01"}], "totalCount": "1,234"},
            }
        }
        items, total = g2b.extract_items(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(total, 1234, "콤마가 든 totalCount 를 정수로 읽어야 한다")

    def test_no_data_is_not_an_error(self):
        """resultCode=03 은 '데이터 없음'이다. 예외로 만들면 빈 구간이 실패가 된다."""
        payload = {"response": {"header": {"resultCode": "03", "resultMsg": "데이터없음"}}}
        items, total = g2b.extract_items(payload)
        self.assertEqual(items, [])
        self.assertEqual(total, 0)

    def test_gateway_path_error_gets_hint(self):
        """returnReasonCode=12 는 경로 문제다. 키를 의심하게 두면 안 된다."""
        payload = {
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {
                    "errMsg": "NO_OPENAPI_SERVICE_ERROR",
                    "returnAuthMsg": "해당 오픈API 서비스가 없거나 폐기됨",
                    "returnReasonCode": "12",
                }
            }
        }
        with self.assertRaises(g2b.KonepsAPIError) as ctx:
            g2b.extract_items(payload)
        message = str(ctx.exception)
        self.assertIn("경로", message)
        self.assertIn("키 문제가 아닙니다", message)

    def test_date_format_error_gets_hint(self):
        payload = {
            "nkoneps.com.response.ResponseError": {
                "header": {"resultCode": "06", "resultMsg": "DATE Format 에러"}
            }
        }
        with self.assertRaises(g2b.KonepsAPIError) as ctx:
            g2b.extract_items(payload)
        self.assertIn("YYYYMMDDHHMM", str(ctx.exception))

    def test_single_item_dict_is_wrapped(self):
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "정상"},
                "body": {"items": {"bidNtceNo": "R26BK01"}, "totalCount": 1},
            }
        }
        items, _ = g2b.extract_items(payload)
        self.assertEqual(len(items), 1)

    def test_nested_item_key_is_unwrapped(self):
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "정상"},
                "body": {"items": {"item": [{"a": 1}, {"b": 2}]}, "totalCount": 2},
            }
        }
        items, _ = g2b.extract_items(payload)
        self.assertEqual(len(items), 2)

    def test_unrecognized_envelope_raises(self):
        with self.assertRaises(g2b.KonepsAPIError):
            g2b.extract_items({"something": "else"})


class ApiKeyTest(unittest.TestCase):
    def test_missing_key_raises(self):
        import os

        saved = os.environ.pop("NARA_API_KEY", None)
        try:
            with self.assertRaises(g2b.KonepsAPIError):
                g2b.load_api_key()
        finally:
            if saved is not None:
                os.environ["NARA_API_KEY"] = saved

    def test_placeholder_key_raises(self):
        import os

        saved = os.environ.get("NARA_API_KEY")
        os.environ["NARA_API_KEY"] = "YOUR_DECODED_SERVICE_KEY_HERE"
        try:
            with self.assertRaises(g2b.KonepsAPIError):
                g2b.load_api_key()
        finally:
            if saved is None:
                os.environ.pop("NARA_API_KEY", None)
            else:
                os.environ["NARA_API_KEY"] = saved


class CoverageReportTest(unittest.TestCase):
    def test_every_service_is_listed(self):
        rows = g2b.coverage_report()
        self.assertEqual(len(rows), len(g2b.SERVICES))
        for row in rows:
            self.assertTrue(row["base_url"].startswith("https://"))
            self.assertTrue(row["public_data_pk"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
