import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from openpyxl import load_workbook
from sionlab_procurement import Client, Procurement
from sionlab_procurement.export import export_records
from sionlab_procurement.service import normalize


class ReleaseTests(unittest.TestCase):
    def test_partial_budget_is_success_in_python_stdio_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Procurement(Client(transport=lambda u, p: {'response': {
                'header': {'resultCode': '00'}, 'body': {'totalCount': 3,
                'items': [{'bidNtceNo': 'SYNTH-001', 'bidNtceOrd': '000'}]}}}, interval=0), tmp)
            result = engine.collect('bounded', {'service': 'bids', 'page_size': 1,
                'start':'2026-10-23','end':'2026-10-23'}, max_calls=1)
            self.assertTrue(result['ok'])
            self.assertTrue(result['partial'])
            self.assertEqual(result['status'], 'paused')
            messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
                            'name': 'sionlab_job_status', 'arguments': {'job_id': 'bounded'}}}]
            child = subprocess.run([sys.executable, '-m', 'sionlab_procurement', '--job-dir', tmp, 'serve'],
                input='\n'.join(json.dumps(x) for x in messages)+'\n', text=True, capture_output=True, check=True)
            self.assertFalse(json.loads(child.stdout.splitlines()[-1])['result']['isError'])
            child = subprocess.run([sys.executable, '-m', 'sionlab_procurement', '--job-dir', tmp,
                'collect', '--job', 'bounded', '--max-calls', '1'], capture_output=True, text=True)
            self.assertEqual(child.returncode, 0, child.stdout)
            self.assertEqual(json.loads(child.stdout)['calls_reserved'], 1)

    def test_readable_export_has_links_scope_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = normalize({'bidNtceNo': '0000123', 'bidNtceOrd': '001', 'bidNtceNm': '=SUM(1,2)',
                'ntceInsttNm': '가상기관', 'bidNtceDtlUrl': 'https://example.invalid/notice/1',
                'presmptPrce': '123456789012345678901'}, 'getBidPblancListInfoCnstwk')
            scope = {'status': 'paused', 'partial': True, 'reason': 'call_budget_exhausted',
                     'source_total_count': 3, 'unique_count': 1, 'query': {'service': 'bids'}}
            manifest = export_records([row], tmp, context=scope)
            self.assertTrue(manifest['partial'])
            book = load_workbook(Path(tmp)/'records.xlsx')
            self.assertEqual(book.active.title, 'Overview')
            view = list(book['Overview'].values)
            self.assertIn('공고명', view[0])
            self.assertIn('0000123', view[1])
            self.assertIn('=SUM(1,2)', view[1])
            link = next(c for c in book['Overview'][2] if c.value == 'https://example.invalid/notice/1')
            self.assertEqual(link.hyperlink.target, link.value)
            meta = dict(book['Collection'].values)
            self.assertEqual(json.loads(meta['partial']), True)
            self.assertEqual(json.loads(meta['source_total_count']), 3)
            self.assertEqual(json.loads(book['records']['B2'].value), row['raw'])
            self.assertTrue(all(c.data_type != 'f' for s in book for r in s for c in r))
            book.close()

    def test_failed_collection_stays_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Procurement(Client(transport=lambda u,p: {'ok':False, 'reason':'http_403',
                'blocked':True, 'data':None, 'read_count':None, 'source_total_count':None}, interval=0), tmp)
            result = engine.collect('blocked', {'service':'bids',
                'start':'2026-10-23','end':'2026-10-23'}, max_calls=1)
            self.assertFalse(result['ok'])
            self.assertEqual(result['status'], 'blocked')

    def test_unknown_export_scope_is_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = export_records([], tmp)
            self.assertIsNone(manifest['partial'])
            self.assertEqual(manifest['scope_reason'], 'collection_context_not_provided')

    def test_exhausted_retry_does_not_hide_prior_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Procurement(Client(transport=lambda u,p: {'ok':False, 'reason':'http_403',
                'blocked':True, 'data':None, 'read_count':None, 'source_total_count':None}, interval=0), tmp)
            engine.collect('blocked', {'service':'bids','start':'2026-10-23','end':'2026-10-23'}, max_calls=1)
            result = engine.collect('blocked', max_calls=1, retry_failed=True)
            self.assertFalse(result['ok'])
            self.assertTrue(result['partial'])
            self.assertEqual(result['failed_segments'][0]['reason'], 'http_403')
