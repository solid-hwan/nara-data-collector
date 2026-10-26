import json
from pathlib import Path
import tempfile
import unittest
from openpyxl import load_workbook
from sionlab_procurement.export import export_records
from sionlab_procurement.service import normalize


class ExportTests(unittest.TestCase):
    def test_exact_large_amount_formula_nested_and_long_text(self):
        original={'bidNtceNo':'00001','bidNtceOrd':'001','bidNtceNm':'=HYPERLINK("https://invalid")',
                  'presmptPrce':'1234567890123456789012345','nested':{'a':['한글',1]},'long':'문'*40000}
        record=normalize(original,'getBidPblancListInfoCnstwk')
        with tempfile.TemporaryDirectory() as temp:
            manifest=export_records([record],temp);folder=Path(temp)
            self.assertEqual(json.loads((folder/'records.jsonl').read_text())['raw'],original)
            book=load_workbook(folder/'records.xlsx',read_only=True,data_only=False)
            rows=list(book['records'].values);overflow=list(book['long_values'].values)
            restored=''.join(x[3] for x in overflow[1:] if x[1]=='raw')
            self.assertEqual(json.loads(restored),original)
            self.assertEqual(manifest['rows'],1)
            for sheet in book:
                for row in sheet:
                    for cell in row:self.assertNotEqual(cell.data_type,'f')
            book.close()

    def test_offline_examples_execute_and_reopen(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as temp:
            r=subprocess.run([sys.executable,'examples/run_examples.py','--output',temp],capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stderr)
            results=json.loads(r.stdout);self.assertTrue(all(x['excel_reopened'] for x in results));self.assertEqual(len(results),2)
