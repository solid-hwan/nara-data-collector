"""Bounded sequential HTTP access. Errors never include credential-bearing URLs."""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from .registry import REGISTRY

BLOCK_CODES = {'20', '21', '22', '23', '29', '30', '31', '32', '33'}
PRIVATE = re.compile(r'ofcl|tel|fax|e?mail|phone|mobile|담당|연락|ceonm|rprsntnm|corpList|dminsttList', re.I)


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not PRIVATE.search(k)}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def failure(reason, blocked=False):
    return {'ok': False, 'data': None, 'source_total_count': None,
            'reason': reason, 'blocked': blocked, 'read_count': None}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'redirect_refused', headers, fp)


class Client:
    """transport(url, params) -> decoded JSON is injectable for local contract tests.

    key is never loaded from a file or another product automatically. Native HTTP
    performs one request, with verified TLS and redirects disabled.
    """
    def __init__(self, key=None, *, transport=None, interval=1.0, timeout=30):
        self._key = key
        self.transport = transport
        self.interval = max(0.0, float(interval))
        self.timeout = timeout
        self._last = 0.0
        self._lock = threading.Lock()

    def _fetch(self, url, params):
        query = urllib.parse.urlencode({**params, 'serviceKey': self._key})
        request = urllib.request.Request(url + '?' + query, headers={'User-Agent': 'SIONLAB-Procurement/0.4.0', 'Accept': 'application/json'})
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=self.timeout) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            return failure('response_too_large')
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            # The public gateway returns XML for certain authentication errors.
            try:
                root = ET.fromstring(raw)
                code = root.findtext('.//returnReasonCode') or root.findtext('.//resultCode')
                if code:
                    safe_code = code if re.fullmatch(r'\d{1,3}', code) else 'unknown'
                    return failure('api_error_' + safe_code, safe_code.lstrip('0') in BLOCK_CODES)
            except ET.ParseError:
                pass
            return failure('invalid_json_response')

    def request(self, service, operation, params):
        if self.transport is None and not self._key:
            return failure('missing_api_key', True)
        url = REGISTRY[service]['base_url'] + '/' + operation
        with self._lock:
            pause = self.interval - (time.monotonic() - self._last)
            if pause > 0:
                time.sleep(pause)
            self._last = time.monotonic()
            try:
                payload = self.transport(url, dict(params)) if self.transport else self._fetch(url, params)
            except urllib.error.HTTPError as exc:
                return failure('http_' + str(exc.code), exc.code in (401, 403, 429))
            except (OSError, ValueError, TimeoutError):
                return failure('transport_error')
        if isinstance(payload, dict) and payload.get('ok') is False:
            return payload
        try:
            response = payload['response']
            code = str(response['header']['resultCode'])
            if code not in ('00', '0', '000', '0000'):
                safe_code = code if re.fullmatch(r'\d{1,3}', code) else 'unknown'
                return failure('api_error_' + safe_code, safe_code.lstrip('0') in BLOCK_CODES)
            body = response['body']
            total = body.get('totalCount')
            if total is None or isinstance(total, bool) or not str(total).isdigit():
                return failure('missing_or_invalid_total_count')
            total = int(total)
            items = body.get('items')
            if isinstance(items, dict):
                items = items.get('item', [])
            if items in (None, ''):
                items = []
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list) or any(not isinstance(i, dict) for i in items):
                return failure('invalid_items_shape')
            # An empty body is not success while the source says records exist.
            if not items and total > 0:
                return failure('missing_page')
            if total < len(items):
                return failure('inconsistent_total_count')
            page, size = int(params['pageNo']), int(params['numOfRows'])
            allowed = min(size, max(total - (page - 1) * size, 0))
            if len(items) > allowed:
                return failure('page_item_count_exceeds_reported_total')
            if 'numOfRows' in body and int(body['numOfRows']) != size:
                return failure('page_size_mismatch')
            if 'pageNo' in body and int(body['pageNo']) != int(params['pageNo']):
                return failure('page_number_mismatch')
            return {'ok': True, 'data': scrub(items), 'source_total_count': total,
                    'reason': None, 'blocked': False, 'read_count': len(items)}
        except (KeyError, TypeError, ValueError, AttributeError):
            return failure('malformed_api_response')
