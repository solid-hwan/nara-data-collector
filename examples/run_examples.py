"""Offline synthetic demonstrations: no credentials or external HTTP used."""
import argparse
import json
from pathlib import Path
import tempfile
from openpyxl import load_workbook
from sionlab_procurement import Client, Procurement
from sionlab_procurement.export import export_records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent
    fixtures=json.loads((here/'synthetic-data.json').read_text('utf-8'))
    summary=[]
    for name,query_file in [('construction','construction-query.json'),('institution','institution-query.json')]:
        rows=fixtures[name]
        def transport(url,params):
            page,size=int(params['pageNo']),int(params['numOfRows'])
            return {'response':{'header':{'resultCode':'00'},'body':{'items':rows[(page-1)*size:page*size],'totalCount':len(rows),'pageNo':page}}}
        with tempfile.TemporaryDirectory(prefix='sionlab-procurement-demo-') as job_dir:
            service=Procurement(Client(transport=transport,interval=0),job_dir)
            query=json.loads((here/query_file).read_text('utf-8'))
            result=service.collect(name,query)
            if result['status']!='complete':raise RuntimeError(result['reason'])
            folder=args.output/name;export_records(result['data'],folder,context=result)
            (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            workbook=load_workbook(folder/'records.xlsx',read_only=True,data_only=False)
            table=list(workbook['records'].values)
            assert len(table)-1==result['unique_count']==2
            for excel_row,record in zip(table[1:],result['data']):
                assert json.loads(excel_row[1])==record['raw']
            workbook.close()
            summary.append({'example':name,'fixture_only':True,'source_rows':result['source_total_count'],'read_rows':result['read_count'],
                            'filtered_rows':result['filtered_count'],'saved_rows':result['unique_count'],'excel_reopened':True})
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
