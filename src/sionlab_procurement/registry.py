"""Official operation identifiers, with SIONLAB request policy layered above them."""
import json
from importlib.resources import files

REGISTRY = json.loads(files(__package__).joinpath('official_operations.json').read_text('utf-8'))
BUSINESS = {'construction': 'Cnstwk', 'goods': 'Thng', 'services': 'Servc', 'foreign': 'Frgcpt'}
PREFIX = {'bids': 'getBidPblancListInfo', 'openings': 'getOpengResultListInfo',
          'awards': 'getScsbidListSttus', 'contracts': 'getCntrctInfoList',
          'specs': 'getPublicPrcureThngInfo', 'plans': 'getOrderPlanSttusList',
          'requests': 'getPrcrmntReqInfoList', 'process': 'getCntrctProcssIntgOpen',
          'private': 'getPrvtBidPblancListInfo'}

def resolve(service, business='construction', operation=None):
    source = 'awards' if service == 'openings' else service
    if source not in REGISTRY:
        raise ValueError('unknown_service')
    if operation is None:
        if service in PREFIX:
            if business not in BUSINESS:
                raise ValueError('unknown_business')
            suffix = BUSINESS[business]
            if service == 'requests' and business == 'services':
                suffix = 'GnrlServc'
            operation = PREFIX[service] + suffix
        elif service == 'standard':
            operation = 'getDataSetOpnStdBidPblancInfo'
        elif service == 'private_awards':
            operation = 'getPrvtScsbidListSttus'
        elif service == 'prices':
            operation = 'getPriceInfoListFcltyCmmnMtrilBildng'
    if operation not in REGISTRY[source]['operations']:
        raise ValueError('unsupported_operation_for_service')
    return source, operation, REGISTRY[source]['operations'][operation]

def date_policy(operation):
    if operation == 'getDataSetOpnStdBidPblancInfo':
        return 'bidNtceBgnDt', 'bidNtceEndDt', '%Y%m%d%H%M', 28
    if operation == 'getDataSetOpnStdScsbidInfo':
        return 'opengBgnDt', 'opengEndDt', '%Y%m%d%H%M', 7
    if operation == 'getDataSetOpnStdCntrctInfo':
        return 'cntrctCnclsBgnDate', 'cntrctCnclsEndDate', '%Y%m%d', 28
    return 'inqryBgnDt', 'inqryEndDt', '%Y%m%d%H%M', 7

def semantics(operation):
    if 'OpengResult' in operation or operation == 'getDataSetOpnStdScsbidInfo':
        return 'opening_results_not_final_award'
    if 'ScsbidListSttus' in operation:
        return 'final_award_source'
    return 'source_record'

def coverage():
    live=json.loads(files(__package__).joinpath('live_verification.json').read_text('utf-8'))
    verified={r['operation']:r for r in live['results']}
    out = []
    for source, desc in REGISTRY.items():
        out.append({'service': source, 'official_source': desc['source'],
                    'schema_checked': desc['checked'], 'implementation': 'generic_validated_adapter',
                    'live_verified': None, 'live_reason': 'Only listed operation samples are verified; the whole service is not',
                    'live_samples': [verified[op] for op in desc['operations'] if op in verified],
                    'operations': list(desc['operations']),
                    'parameters': {k: list(v['parameters']) for k,v in desc['operations'].items()}})
    return {'version': '0.1.0', 'services': out, 'live_evidence':{k:live[k] for k in ('run_id','checked_at','query_day_kst','actual_api_calls','full_collection')}, 'opening_service_alias': 'openings -> awards source, opening operation',
            'local_contract_tests': 'representative adapters and shared engine only; see docs/verification.md', 'all_services_live_verified': False,
            'limitations': ['Single-page detail never implies all detail subresources fetched',
                           'Source completeness and mutable data snapshots are not guaranteed',
                           'Opening rank is never inferred as final award']}
