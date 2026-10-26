"""MCP 2025-11-25 stdio tools subset, implemented from the public protocol.

No HTTP listener or arbitrary shell execution is exposed. Requests are sequential.
"""
import json
import sys
from .client import failure

QUERY = {'type':'object','properties':{
    'service':{'type':'string','enum':['bids','openings','awards','contracts','specs','plans','requests','prices','process','standard','private','private_awards']},
    'business':{'type':'string','enum':['construction','goods','services','foreign']},
    'operation':{'type':'string','description':'Exact official operation identifier; sionlab_coverage lists operations and parameter names.'},
    'start':{'type':'string','description':'YYYY-MM-DD, inclusive'},'end':{'type':'string','description':'YYYY-MM-DD, inclusive'},
    'params':{'type':'object','additionalProperties':{'type':['string','integer']}},
    'page_size':{'type':'integer','minimum':1,'maximum':100,'default':20},
    'filters':{'type':'object','additionalProperties':{'type':'string'},'description':'Case-insensitive contains, applied only to fetched rows.'}},
    'required':['service'],'additionalProperties':False}


def tools():
    search=json.loads(json.dumps(QUERY));search['properties']['page']={'type':'integer','minimum':1,'default':1}
    detail=json.loads(json.dumps(search));detail['properties']['identifiers']={'type':'object','additionalProperties':{'type':'string'},'minProperties':1};detail['required'].append('identifiers')
    schemas=[('sionlab_search','Search one official API page. Never claims full collection.',search),
      ('sionlab_detail','Match identifiers in one page; specify official selector params for non-bid services.',detail),
      ('sionlab_collect','Collect sequentially to SQLite, resume unchanged query, maximum 20 total reserved calls.',
       {'type':'object','properties':{'job_id':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$'},'query':QUERY,
         'max_calls':{'type':'integer','minimum':1,'maximum':20,'default':20},'retry_failed':{'type':'boolean','default':False}},'required':['job_id'],'additionalProperties':False}),
      ('sionlab_coverage','List official operations, supported contracts and live verification limitations.',{'type':'object','additionalProperties':False}),
      ('sionlab_job_status','Read saved checkpoint and counts; optional saved rows.',{'type':'object','properties':{'job_id':{'type':'string'},'include_data':{'type':'boolean','default':False}},'required':['job_id'],'additionalProperties':False})]
    return [{'name':name,'description':description,'inputSchema':schema,'annotations':{'readOnlyHint':name!='sionlab_collect','destructiveHint':False,'openWorldHint':name in ('sionlab_search','sionlab_detail','sionlab_collect')}} for name,description,schema in schemas]


def call(service,name,args):
    methods={'sionlab_search':service.search,'sionlab_detail':service.detail,'sionlab_collect':service.collect,
             'sionlab_coverage':service.coverage,'sionlab_job_status':service.job_status}
    if name not in methods:return failure('unknown_tool')
    if not isinstance(args,dict):return failure('arguments_must_be_object')
    try:
        return methods[name](**args)
    except (TypeError,ValueError,KeyError):
        return failure('invalid_arguments')
    except (OSError,RuntimeError):
        return failure('local_execution_error')


def serve(service):
    initialized=False
    for line in sys.stdin:
        request_id=None
        try:
            req=json.loads(line)
            if not isinstance(req,dict) or req.get('jsonrpc')!='2.0' or not isinstance(req.get('method'),str):
                raise ValueError('invalid_request')
            request_id=req.get('id')
            method=req['method'];params=req.get('params',{})
            if 'id' not in req:
                # Notifications have no response.
                continue
            if method=='initialize':
                requested=params.get('protocolVersion')
                version=requested if requested in ('2024-11-05','2025-03-26','2025-06-18','2025-11-25') else '2025-11-25'
                result={'protocolVersion':version,'capabilities':{'tools':{'listChanged':False}},
                        'serverInfo':{'name':'sionlab-procurement-mcp','version':'0.4.0'},
                        'instructions':'Search/detail are one-page snapshots. Opening rank is not a final award. Check partial and reason.'}
                initialized=True
            elif method=='ping':result={}
            elif method=='server/discover':
                print(json.dumps({'jsonrpc':'2.0','id':request_id,'error':{'code':-32022,'message':'Supported initialization protocol','data':{'supported':['2025-11-25']}}}),flush=True)
                continue
            elif not initialized:
                print(json.dumps({'jsonrpc':'2.0','id':request_id,'error':{'code':-32002,'message':'Initialize first'}}),flush=True);continue
            elif method=='tools/list':result={'tools':tools()}
            elif method=='tools/call':
                data=call(service,params.get('name'),params.get('arguments',{}))
                result={'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False)}],
                        'structuredContent':data,'isError':data.get('ok') is False}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':request_id,'error':{'code':-32601,'message':'Method not found'}}),flush=True);continue
            out={'jsonrpc':'2.0','id':request_id,'result':result}
        except json.JSONDecodeError:
            out={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}
        except (ValueError,TypeError,AttributeError):
            out={'jsonrpc':'2.0','id':request_id,'error':{'code':-32600,'message':'Invalid request'}}
        print(json.dumps(out,ensure_ascii=False),flush=True)
