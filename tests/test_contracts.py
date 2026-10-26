import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from sionlab_procurement import Client, Procurement
from sionlab_procurement.client import scrub
from sionlab_procurement.registry import REGISTRY
from sionlab_procurement.service import normalize, record_key


def payload(rows,total=None,code='00',page=None):
    body={'items':rows,'totalCount':len(rows) if total is None else total}
    if page is not None:body['pageNo']=page
    return {'response':{'header':{'resultCode':code},'body':body}}


def row(i,**kw):
    return {'bidNtceNo':f'SYNTH-{i}','bidNtceOrd':'000','bidNtceNm':'가상 공사',**kw}


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.query={'service':'bids','start':'2026-10-01','end':'2026-10-01','page_size':2}

    def service(self,transport):
        return Procurement(Client(transport=transport,interval=0),self.tmp.name)

    def test_one_page_counts_and_filter(self):
        s=self.service(lambda u,p:payload([row(1),row(2,bidNtceNm='용역')],8))
        r=s.search(**self.query,filters={'bidNtceNm':'공사'})
        self.assertEqual((r['source_total_count'],r['read_count'],r['filtered_count']),(8,2,1))
        self.assertTrue(r['partial']);self.assertIsNone(r['total_after_filter'])

    def test_privacy_nested_and_identifiers(self):
        s=self.service(lambda u,p:payload([row(1,ntceInsttOfclNm='PRIVATE',telNo='PRIVATE',nested={'email':'PRIVATE','safe':'ok'},corpList='PRIVATE')]))
        r=s.search(**self.query);text=json.dumps(r)
        self.assertNotIn('PRIVATE',text);self.assertEqual(r['data'][0]['normalized']['identifiers']['bidNtceOrd'],'000')

    def test_no_key_is_null(self):
        r=Procurement(Client()).search(**self.query)
        self.assertFalse(r['ok']);self.assertIsNone(r['data']);self.assertIsNone(r['read_count']);self.assertEqual(r['reason'],'missing_api_key')

    def test_codes_and_single_item(self):
        for code in ('00','0000'):
            r=self.service(lambda u,p:payload({'item':row(1)},1,code)).search(**self.query)
            self.assertTrue(r['ok']);self.assertEqual(r['read_count'],1)

    def test_gateway_errors_never_success_zero(self):
        for code in ('20','22','23','29','30','31','01'):
            r=self.service(lambda u,p:payload([],0,code)).search(**self.query)
            self.assertIsNone(r['data']);self.assertIsNone(r['source_total_count'])
            self.assertEqual(r['blocked'],code!='01')

    def test_empty_success_vs_missing_page(self):
        self.assertTrue(self.service(lambda u,p:payload([],0)).search(**self.query)['ok'])
        r=self.service(lambda u,p:payload([],8)).search(**self.query)
        self.assertFalse(r['ok']);self.assertEqual(r['reason'],'missing_page')

    def test_missing_total_and_wrong_page(self):
        r=self.service(lambda u,p:{'response':{'header':{'resultCode':'00'},'body':{'items':[]}}}).search(**self.query)
        self.assertEqual(r['reason'],'missing_or_invalid_total_count')
        r=self.service(lambda u,p:payload([row(1)],1,page=9)).search(**self.query)
        self.assertEqual(r['reason'],'page_number_mismatch')

    def test_input_validation_no_calls(self):
        def unexpected(*a):raise AssertionError('network called')
        s=self.service(unexpected)
        for extra in ({'page_size':0},{'page_size':101},{'page':0},{'params':{'serviceKey':'secret'}},{'params':{'unknown':'x'}},{'filters':{'x':2}}):
            self.assertFalse(s.search(**{**self.query,**extra})['ok'])

    def test_standard_parameter_contracts(self):
        calls=[]
        s=self.service(lambda u,p:(calls.append((u,p)) or payload([],0)))
        s.search('standard',start='2026-10-01',end='2026-10-01')
        self.assertIn('bidNtceBgnDt',calls[-1][1]);self.assertNotIn('inqryBgnDt',calls[-1][1])
        r=s.search('standard',operation='getDataSetOpnStdScsbidInfo',start='2026-10-01',end='2026-10-01')
        self.assertEqual(r['reason'],'missing_required_parameter_bsnsDivCd')
        s.search('standard',operation='getDataSetOpnStdScsbidInfo',start='2026-10-01',end='2026-10-01',params={'bsnsDivCd':'3'})
        self.assertIn('opengBgnDt',calls[-1][1])
        s.search('standard',operation='getDataSetOpnStdCntrctInfo',start='2026-10-01',end='2026-10-01')
        self.assertEqual(calls[-1][1]['cntrctCnclsEndDate'],'20261001')

    def test_opening_never_final_award(self):
        s=self.service(lambda u,p:payload([row(1,opengRank='1')]))
        r=s.search(**{**self.query,'service':'openings'})
        self.assertEqual(r['record_semantics'],'opening_results_not_final_award')
        self.assertNotIn('final_award',r['data'][0]['normalized'])

    def test_identifier_detail_one_page(self):
        s=self.service(lambda u,p:payload([row(1),row(1,bidNtceOrd='001')],6))
        r=s.detail('bids',{'bidNtceNo':'SYNTH-1','bidNtceOrd':'001'},page_size=2)
        self.assertEqual(r['filtered_count'],1);self.assertFalse(r['detail_complete']);self.assertTrue(r['partial'])

    def test_new_detail_explicit_selector(self):
        s=self.service(lambda u,p:payload([],0))
        r=s.detail('contracts',{'untyCntrctNo':'SYNTH'})
        self.assertEqual(r['reason'],'detail_requires_explicit_inqryDiv')

    def test_collect_pages_dedup(self):
        s=self.service(lambda u,p:payload([row(1),row(2)] if p['pageNo']=='1' else [row(2),row(3)],4))
        r=s.collect('demo',self.query)
        self.assertEqual((r['status'],r['read_count'],r['filtered_count'],r['unique_count']),('complete',4,4,3))
        self.assertEqual(s.collect('demo')['calls_reserved'],2)

    def test_collect_period_split(self):
        calls=[]
        s=self.service(lambda u,p:(calls.append(p) or payload([row(p['inqryBgnDt'])])))
        r=s.collect('demo',{**self.query,'end':'2026-10-16'})
        self.assertEqual(r['status'],'complete');self.assertEqual(len(calls),3)
        self.assertEqual([x['inqryBgnDt'] for x in calls],['202610010000','202610080000','202610150000'])
        self.assertEqual([x['inqryEndDt'] for x in calls],['202610072359','202610142359','202610162359'])

    def test_filter_across_empty_accepted_pages(self):
        s=self.service(lambda u,p:payload([row(p['pageNo']+'a'),row(p['pageNo']+'b')],4))
        r=s.collect('demo',{**self.query,'filters':{'bidNtceNm':'no matches'}})
        self.assertEqual(r['status'],'complete');self.assertEqual((r['read_count'],r['filtered_count'],r['unique_count']),(4,0,0))

    def test_short_page_reports_failure(self):
        r=self.service(lambda u,p:payload([row(1)],6)).collect('demo',self.query)
        self.assertEqual(r['reason'],'short_page_before_total');self.assertTrue(r['partial'])
        self.assertEqual(r['unique_count'],0);self.assertEqual(r['failed_segments'][0]['page'],1)

    def test_repeated_page_and_total_drift(self):
        r=self.service(lambda u,p:payload([row(1),row(2)],6)).collect('repeated',self.query)
        self.assertEqual(r['reason'],'repeated_page')
        r=self.service(lambda u,p:payload([row(p['pageNo']+'a'),row(p['pageNo']+'b')],4 if p['pageNo']=='1' else 6)).collect('drift',self.query)
        self.assertEqual(r['reason'],'source_total_changed')

    def test_filtered_repeated_source_page_still_fails(self):
        r=self.service(lambda u,p:payload([row(1),row(2)],6)).collect('filtered-repeat',{**self.query,'filters':{'bidNtceNm':'no match'}})
        self.assertEqual(r['reason'],'repeated_page')

    def test_uninitialized_status_is_null_reason(self):
        s=self.service(lambda u,p:payload([],0))
        s.collect('invalid',{'service':'nonexistent'})
        r=s.job_status('invalid')
        self.assertFalse(r['ok']);self.assertIsNone(r['data']);self.assertEqual(r['reason'],'uninitialized_or_invalid_job_state')

    def test_native_date_bypass_rejected(self):
        s=self.service(lambda u,p:payload([],0))
        r=s.search('bids',params={'inqryBgnDt':'202601010000','inqryEndDt':'202612312359'})
        self.assertEqual(r['reason'],'native_date_range_exceeds_policy')

    def test_budget_persists_and_resume_does_not_extend(self):
        calls=[]
        s=self.service(lambda u,p:(calls.append(p) or payload([row(p['pageNo']+'a'),row(p['pageNo']+'b')],100)))
        r=s.collect('demo',self.query,max_calls=2)
        self.assertEqual(r['reason'],'call_budget_exhausted');self.assertEqual(len(calls),2)
        s.collect('demo',max_calls=2);self.assertEqual(len(calls),2)
        self.assertEqual(s.collect('demo',max_calls=20)['reason'],'budget_mismatch_use_original_max_calls')
        self.assertEqual(s.collect('other',self.query,max_calls=21)['reason'],'max_calls_must_be_1_to_20')

    def test_blocked_stops_and_requires_explicit_retry(self):
        calls=[]
        s=self.service(lambda u,p:(calls.append(p) or payload([],0,'30')))
        r=s.collect('demo',self.query)
        self.assertEqual(r['status'],'blocked');s.collect('demo');self.assertEqual(len(calls),1)
        s.client=Client(transport=lambda u,p:payload([row(1)]),interval=0)
        r=s.collect('demo',retry_failed=True);self.assertEqual(r['status'],'complete');self.assertEqual(r['failed_segments'],[])

    def test_query_isolation_and_job_names(self):
        s=self.service(lambda u,p:payload([],0));s.collect('demo',self.query)
        r=s.collect('demo',{**self.query,'filters':{'ntceInsttNm':'other institution'}})
        self.assertEqual(r['reason'],'query_mismatch_use_new_job_id')
        self.assertFalse(s.collect('../escape',self.query)['ok'])

    def test_contract_revision_and_participant_preserved(self):
        a=normalize({'untyCntrctNo':'X','cntrctOrd':'001'},'getCntrctInfoListCnstwk')
        b=normalize({'untyCntrctNo':'X','cntrctOrd':'002'},'getCntrctInfoListCnstwk')
        self.assertNotEqual(record_key(a,'contracts','getCntrctInfoListCnstwk'),record_key(b,'contracts','getCntrctInfoListCnstwk'))
        a=normalize(row(1,bidClsfcNo='1',rbidNo='0',bidprcCorpBizrno='A'),'getOpengResultListInfoCnstwk')
        b=normalize(row(1,bidClsfcNo='1',rbidNo='0',bidprcCorpBizrno='B'),'getOpengResultListInfoCnstwk')
        self.assertNotEqual(record_key(a,'awards','getOpengResultListInfoCnstwk'),record_key(b,'awards','getOpengResultListInfoCnstwk'))

    def test_every_official_operation_resolves_without_network(self):
        from sionlab_procurement.registry import resolve
        for source,meta in REGISTRY.items():
            for op in meta['operations']:
                self.assertEqual(resolve(source,operation=op)[1],op)
        self.assertEqual(len(REGISTRY),11)

    def test_oversized_last_page_cannot_complete(self):
        s=self.service(lambda u,p:payload([row(p['pageNo']+'a'),row(p['pageNo']+'b')],3))
        r=s.collect('too-many',self.query)
        self.assertEqual(r['reason'],'page_item_count_exceeds_reported_total')
        self.assertEqual(r['unique_count'],2);self.assertEqual(r['status'],'failed')

    def test_response_page_size_mismatch(self):
        def transport(u,p):
            data=payload([row(1)],1);data['response']['body']['numOfRows']=99;return data
        self.assertEqual(self.service(transport).search(**self.query)['reason'],'page_size_mismatch')

    def test_status_uses_one_read_snapshot_during_writer_commit(self):
        from sionlab_procurement import jobs
        from sionlab_procurement.service import canonical
        s=self.service(lambda u,p:payload([row(1)],1));s.collect('snapshot',self.query)
        original=jobs.get_state
        def read_then_commit(db):
            old=original(db)
            writer=sqlite3.connect(Path(self.tmp.name)/'snapshot.sqlite3')
            new=json.loads(writer.execute('SELECT body FROM state WHERE id=1').fetchone()[0]);new['calls']=2
            writer.execute('UPDATE state SET body=? WHERE id=1',(canonical(new),))
            writer.execute('INSERT INTO records VALUES(?,?)',('new',canonical(normalize(row(2),'getBidPblancListInfoCnstwk'))))
            writer.execute('UPDATE pages SET read_count=2,filtered_count=2')
            writer.commit();writer.close();return old
        with patch.object(jobs,'get_state',side_effect=read_then_commit):
            result=s.job_status('snapshot',True)
        self.assertEqual((result['calls_reserved'],result['unique_count'],result['read_count'],len(result['data'])),(1,1,1,1))
        result=s.job_status('snapshot',True)
        self.assertEqual((result['calls_reserved'],result['unique_count'],result['read_count'],len(result['data'])),(2,2,2,2))

    def test_default_service_adapters_with_valid_conditional_inputs(self):
        for service in ['bids','openings','awards','contracts','specs','plans','requests','prices','process','standard','private','private_awards']:
            calls=[]
            engine=self.service(lambda u,p:(calls.append((u,p)) or payload([row(1)])))
            query={'service':service,'start':'2026-10-01','end':'2026-10-01'}
            if service=='plans':query['params']={'orderBgnYm':'202610','orderEndYm':'202612','orderInsttCd':'SYNTH-ORG'}
            if service=='prices':query={'service':'prices'}
            if service=='process':query={'service':'process','params':{'bidNtceNo':'SYNTH-1','inqryDiv':'1'}}
            result=engine.search(**query)
            self.assertTrue(result['ok'],(service,result));self.assertEqual(len(calls),1)

    def test_plans_require_separate_order_months(self):
        s=self.service(lambda u,p:payload([],0))
        r=s.search('plans',start='2026-10-01',end='2026-10-01')
        self.assertEqual(r['reason'],'plans_require_order_months_and_publication_dates')

    def test_live_coverage_is_only_four_operation_samples(self):
        c=Procurement.coverage();samples=[s for service in c['services'] for s in service['live_samples']]
        self.assertEqual(len(samples),4);self.assertTrue(all(s['partial'] for s in samples))
        self.assertTrue(all(s['live_verified'] is None for s in c['services']))
        self.assertFalse(c['all_services_live_verified'])

    def test_actual_http_json_and_xml_errors(self):
        responses=[(200,json.dumps(payload([row(1)])).encode()),(200,b'<OpenAPI_ServiceResponse><returnReasonCode>30</returnReasonCode></OpenAPI_ServiceResponse>'),(403,b'Forbidden')]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(inner):
                code,body=responses.pop(0);inner.send_response(code);inner.end_headers();inner.wfile.write(body)
            def log_message(*args):pass
        http=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            with patch.dict(REGISTRY['bids'],base_url=f'http://127.0.0.1:{http.server_port}'):
                s=Procurement(Client(key='SYNTHETIC-KEY',interval=0))
                self.assertTrue(s.search(**self.query)['ok'])
                self.assertEqual(s.search(**self.query)['reason'],'api_error_30')
                r=s.search(**self.query);self.assertEqual(r['reason'],'http_403');self.assertNotIn('SYNTHETIC-KEY',json.dumps(r))
        finally:http.shutdown();http.server_close();thread.join()


class ProcessSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)

    def child(self,point):
        code='''import json,sys,time
from sionlab_procurement import Client,Procurement
rows=[{'bidNtceNo':'SYNTH-1','bidNtceOrd':'000'},{'bidNtceNo':'SYNTH-2','bidNtceOrd':'000'}]
s=Procurement(Client(transport=lambda u,p:{'response':{'header':{'resultCode':'00'},'body':{'totalCount':2,'items':rows}}},interval=0),sys.argv[1])
def hook(point):
 if point==sys.argv[2]:
  print(point,flush=True)
  time.sleep(60)
s._checkpoint_hook=hook
print(json.dumps(s.collect('crash',{'service':'bids','start':'2026-10-01','end':'2026-10-01','page_size':2})),flush=True)
'''
        child=subprocess.Popen([sys.executable,'-c',code,self.tmp.name,point],stdout=subprocess.PIPE,text=True)
        self.addCleanup(lambda:child.kill() if child.poll() is None else None)
        self.assertEqual(child.stdout.readline().strip(),point)
        return child

    def resume(self):
        s=Procurement(Client(transport=lambda u,p:payload([row(1),row(2)]),interval=0),self.tmp.name)
        return s.collect('crash')

    def test_kill_before_commit_replays_atomic_page(self):
        child=self.child('before_commit');child.kill();child.wait();child.stdout.close()
        r=self.resume();self.assertEqual(r['status'],'complete');self.assertEqual(r['unique_count'],2);self.assertEqual(r['calls_reserved'],2)
        db=sqlite3.connect(Path(self.tmp.name)/'crash.sqlite3')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM pages').fetchone()[0],1);db.close()

    def test_kill_after_commit_does_not_fetch_again(self):
        child=self.child('after_commit');child.kill();child.wait();child.stdout.close()
        r=self.resume();self.assertEqual(r['status'],'complete');self.assertEqual(r['unique_count'],2);self.assertEqual(r['calls_reserved'],1)

    def test_second_process_cannot_mix_job(self):
        child=self.child('before_commit')
        r=self.resume();self.assertEqual(r['reason'],'job_busy')
        child.kill();child.wait();child.stdout.close();self.assertEqual(self.resume()['unique_count'],2)


class Stdio(unittest.TestCase):
    def test_initialize_list_coverage_no_key_real_process(self):
        msgs=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}}},
              {'jsonrpc':'2.0','method':'notifications/initialized'},
              {'jsonrpc':'2.0','id':2,'method':'tools/list'},
              {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'sionlab_coverage','arguments':{}}},
              {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'sionlab_search','arguments':{'service':'bids','start':'2026-10-01','end':'2026-10-01'}}}]
        env={k:v for k,v in os.environ.items() if k!='DATA_GO_KR_API_KEY'}
        p=subprocess.run([sys.executable,'-m','sionlab_procurement','serve'],input='\n'.join(json.dumps(x) for x in msgs)+'\n',text=True,capture_output=True,env=env,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        rows=[json.loads(x) for x in p.stdout.splitlines()];self.assertEqual(len(rows),4)
        self.assertEqual(len(rows[1]['result']['tools']),5)
        self.assertEqual(len(rows[2]['result']['structuredContent']['services']),11)
        self.assertEqual(rows[3]['result']['structuredContent']['reason'],'missing_api_key')
        self.assertTrue(rows[3]['result']['isError'])


if __name__=='__main__':unittest.main()
