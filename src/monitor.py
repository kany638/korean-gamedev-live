"""Discover, reverify known URLs, retain stable state, and publish audited feeds."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yaml
from .collector import Lead, crawl_lists, configure_domains, source_host_allowed
from .transport import PublicHTTP, FetchError, authorization_only
from .classifier import analyze
from .calendar_feed import make_ics
from .browser import PublicRenderer
from .industry_expansion import broaden_config
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
TZ=ZoneInfo('Asia/Seoul')


def read_json(path,default):
    try: return json.loads(Path(path).read_text('utf-8'))
    except FileNotFoundError: return copy.deepcopy(default)
    # Corrupt state is NOT treated as empty. Do not silently reset IDs/history.


def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n','utf-8')
    os.replace(tmp,path)


def hours(iso,now):
    if not iso: return 1e9
    try:
        dt=datetime.fromisoformat(iso)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=TZ)
        return (now-dt).total_seconds()/3600
    except (ValueError,TypeError): return 1e9


def fingerprint(job):
    ignored={'last_seen','last_verified','last_attempt','first_seen','revision','updated_at',
             'stale','last_error','closed_at','not_found_count'}
    return json.dumps({k:v for k,v in job.items() if k not in ignored},sort_keys=True,ensure_ascii=False)


def choose_queue(leads,state,now,cap):
    known=state['jobs']; cache=state.setdefault('rejected',{})
    new=[]; revisit={}
    for lead in leads:
        if lead.url not in known:
            if hours(cache.get(lead.url,{}).get('last_attempt'),now)>=12:
                new.append(lead)
        else: revisit[lead.url]=lead
    # Crucial: direct re-checking is not dependent on still appearing on page 1.
    for url,j in known.items():
        if j.get('status')=='closed': continue
        revisit.setdefault(url,Lead(j['title'],url,j['company'],j['source'],
            {'_trusted_adapter':'greenhouse_recheck','board_token':j['public_api_board'],'id':j['public_api_job_id']} if j.get('public_api_board') and j.get('public_api_job_id') else {'_discovery_kind':'dated_program_page'} if j.get('source_class')=='official_program' and j.get('type')=='program' else {}))
    old=[x for x in revisit.values() if hours(known[x.url].get('last_attempt'),now)>=4]
    old.sort(key=lambda x:(0 if known[x.url].get('deadline') and known[x.url]['deadline'] <= (now.date()+timedelta(days=7)).isoformat() else 1,
                           known[x.url].get('last_verified','')))
    # Interleave sources so one large board cannot monopolize all new slots.
    groups=defaultdict(list)
    for x in new: groups[x.source].append(x)
    fair=[]
    while any(groups.values()):
        for src in sorted(groups):
            if groups[src]: fair.append(groups[src].pop(0))
    reserved=min(len(old),max(1,cap//2)) if old else 0
    selected=old[:reserved]+fair[:cap-reserved]
    selected+=old[reserved:reserved+max(0,cap-len(selected))]
    return selected


def migrate_state(state,now):
    state=copy.deepcopy(state);state.setdefault('jobs',{});state.setdefault('rejected',{})
    # Retain known URLs/first-seen time when upgrading, but never certify legacy
    # fields as freshly verified. All retained records are scheduled for recheck.
    for url,j in state['jobs'].items():
        j.setdefault('url',url)
        j.setdefault('first_seen',now.isoformat())
        j.setdefault('updated_at',j['first_seen'])
        j.setdefault('revision',0)
        j.setdefault('status','open')
        j.setdefault('tier','review')
        j.setdefault('company','회사 원문 확인')
        j.setdefault('source','legacy')
        j.setdefault('title','기존 공고 · 재확인 필요')
        j.setdefault('deadline',None)
        j.setdefault('deadline_at',None)
        j.setdefault('type','job')
        j.setdefault('experience','이전 버전 · 재검증 필요')
        j.setdefault('experience_bucket','unknown')
        j.setdefault('verification','legacy_unverified')
        j.setdefault('notice','기존 버전에서 이전된 기록. 상세페이지 재확인 전 신뢰하지 마세요.')
    return state


def scan(config,state,now,http=None,env=None,renderer=None):
    state=migrate_state(state,now)
    configure_domains(config)
    http=http or PublicHTTP(timeout=config.get('request_timeout_seconds',12),
        delay=config.get('request_delay_seconds',1),max_requests=config.get('max_requests_per_run',220),
        domain_limit=config.get('max_requests_per_domain',50),max_seconds=config.get('max_runtime_seconds',1080))
    if isinstance(http,PublicHTTP):
        http.allowed_greenhouse_boards={s['board_token'] for s in config['sources'] if s.get('kind')=='greenhouse'}
    # Broaden beyond the fixed V3 company list without discarding any earlier
    # verified posting state. Roster/homepage entries are never job postings.
    config, expansion_health = broaden_config(config,state,now,http,int(state.get('run_count',0)))
    configure_domains(config)
    owned_renderer=renderer is None
    renderer=renderer or PublicRenderer(http,config.get('browser',{}))
    run_index=int(state.get('run_count',0))
    leads,health=crawl_lists(config,http,env=env,renderer=renderer,run_index=run_index)
    hmap={x['id']:x for x in health}
    pending=[];usable=[]
    for lead in leads:
        src=next((x for x in config['sources'] if x['id']==lead.source),{})
        restricted=src.get('mode') in ('manual','authorized_only') or authorization_only(urlparse(lead.url).hostname or '')
        if restricted and not lead.metadata:
            pending.append(dict(title=lead.title,url=lead.url,source=lead.source,
                                status='discovered_only_not_verified',note='공식/허가된 연동 필요. 달력에는 추가하지 않음.'))
        else: usable.append(lead)
    # Store overflow identities, not search snippets or descriptions, so configured
    # detail caps do not repeatedly erase less popular company leads.
    backlog=state.setdefault('pending',{})
    current={lead.url:lead for lead in usable}
    for url,item in list(backlog.items()):
        if url in state['jobs'] or hours(item.get('discovered_at'),now)>24*14:
            del backlog[url]; continue
        source=next((s for s in config['sources'] if s['id']==item.get('source')),None)
        if source and source.get('mode') not in ('manual','authorized_only','api'):
            current.setdefault(url,Lead(item['title'],url,item.get('company','회사 원문 확인'),item['source']))
    queue=choose_queue(list(current.values()),state,now,int(config.get('max_details_per_scan',72)))
    chosen={x.url for x in queue}
    for lead in usable:
        if lead.url not in state['jobs'] and lead.url not in chosen and not lead.metadata:
            backlog.setdefault(lead.url,dict(title=lead.title,company=lead.company,source=lead.source,discovered_at=now.isoformat()))
    for url in chosen: backlog.pop(url,None)
    limit=int(config.get('max_pending_leads',1800))
    state['pending']=dict(sorted(backlog.items(),key=lambda pair:pair[1].get('discovered_at',''),reverse=True)[:limit])
    reasons=Counter();verified=0;changed=0;created=0;errors=0
    for lead in queue:
        prev=state['jobs'].get(lead.url)
        h=hmap.get(lead.source)
        if h: h['detail_attempts']+=1
        try:
            src=next((x for x in config['sources'] if x['id']==lead.source),{})
            if lead.metadata.get('_trusted_adapter') in ('greenhouse_public_api','greenhouse_recheck'):
                jobid=lead.metadata.get('id') or lead.metadata.get('record',{}).get('id')
                record=http.greenhouse_json(lead.metadata['board_token'],jobid)
                if not isinstance(record,dict) or not isinstance(record.get('content'),str):
                    raise FetchError('official_api_detail_schema_error')
                lead=Lead(lead.title,lead.url,lead.company,lead.source,{'_trusted_adapter':'greenhouse_public_api',
                    'board_token':lead.metadata['board_token'],'record':record})
                html=None
            elif lead.metadata.get('_trusted_adapter')=='saramin_api':
                html=None
            else:
                html=http.get(lead.url)
            job,reason=analyze(lead,html,now.date())
            if reason=='unreadable' and html and src.get('render_js'):
                html=renderer.render(lead.url,src,html)
                job,reason=analyze(lead,html,now.date())
            reasons[reason]+=1
            # A page fetched successfully but unparsable is not a verified listing.
            if reason=='unreadable': raise FetchError('detail_unreadable')
            verified+=1
            if h: h['detail_verified']+=1
            if not job:
                if prev and reason in ('closed','expired','experience_over_3','students_only','senior_title'):
                    prev.update(status='closed',closed_at=now.isoformat(),last_verified=now.isoformat(),
                                last_attempt=now.isoformat(),updated_at=now.isoformat(),revision=prev.get('revision',0)+1)
                    changed+=1
                elif prev:
                    # Do not certify a broken or irrelevant parser result as fresh.
                    prev.update(last_attempt=now.isoformat(),last_error=reason)
                else:
                    state['rejected'][lead.url]={'last_attempt':now.isoformat(),'reason':reason}
                continue
            if h: h['matched']+=1
            job['status']='open'
            job['source_class']=src.get('source_class','job_board')
            if prev:
                if job['company']=='회사 원문 확인': job['company']=prev['company']
                meaningful=fingerprint(prev)!=fingerprint(job)
                job.update(first_seen=prev['first_seen'],revision=prev.get('revision',0)+int(meaningful),
                           updated_at=now.isoformat() if meaningful else prev.get('updated_at',now.isoformat()))
                changed+=int(meaningful)
            else:
                created+=1
                job.update(first_seen=now.isoformat(),revision=0,updated_at=now.isoformat())
            job.update(last_seen=now.isoformat(),last_verified=now.isoformat(),last_attempt=now.isoformat(),last_error=None)
            state['jobs'][lead.url]=job
        except Exception as exc:
            errors+=1
            code=exc.code if isinstance(exc,FetchError) else type(exc).__name__
            reasons[code]+=1
            if h: h['last_detail_error']=code
            if prev:
                prev.update(last_attempt=now.isoformat(),last_error=code)
                if code in ('http_404','http_410'):
                    prev['not_found_count']=prev.get('not_found_count',0)+1
                    if prev['not_found_count']>=2:
                        prev.update(status='closed',closed_at=now.isoformat(),updated_at=now.isoformat(),revision=prev.get('revision',0)+1)
            else:
                state['rejected'][lead.url]={'last_attempt':now.isoformat(),'reason':code}
    if owned_renderer: renderer.close()
    state['run_count']=run_index+1
    source_history=state.setdefault('source_history',{})
    for h in health:
        previous=source_history.get(h['id'],{})
        # Scheduled rotations are NOT attempts; retain the genuine checked-at time.
        h['checked_at']=previous.get('checked_at') if h['status']=='scheduled_rotation_skip' else now.isoformat()
        fetched=any(p.get('status') in ('html_received','rendered_received') for p in h.get('pages',[])) or h['status'] in ('api_response_received','official_api_response_received')
        h['last_listing_success']=now.isoformat() if fetched else previous.get('last_listing_success')
        h['last_detail_success']=now.isoformat() if h['detail_verified'] else previous.get('last_detail_success')
        source_history[h['id']]={k:h[k] for k in ('checked_at','status','last_listing_success','last_detail_success')}
    state['last_scanned']=now.isoformat()
    if verified: state['last_verified_scan']=now.isoformat()
    state['version']=4 if expansion_health.get('enabled') else 3
    for url,r in list(state['rejected'].items()):
        if hours(r.get('last_attempt'),now)>24*14: del state['rejected'][url]
    for url,r in list(state['jobs'].items()):
        if r.get('status')=='closed' and hours(r.get('closed_at'),now)>24*90: del state['jobs'][url]
    health_out=dict(version=state['version'],industry_expansion=expansion_health,
                   expanded_source_catalog=[{k:v for k,v in x.items() if k in ('id','name','url','mode','note','source_class','targets','reference_url','reference_status','entry_points','render_js')} for x in config['sources']],last_scan_kst=now.isoformat(),last_verified_scan_kst=state.get('last_verified_scan'),
                   sources=health,candidate_links=len(leads),unverified_candidates=pending[:150],
                   detail_attempts=len(queue),deferred_detail_links=len(state['pending']),source_class_counts=dict(Counter(s.get('source_class','job_board') for s in config['sources'])),verified_detail_records=verified,new_matches=created,changed_matches=changed,
                   detail_errors=errors,request_count=http.requests_made,classification_counts=dict(reasons),
                   run_status='records_verified' if verified else 'degraded_no_verified_details',
                   warning='Broadened rotating discovery, NOT exhaustive market coverage. Only successful listing/detail checks count; check source failures.')
    return state,health_out


def published_jobs(state,now,cfg):
    out=[]
    for j in state.get('jobs',{}).values():
        j=copy.deepcopy(j)
        if j.get('status')=='closed':
            if hours(j.get('closed_at'),now)<=24*int(cfg.get('cancelled_retention_days',30)): out.append(j)
            continue
        if j.get('deadline') and j['deadline']<(now.date()-timedelta(days=14)).isoformat(): continue
        j['stale']=hours(j.get('last_verified'),now)>float(cfg.get('stale_after_hours',48))
        if j['stale'] and hours(j.get('last_verified'),now)>24*30: continue
        out.append(j)
    return out


def publish(config,state,health,now,output:Path):
    site=output/'site';site.mkdir(parents=True,exist_ok=True)
    jobs=published_jobs(state,now,config)
    feeds={'calendar.ics':('실시간 게임개발 채용공고',jobs),
           'entry.ics':('실시간 · 신입/경력무관',[j for j in jobs if j['tier']=='primary']),
           'stretch.ics':('실시간 · 1~3년 도전',[j for j in jobs if j['tier']=='stretch']),
           'review.ics':('실시간 · 자격확인',[j for j in jobs if j['tier']=='review']),
           'secondary.ics':('실시간 · 보조 분야',[j for j in jobs if j['tier']=='secondary'])}
    for filename,(name,rows) in feeds.items():
        (site/filename).write_bytes(make_ics(rows,now,config.get('review_after_days',2),name).encode('utf-8'))
    public_fields={'title','company','url','source','deadline','deadline_at','deadline_basis','experience','experience_bucket',
                   'graduate_eligibility','type','employment','tier','location','fit','status','stale','first_seen',
                   'last_verified','last_error','verification','notice','min_years','max_years','source_class'}
    write_json(site/'jobs.json',[{k:v for k,v in j.items() if k in public_fields} for j in jobs])
    health['calendar_events']=len(jobs)
    health['active_events']=sum(j.get('status')!='closed' for j in jobs)
    write_json(site/'health.json',health)
    write_json(site/'source_catalog.json',health.get('expanded_source_catalog') or [{k:v for k,v in s.items() if k in ('id','name','url','mode','note','source_class','targets','reference_url','reference_checked','reference_status','entry_points','render_js')} for s in config['sources']])
    write_json(output/'data/state.json',state)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--config',type=Path,default=ROOT/'config.yaml')
    parser.add_argument('--as-of',help='Test only; ISO datetime. Omit for production.')
    args=parser.parse_args()
    cfg=yaml.safe_load(args.config.read_text('utf-8'))
    state=read_json(args.output/'data/state.json',{'version':3,'jobs':{},'rejected':{}})
    now=datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(TZ)
    if now.tzinfo is None: now=now.replace(tzinfo=TZ)
    state,health=scan(cfg,state,now)
    publish(cfg,state,health,now,args.output)
    print(json.dumps({k:health[k] for k in ('run_status','candidate_links','verified_detail_records','new_matches','detail_errors','calendar_events')},ensure_ascii=False))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as f:
            f.write('# Live recruitment scan\n\n')
            f.write(f'Run: {health["run_status"]}; verified details: {health["verified_detail_records"]}; events: {health["calendar_events"]}\n\n')
            f.write('A green workflow does not prove every source is covered. Read the dashboard source-health table.\n')

if __name__=='__main__': main()
