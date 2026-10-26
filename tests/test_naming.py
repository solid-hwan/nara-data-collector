"""명칭 변경 뒤에도 기존 실행·MCP 계약을 보존한다."""
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from nara_data_mcp import Client, Procurement, __version__
from sionlab_procurement.server import call, tools

NAMES = ('search', 'detail', 'collect', 'coverage', 'job_status')


def clean_env():
    return {k: v for k, v in os.environ.items() if k != 'DATA_GO_KR_API_KEY'}


class NamingTests(unittest.TestCase):
    def test_package_and_cli_aliases(self):
        self.assertEqual(importlib.metadata.version('nara-data-mcp'), __version__)
        commands = [[sys.executable, '-m', module] for module in ('nara_data_mcp', 'sionlab_procurement')]
        commands += [[str(Path(sys.executable).parent / name)] for name in ('nara-data-mcp', 'sionlab-procurement')]
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for command in commands:
                help_result = subprocess.run(command + ['--help'], capture_output=True, text=True, check=True, timeout=10)
                self.assertIn('나라장터 데이터 수집기', help_result.stdout)
                self.assertIn('nara-data-mcp', help_result.stdout)
                result = subprocess.run(command + ['--job-dir', tmp, 'coverage'], capture_output=True, text=True, check=True, timeout=10, env=clean_env())
                outputs.append(json.loads(result.stdout))
            self.assertTrue(all(row == outputs[0] for row in outputs))

    def test_only_new_tools_listed_and_all_old_calls_forward_arguments(self):
        advertised = {row['name']: row for row in tools()}
        self.assertEqual(set(advertised), {'nara_' + name for name in NAMES})
        self.assertFalse(advertised['nara_collect']['annotations']['readOnlyHint'])
        for name in NAMES:
            service = Mock()
            method = getattr(service, name)
            method.return_value = {'ok': True, 'fixture': name}
            for prefix in ('nara_', 'sionlab_'):
                self.assertEqual(call(service, prefix + name, {'fixture': '입력'}), method.return_value)
                method.assert_called_with(fixture='입력')
            self.assertEqual(method.call_count, 2)
            self.assertEqual(call(service, 'nara_' + name, []), call(service, 'sionlab_' + name, []))
        self.assertEqual(call(Mock(), 'unlisted_tool', {})['reason'], 'unknown_tool')

    def test_stdio_initialize_list_and_all_aliases(self):
        args = {'search': {'service': 'bids', 'start': '2026-10-23', 'end': '2026-10-23'},
                'detail': {'service': 'bids', 'identifiers': {'bidNtceNo': 'fixture'}, 'start': '2026-10-23', 'end': '2026-10-23'},
                'collect': {'job_id': 'missing-query'}, 'coverage': {}, 'job_status': {'job_id': 'not-found'}}
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        for name in NAMES:
            for prefix in ('nara_', 'sionlab_'):
                messages.append({'jsonrpc': '2.0', 'id': len(messages), 'method': 'tools/call',
                                 'params': {'name': prefix + name, 'arguments': args[name]}})
        with tempfile.TemporaryDirectory() as tmp:
            child = subprocess.run([sys.executable, '-m', 'nara_data_mcp', '--job-dir', tmp, 'serve'],
                input='\n'.join(json.dumps(m) for m in messages)+'\n', text=True, capture_output=True,
                check=True, timeout=15, env=clean_env())
        rows = [json.loads(line)['result'] for line in child.stdout.splitlines()]
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0]['serverInfo'], {'name': 'nara-data-mcp', 'version': __version__})
        self.assertEqual({t['name'] for t in rows[1]['tools']}, {'nara_' + n for n in NAMES})
        for i in range(2, 12, 2):
            self.assertEqual(rows[i], rows[i + 1])
        self.assertEqual(rows[2]['structuredContent']['reason'], 'missing_api_key')
        self.assertTrue(rows[2]['isError'])
        self.assertFalse(rows[8]['isError'])

    def test_old_job_read_and_resume_through_new_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Procurement(Client(transport=lambda u, p: {'response': {'header': {'resultCode': '00'},
                'body': {'totalCount': 2, 'items': [{'bidNtceNo': 'fixture', 'bidNtceOrd': '000'}]}}}, interval=0), tmp)
            original = service.collect('existing', {'service': 'bids', 'page_size': 1,
                'start': '2026-10-23', 'end': '2026-10-23'}, max_calls=1)
            for module in ('nara_data_mcp', 'sionlab_procurement'):
                result = subprocess.run([sys.executable, '-m', module, '--job-dir', tmp,
                    'collect', '--job', 'existing', '--max-calls', '1'], text=True, capture_output=True,
                    check=True, timeout=10, env=clean_env())
                state = json.loads(result.stdout)
                self.assertEqual((state['calls_reserved'], state['unique_count'], state['reason']),
                                 (original['calls_reserved'], original['unique_count'], 'call_budget_exhausted'))
