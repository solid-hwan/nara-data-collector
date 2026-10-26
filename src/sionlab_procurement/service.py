"""Original search/detail contracts; collection lives in jobs.py."""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from .client import Client, failure
from .registry import resolve, date_policy, semantics, coverage


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def date_windows(start, end, days):
    a = datetime.strptime(start, '%Y-%m-%d')
    b = datetime.strptime(end, '%Y-%m-%d')
    if a > b:
        raise ValueError('date_range_reversed')
    if (b - a).days > 3660:
        raise ValueError('date_range_exceeds_ten_years')
    while a <= b:
        stop = min(a + timedelta(days=days - 1), b)
        yield a.strftime('%Y-%m-%d'), stop.strftime('%Y-%m-%d')
        a = stop + timedelta(days=1)


def prepare(service, business='construction', operation=None, start=None, end=None, params=None, page=1, page_size=20):
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise ValueError('invalid_page')
    if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= 100:
        raise ValueError('page_size_must_be_1_to_100')
    source, op, spec = resolve(service, business, operation)
    p = dict(params or {})
    if any(k not in spec['parameters'] or k in ('pageNo', 'numOfRows', 'type') for k in p):
        raise ValueError('unsupported_or_reserved_parameter')
    if any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in p.values()):
        raise ValueError('parameters_must_be_strings_or_integers')
    p = {k: str(v) for k,v in p.items()}
    p.update(pageNo=str(page), numOfRows=str(page_size), type='json')
    if 'inqryDiv' in spec['parameters']:
        p.setdefault('inqryDiv', '1')
    if bool(start) != bool(end):
        raise ValueError('both_dates_required')
    a, b, fmt, days = date_policy(op)
    if start:
        if a not in spec['parameters'] or b not in spec['parameters']:
            raise ValueError('operation_requires_native_date_parameters')
        if a in p or b in p:
            raise ValueError('conflicting_date_parameters')
        windows = list(date_windows(start, end, days))
        if len(windows) != 1:
            raise ValueError('search_range_too_large_use_collect')
        p[a] = datetime.strptime(start, '%Y-%m-%d').strftime(fmt)
        p[b] = datetime.strptime(end, '%Y-%m-%d').replace(hour=23, minute=59).strftime(fmt)
    # Native API parameters remain available but no unbounded temporal query.
    temporal = a in spec['parameters'] and b in spec['parameters']
    identifiers = ('bidNtceNo', 'untyCntrctNo', 'bfSpecRgstNo', 'prcrmntReqNo', 'orderPlanUntyNo')
    if temporal and not start and not any(p.get(k) for k in identifiers):
        if not (p.get(a) and p.get(b)) and not (p.get('orderBgnYm') and p.get('orderEndYm')):
            raise ValueError('explicit_dates_or_identifier_required')
    if bool(p.get(a)) != bool(p.get(b)):
        raise ValueError('both_native_dates_required')
    if p.get(a) and not start:
        try:
            native_a, native_b = datetime.strptime(p[a],fmt), datetime.strptime(p[b],fmt)
        except ValueError:
            raise ValueError('invalid_native_date_format') from None
        if native_a > native_b or native_b - native_a >= timedelta(days=days):
            raise ValueError('native_date_range_exceeds_policy')
    if source == 'plans' and 'PPSSrch' not in op and p.get('inqryDiv') == '1':
        if not all(p.get(k) for k in ('orderBgnYm','orderEndYm','inqryBgnDt','inqryEndDt')):
            raise ValueError('plans_require_order_months_and_publication_dates')
    if p.get('orderBgnYm') or p.get('orderEndYm'):
        try:
            ma=datetime.strptime(p.get('orderBgnYm',''),'%Y%m')
            mb=datetime.strptime(p.get('orderEndYm',''),'%Y%m')
        except ValueError:
            raise ValueError('invalid_order_months') from None
        if ma>mb:
            raise ValueError('order_month_range_reversed')
    if source == 'process' and not any(p.get(k) for k in ('bidNtceNo','bfSpecRgstNo','orderPlanNo','prcrmntReqNo')):
        raise ValueError('process_identifier_required')
    for key, meta in spec['parameters'].items():
        if meta['required'] and not p.get(key):
            raise ValueError('missing_required_parameter_' + key)
    return source, op, p


def normalize(row, operation):
    # Keep identifiers verbatim. No numeric conversion of numbers, ordinals, money.
    identifiers = {k:v for k,v in row.items() if k.endswith(('No','Ord','Sno','Seq')) or k in ('orderYear','orderInsttCd','bidClsfcNo','rbidNo')}
    title = next((row[k] for k in ('bidNtceNm','cntrctNm','cntrctCnclsNm','bizNm','prdctClsfcNoNm','krnPrdctNm') if row.get(k)), None)
    return {'raw': row, 'normalized': {'identifiers': identifiers, 'title': title,
                                     'record_semantics': semantics(operation)},
            'missing_reasons': {'title': 'source_field_missing'} if title is None else {}}


def record_key(record, service, operation):
    # Generic adapters cannot prove a shared uniqueness key for all official
    # subresources. Deduplicate only equal privacy-filtered source records;
    # contract amendments and distinct participants remain separate records.
    return hashlib.sha256(canonical([service, operation, record['raw']]).encode()).hexdigest()


class Procurement:
    def __init__(self, client=None, job_dir='jobs'):
        self.client = client or Client()
        self.job_dir = Path(job_dir)

    def search(self, service, business='construction', operation=None, start=None, end=None,
               params=None, page=1, page_size=20, filters=None):
        try:
            if filters is not None and (not isinstance(filters, dict) or any(not isinstance(v,str) for v in filters.values())):
                raise ValueError('filters_must_be_string_mapping')
            source, op, p = prepare(service,business,operation,start,end,params,page,page_size)
        except (ValueError,TypeError) as exc:
            # Input error strings are controlled constants, not repr(user input).
            reason = str(exc) if str(exc).replace('_','').isalnum() else 'invalid_input'
            return {**failure(reason), 'filtered_count': None, 'partial': True, 'failed_segments': []}
        response = self.client.request(source,op,p)
        base = {'service':source,'operation':op,'page':page,'page_size':page_size,
                'record_semantics':semantics(op),'filters':filters or {}, 'query':p,
                'privacy':'contact_fields_and_composite_contact_lists_excluded'}
        if not response['ok']:
            return {**base,**response,'filtered_count':None,'partial':True,
                    'failed_segments':[{'page':page,'start':start,'end':end,'reason':response['reason']}]}
        rows = response['data']
        accepted = [normalize(row,op) for row in rows if all(v.casefold() in str(row.get(k,'')).casefold() for k,v in (filters or {}).items())]
        total = response['source_total_count']
        return {**base,**response,'data':accepted,'filtered_count':len(accepted),
                'partial':page > 1 or total > len(rows), 'failed_segments':[],
                'scope':'one_page_only','page_fingerprint':hashlib.sha256(canonical(rows).encode()).hexdigest(),'total_after_filter':None,
                'total_after_filter_reason':'filter_applies_only_to_read_page'}

    def detail(self, service, identifiers, business='construction', operation=None, params=None, **kwargs):
        if not isinstance(identifiers,dict) or not identifiers or any(not isinstance(v,str) for v in identifiers.values()):
            return failure('identifiers_must_be_nonempty_string_mapping')
        source, op, spec = resolve(service,business,operation)
        merged = dict(params or {})
        direct = {k:v for k,v in identifiers.items() if k in spec['parameters']}
        merged.update(direct)
        if 'inqryDiv' in spec['parameters'] and direct:
            
            if source in ('bids','private'):
                merged.setdefault('inqryDiv','2')
            elif 'inqryDiv' not in merged:
                return failure('detail_requires_explicit_inqryDiv')
        result = self.search(service,business,operation,params=merged,**kwargs)
        if result['ok']:
            result['data'] = [r for r in result['data'] if all(str(r['raw'].get(k,'')) == v for k,v in identifiers.items())]
            result['filtered_count'] = len(result['data'])
            result['scope'] = 'identifier_match_in_one_page'
            result['detail_complete'] = not result['partial']
        return result

    def collect(self, job_id, query=None, max_calls=20, retry_failed=False):
        from .jobs import collect
        return collect(self,job_id,query,max_calls,retry_failed)

    def job_status(self, job_id, include_data=False):
        from .jobs import status
        return status(self.job_dir,job_id,include_data)

    coverage = staticmethod(coverage)
