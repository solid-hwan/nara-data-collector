#!/usr/bin/env python3
"""g2b.fetch() 테스트 — urlopen 을 가로채므로 네트워크를 쓰지 않는다.

fetch() 가 URL 을 조립하고 HTTP 오류를 해석하는 부분은 가장 위험한데
네트워크 의존 때문에 테스트가 비어 있었다. urllib 을 스텁으로 바꿔
일일 호출 한도를 쓰지 않고 고정한다.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from koneps_mcp import g2b  # noqa: E402

_OK_BODY = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "정상"},
        "body": {"items": [{"bidNtceNo": "R26BK01", "bidNtceNm": "AI 플랫폼 구축"}],
                 "totalCount": 42},
    }
}


class _Resp(io.BytesIO):
    """urlopen 컨텍스트 매니저 흉내."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _stub(body: dict) -> mock.Mock:
    return mock.Mock(side_effect=lambda req, timeout=None: _Resp(json.dumps(body).encode()))


def _captured_url(patched: mock.Mock) -> str:
    return patched.call_args.args[0].full_url


class FetchUrlTest(unittest.TestCase):
    def setUp(self):
        self.key_patch = mock.patch.object(g2b, "load_api_key", return_value="TESTKEY")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

    def test_builds_expected_url_for_each_namespace(self):
        """서비스별 네임스페이스가 URL 에 그대로 반영돼야 한다."""
        cases = [
            ("bid", "용역", "/ad/BidPublicInfoService/getBidPblancListInfoServc"),
            ("award", "외자", "/as/ScsbidInfoService/getScsbidListSttusFrgcpt"),
            ("prespec", "물품", "/ao/HrcspSsstndrdInfoService/getPublicPrcureThngInfoThng"),
            ("private", "기타", "/ao/PrvtBidNtceService/getPrvtBidPblancListInfoEtc"),
        ]
        for service, business, expected_path in cases:
            with mock.patch.object(g2b.urllib.request, "urlopen", _stub(_OK_BODY)) as patched:
                g2b.fetch(service, business_type=business,
                          begin="202609160000", end="202609162359")
            self.assertIn(expected_path, _captured_url(patched))

    def test_openstd_omits_inqry_div_but_others_include_it(self):
        """개방표준 계열은 inqryDiv 를 받지 않는다. 넣으면 응답이 달라진다."""
        with mock.patch.object(g2b.urllib.request, "urlopen", _stub(_OK_BODY)) as patched:
            g2b.fetch("openstd_award", begin="202609150000", end="202609152359")
        self.assertNotIn("inqryDiv", _captured_url(patched))

        with mock.patch.object(g2b.urllib.request, "urlopen", _stub(_OK_BODY)) as patched:
            g2b.fetch("bid", business_type="용역",
                      begin="202609160000", end="202609162359")
        self.assertIn("inqryDiv=1", _captured_url(patched))

    def test_service_specific_date_param_names(self):
        """개방표준 낙찰은 opengBgnDt 를, 입찰공고는 inqryBgnDt 를 쓴다."""
        with mock.patch.object(g2b.urllib.request, "urlopen", _stub(_OK_BODY)) as patched:
            g2b.fetch("openstd_award", begin="202609150000", end="202609152359")
        url = _captured_url(patched)
        self.assertIn("opengBgnDt=202609150000", url)
        self.assertNotIn("inqryBgnDt", url)

    def test_api_key_is_sent_but_blank_extras_are_dropped(self):
        with mock.patch.object(g2b.urllib.request, "urlopen", _stub(_OK_BODY)) as patched:
            g2b.fetch("bid", business_type="용역", begin="202609160000",
                      end="202609162359", extra_params={"bidNtceNm": "", "keep": "yes"})
        url = _captured_url(patched)
        self.assertIn("serviceKey=TESTKEY", url)
        self.assertIn("keep=yes", url)
        self.assertNotIn("bidNtceNm", url, "빈 파라미터는 보내지 않아야 한다")

    def test_returns_parsed_items_and_total(self):
        with mock.patch.object(g2b.urllib.request, "urlopen", _stub(_OK_BODY)):
            out = g2b.fetch("bid", business_type="용역",
                            begin="202609160000", end="202609162359")
        self.assertEqual(out["total_count"], 42)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["operation"], "getBidPblancListInfoServc")
        self.assertEqual(out["business_type"], "용역")


class FetchErrorTest(unittest.TestCase):
    def setUp(self):
        self.key_patch = mock.patch.object(g2b, "load_api_key", return_value="TESTKEY")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

    def test_http_400_with_gateway_envelope_raises_path_hint(self):
        """400 본문의 게이트웨이 오류를 읽어 '경로 문제'로 알려야 한다.

        조용히 빈 결과를 돌려주면 사용자가 '데이터가 없다'고 오해한다.
        """
        body = json.dumps({
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {
                    "errMsg": "NO_OPENAPI_SERVICE_ERROR",
                    "returnReasonCode": "12",
                }
            }
        }).encode()
        err = urllib.error.HTTPError("http://x", 400, "Bad Request", {}, io.BytesIO(body))
        with mock.patch.object(g2b.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(g2b.KonepsAPIError) as ctx:
                g2b.fetch("bid", business_type="용역",
                          begin="202609160000", end="202609162359")
        self.assertIn("경로", str(ctx.exception))

    def test_http_400_with_unparseable_body_still_raises(self):
        err = urllib.error.HTTPError("http://x", 400, "Bad Request", {},
                                     io.BytesIO(b"<html>nope</html>"))
        with mock.patch.object(g2b.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(g2b.KonepsAPIError) as ctx:
                g2b.fetch("bid", business_type="용역",
                          begin="202609160000", end="202609162359")
        self.assertIn("400", str(ctx.exception))

    def test_network_failure_raises_koneps_error(self):
        with mock.patch.object(g2b.urllib.request, "urlopen",
                               side_effect=OSError("timed out")):
            with self.assertRaises(g2b.KonepsAPIError):
                g2b.fetch("bid", business_type="용역",
                          begin="202609160000", end="202609162359")

    def test_api_key_never_appears_in_error_message(self):
        """예외 메시지에 키가 새면 로그·이슈 리포트로 유출된다."""
        with mock.patch.object(g2b.urllib.request, "urlopen",
                               side_effect=OSError("boom")):
            try:
                g2b.fetch("bid", business_type="용역",
                          begin="202609160000", end="202609162359")
            except g2b.KonepsAPIError as exc:
                self.assertNotIn("TESTKEY", str(exc))
            else:
                self.fail("예외가 발생해야 한다")

    def test_bad_combination_raises_before_any_request(self):
        """호출 전에 막아야 일일 한도를 낭비하지 않는다."""
        with mock.patch.object(g2b.urllib.request, "urlopen") as patched:
            with self.assertRaises(g2b.KonepsAPIError):
                g2b.fetch("award", business_type="기타",
                          begin="202609160000", end="202609162359")
        patched.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
