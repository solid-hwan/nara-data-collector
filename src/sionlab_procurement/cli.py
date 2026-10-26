import argparse
import json
import os
from pathlib import Path
from .client import Client, failure
from .service import Procurement


def main(argv=None):
    parser=argparse.ArgumentParser(prog='nara-data-mcp', description='나라장터 데이터 MCP 0.5.0 — 공고·발주계획 검색과 수집')
    parser.add_argument('--job-dir',default=os.environ.get('SIONLAB_JOB_DIR','jobs'))
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('serve',help='MCP stdio server')
    commands.add_parser('coverage',help='official operations and verified scope')
    for name in ('search','detail','collect'):
        cmd=commands.add_parser(name)
        cmd.add_argument('--query',type=Path,required=name!='collect')
        if name=='collect':
            cmd.add_argument('--job',required=True)
            cmd.add_argument('--max-calls',type=int,default=20)
            cmd.add_argument('--retry-failed',action='store_true')
    cmd=commands.add_parser('status');cmd.add_argument('--job',required=True);cmd.add_argument('--include-data',action='store_true')
    cmd=commands.add_parser('export');cmd.add_argument('--job',required=True);cmd.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    service=Procurement(Client(key=os.environ.get('DATA_GO_KR_API_KEY')),args.job_dir)
    if args.command=='serve':
        from .server import serve
        serve(service);return 0
    try:
        query=json.loads(args.query.read_text('utf-8')) if getattr(args,'query',None) else None
        if args.command=='coverage':result=service.coverage()
        elif args.command=='search':result=service.search(**query)
        elif args.command=='detail':result=service.detail(**query)
        elif args.command=='collect':result=service.collect(args.job,query,args.max_calls,args.retry_failed)
        elif args.command=='status':result=service.job_status(args.job,args.include_data)
        elif args.command=='export':
            from .export import export_records
            saved=service.job_status(args.job,True)
            result=export_records(saved['data'],args.output,context=saved) if saved.get('data') is not None else saved
    except (OSError,ValueError,TypeError):
        result=failure('invalid_input_or_local_file')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if result.get('ok') is False else 0
