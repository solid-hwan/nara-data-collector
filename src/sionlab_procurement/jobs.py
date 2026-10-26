"""One SQLite database per immutable query; atomic page and cursor checkpoints."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from .client import failure
from .registry import resolve, date_policy
from .service import canonical, date_windows, prepare, record_key


def job_path(directory, job_id):
    if not isinstance(job_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',job_id):
        raise ValueError('invalid_job_id')
    return Path(directory) / (job_id + '.sqlite3')


@contextmanager
def lock(path):
    # Lock the persistent sidecar, not the SQLite inode; a crash releases the lock.
    handle = open(str(path) + '.lock','a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: raise ValueError('job_busy') from None
        else:
            import fcntl
            try: fcntl.flock(handle,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('job_busy') from None
        yield
    finally:
        handle.close()


def connect(path, readonly=False):
    db = sqlite3.connect('file:' + str(path.resolve()) + '?mode=ro',uri=True) if readonly else sqlite3.connect(path)
    if not readonly:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.executescript('''CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pages (segment INTEGER NOT NULL,page INTEGER NOT NULL,fingerprint TEXT NOT NULL,read_count INTEGER NOT NULL,filtered_count INTEGER NOT NULL,PRIMARY KEY(segment,page));''')
    return db


def get_state(db):
    row=db.execute('SELECT body FROM state WHERE id=1').fetchone()
    return json.loads(row[0]) if row else None


def put_state(db,state):
    state['updated_at'] = datetime.now(timezone.utc).isoformat()
    db.execute('INSERT INTO state(id,body) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(canonical(state),))


def snapshot(db,state,include_data=False):
    count=db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
    rows=db.execute('SELECT COALESCE(SUM(read_count),0),COALESCE(SUM(filtered_count),0) FROM pages').fetchone()
    totals=state['source_totals']
    complete_totals=all(v is not None for v in totals)
    reason=state.get('reason')
    result={'ok':state['status']=='complete' or (state['status']=='paused' and reason=='call_budget_exhausted' and not state['failures']),
            'job_id':state['job_id'],'status':state['status'],
            'reason':reason,'partial':state['status']!='complete','data':None,
            'source_total_count':sum(totals) if complete_totals else None,
            'source_total_reason':None if complete_totals else 'unqueried_or_failed_segments',
            'source_totals_by_segment':totals,'read_count':rows[0], 'filtered_count':rows[1],
            'unique_count':count,'calls_reserved':state['calls'],'max_calls':state['max_calls'],
            'checkpoint':{'segment':state['segment'],'page':state['page']},
            'failed_segments':state['failures'],'query':state['query'],
            'counts_note':'read/filtered include duplicates; unique_count is persisted deduplication; totals are per-window source reports',
            'snapshot_guarantee':False, 'created_at':state.get('created_at'), 'updated_at':state.get('updated_at')}
    if include_data:
        result['data']=[json.loads(r[0]) for r in db.execute('SELECT body FROM records ORDER BY key')]
    return result


def status(directory,job_id,include_data=False):
    try:
        path=job_path(directory,job_id)
        if not path.exists():return failure('job_not_found')
        with connect(path,readonly=True) as db:
            db.execute('BEGIN')  # State, counts, pages and rows share one WAL read snapshot.
            state=get_state(db)
            if not isinstance(state,dict) or not {'query','windows','source_totals','segment','page','calls','max_calls','status','failures','job_id'} <= set(state):
                return failure('uninitialized_or_invalid_job_state')
            return snapshot(db,state,include_data)
    except (ValueError,TypeError,KeyError,sqlite3.DatabaseError):
        return failure('invalid_or_unreadable_job')


def collect(service,job_id,query,max_calls,retry_failed):
    try:
        path=job_path(service.job_dir,job_id)
        if not isinstance(max_calls,int) or isinstance(max_calls,bool) or not 1<=max_calls<=20:
            raise ValueError('max_calls_must_be_1_to_20')
        service.job_dir.mkdir(parents=True,exist_ok=True)
        with lock(path):
            with connect(path) as db:
                state=get_state(db)
                if state:
                    if query is not None and canonical(query)!=canonical(state['query']):
                        raise ValueError('query_mismatch_use_new_job_id')
                    if max_calls!=state['max_calls']:
                        raise ValueError('budget_mismatch_use_original_max_calls')
                    if state['status']=='complete':return snapshot(db,state,True)
                    if state['status'] in ('failed','blocked') and not retry_failed:
                        return snapshot(db,state,True)
                else:
                    if not isinstance(query,dict) or not query.get('service'):
                        raise ValueError('query_required_for_new_job')
                    allowed={'service','business','operation','start','end','params','page_size','filters'}
                    if set(query)-allowed:raise ValueError('unknown_query_field')
                    source,op,spec=resolve(query['service'],query.get('business','construction'),query.get('operation'))
                    start,end=query.get('start'),query.get('end')
                    if bool(start)!=bool(end):raise ValueError('both_dates_required')
                    # Native date fields cannot be split safely: require normalized
                    # start/end for temporal collection instead of silently ignoring.
                    params=query.get('params') or {}
                    a,b,fmt,days=date_policy(op)
                    if a in params or b in params:
                        raise ValueError('collection_requires_normalized_dates')
                    windows=list(date_windows(start,end,days)) if start else [(None,None)]
                    initial={**query,'start':windows[0][0],'end':windows[0][1]}
                    prepare(**{k:v for k,v in initial.items() if k!='filters'})
                    state={'job_id':job_id,'created_at':datetime.now(timezone.utc).isoformat(),
                           'query':query,'windows':windows,'source_totals':[None]*len(windows),
                           'segment':0,'page':1,'calls':0,'max_calls':max_calls,'status':'running',
                           'reason':None,'failures':[]}
                    put_state(db,state);db.commit()
                while state['segment']<len(state['windows']):
                    if state['calls']>=state['max_calls']:
                        state.update(status='paused',reason='call_budget_exhausted')
                        put_state(db,state);db.commit();break
                    segment,page=state['segment'],state['page']
                    start,end=state['windows'][segment]
                    # Reserve before the request. A killed process cannot reset its
                    # budget even if it dies after the API receives a request.
                    state['calls']+=1
                    state.update(status='running',reason=None)
                    put_state(db,state);db.commit()
                    response=service.search(**{**state['query'],'start':start,'end':end,'page':page})
                    if response['ok']:
                        total=response['source_total_count'];expected=state['source_totals'][segment]
                        fingerprint=response['page_fingerprint']
                        duplicate=db.execute('SELECT 1 FROM pages WHERE segment=? AND fingerprint=?',(segment,fingerprint)).fetchone()
                        reason=None
                        if expected is not None and expected!=total:reason='source_total_changed'
                        elif duplicate and response['read_count']:reason='repeated_page'
                        elif response['read_count']<response['page_size'] and (page-1)*response['page_size']+response['read_count']<total:reason='short_page_before_total'
                        if reason:response={**response,**failure(reason)}
                    if not response['ok']:
                        failure_record={'segment':segment,'page':page,'start':start,'end':end,'reason':response['reason']}
                        state['failures'].append(failure_record)
                        state.update(status='blocked' if response.get('blocked') else 'failed',reason=response['reason'])
                        put_state(db,state);db.commit();break
                    # Entire page and successor cursor are committed together.
                    db.execute('BEGIN IMMEDIATE')
                    for row in response['data']:
                        key=record_key(row,response['service'],response['operation'])
                        db.execute('INSERT INTO records(key,body) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET body=excluded.body',(key,canonical(row)))
                    db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',(segment,page,fingerprint,response['read_count'],response['filtered_count']))
                    state['source_totals'][segment]=total
                    if page*response['page_size']>=total:
                        state['segment']+=1;state['page']=1
                    else:state['page']+=1
                    state['failures']=[f for f in state['failures'] if (f['segment'],f['page'])!=(segment,page)]
                    if state['segment']==len(state['windows']):state.update(status='complete',reason=None)
                    put_state(db,state)
                    # Fault injection is an internal callable used by process-kill
                    # tests, never a production environment switch.
                    hook=getattr(service,'_checkpoint_hook',None)
                    if hook:hook('before_commit')
                    db.commit()
                    if hook:hook('after_commit')
                return snapshot(db,state,True)
    except ValueError as exc:
        safe=str(exc)
        return failure(safe if safe.replace('_','').isalnum() else 'invalid_input')
    except sqlite3.DatabaseError:
        return failure('job_database_error')
