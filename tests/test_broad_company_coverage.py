"""V4 simulated checks. These do NOT claim live access to any job board."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from src.collector import crawl_lists, extract_list, normalized_url
from src.industry_expansion import (
    base_registry, company_key, homepage_https,
    parse_kgames_directory, parse_kmga_directory, broaden_config
)
from src.monitor import scan, publish
from src.transport import FetchError

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config.yaml').read_text('utf-8'))
NOW=datetime(2026,10,13,9,0,tzinfo=ZoneInfo('Asia/Seoul'))
KHTML='''<section class="partner"><h5>㈜테스트게임즈</h5>
<a href="http://example-studio.kr/jobs">회사 홈페이지</a></section>
<section><h5>모리사와코리아</h5><a href="https://fonts.example/">소개</a></section>
<section><h5>㈜게임사2</h5><a href="https://192.168.1.2/">사내 주소</a></section>'''
MHTML='''<table><tr><td>이사사</td><td></td><td>멤버스튜디오</td></tr>
<tr><td>이사사</td><td></td><td>스쿠티랩스</td></tr></table>'''

class FakeHTTP:
    def __init__(self, mapping=None):
        self.mapping=mapping or {}
        self.calls=[]
        self.requests_made=0
    def get(self,url,*a,**kw):
        self.requests_made+=1
        self.calls.append(url)
        val=self.mapping.get(url,'<html><main>No job postings</main></html>')
        if isinstance(val,Exception):raise val
        return val


def test_registry_is_sourced_not_pretending_careers_urls():
    reg=base_registry()
    assert len(reg)>=70
    assert sum('website' in x for x in reg.values())>=30
    assert reg[company_key('아쿠아트리')].get('website') is None
    assert all(x['evidence'] for x in reg.values())


@pytest.mark.parametrize('url', ['http://127.0.0.1/x','file:///etc/passwd','https://localhost/','https://user:pw@example.com','http://10.0.0.1/','ftp://example.com/','https://example.com:8080/'])
def test_registry_refuses_unsafe_homepages(url):
    assert homepage_https(url) is None


def test_kgames_extracts_nearby_site_not_unrelated_company():
    got=parse_kgames_directory(KHTML)
    assert len(got)==1 and got[0]['name']=='㈜테스트게임즈'
    assert got[0]['website']=='https://example-studio.kr/jobs'


def test_kmga_adds_names_without_inventing_urls():
    got=parse_kmga_directory(MHTML)
    assert len(got)==2
    assert all('website' not in r for r in got)


def test_registry_adds_rotating_sources_with_explicit_source_class():
    cfg={'sources':[], 'industry_expansion':{'enabled':True,'sites_per_run':5}}
    state={}
    runtime,h=broaden_config(cfg,state,NOW,FakeHTTP({'https://www.kgames.or.kr/partnership/partner-list/':KHTML,
                           'https://www.k-mga.or.kr/content/27':MHTML}),0)
    studios=[s for s in runtime['sources'] if s['source_class']=='corporate_discovery']
    assert len(studios)>=30
    assert len([s for s in studios if s['_active_this_run']])==5
    assert all(s['render_js'] for s in studios)  # bounded fallback, only after permitted HTML
    assert h['additional_homepages_registered']==len(studios)
    assert h['company_search_names']>=70
    assert h['directory_last_success']
    assert cfg['sources']==[]   # caller's configuration is not mutated
    assert state['industry_roster_cache']['companies']
    assert any(s['url']=='https://example-studio.kr/jobs' for s in studios)


def test_rotation_fairness_across_runs():
    opts={'sources':[], 'industry_expansion':{'enabled':True,'sites_per_run':9}}
    state={'industry_roster_cache':{'last_attempt':NOW.isoformat()}}
    sites=[]
    for n in range(6):
        cfg,h=broaden_config(opts,state,NOW,FakeHTTP(),n)
        selected={x['id'] for x in cfg['sources'] if x.get('_active_this_run')}
        sites.append(selected)
    assert len(set.union(*sites))>=25
    assert sites[0]!=sites[1]


def test_skipped_longtail_sites_are_not_claimed_checked():
    opts={'sources':[], 'industry_expansion':{'enabled':True,'sites_per_run':2}}
    state={'industry_roster_cache':{'last_attempt':NOW.isoformat()}}
    config,h=broaden_config(opts,state,NOW,FakeHTTP(),0)
    http=FakeHTTP()
    leads,health=crawl_lists(config,http,env={},run_index=0)
    skipped=[s for s in health if s['status']=='scheduled_rotation_skip']
    assert skipped and not any(s['pages'] for s in skipped)
    visited=[s for s in health if s.get('source_class')=='corporate_discovery' and s['pages']]
    assert len(visited)==2
    assert len(http.calls)==2+sum(s['source_class']=='official_careers' for s in config['sources'])
    assert not leads


def test_legacy_jobs_and_source_identity_are_kept_in_runtime():
    cfg={'sources':[],'industry_expansion':{'enabled':True,'sites_per_run':1},
         'max_details_per_scan':1, 'max_listing_runtime_seconds':20}
    state={'jobs':{'https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=111':{
        'title':'Unreal C++ 게임 프로그래머 신입','company':'기존 게임사',
        'source':'legacy','status':'closed','first_seen':NOW.isoformat(),
        'closed_at':NOW.isoformat(),'tier':'review','type':'job','deadline':None}},
        'industry_roster_cache':{'last_attempt':NOW.isoformat()}}
    future,h=scan(cfg,state,NOW,http=FakeHTTP(),env={})
    assert future['version']==4
    assert len(future['jobs'])==1
    assert future['jobs'][next(iter(future['jobs']))]['first_seen']==NOW.isoformat()
    assert h['industry_expansion']['company_search_names']>=70
    assert h['calendar_events'] if 'calendar_events' in h else True


def test_employer_directly_linked_public_job_board_is_supported():
    source={'id':'game_studio','source_class':'corporate_discovery','kind':'official',
            'company':'테스트스튜디오','url':'https://studio.example/','domains':['studio.example']}
    html='<section><h3>C++ Unreal 클라이언트 개발자 신입</h3><a href="https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=901">APPLY</a></section>'
    leads=extract_list(html,source)
    assert len(leads)==1 and 'GI_No=901' in leads[0].url


def test_naver_queries_include_industry_companies_only_when_enabled():
    cfg={'sources':[],'industry_expansion':{'enabled':True},'naver':{'enabled':True,'queries':['gamejob 신입']}}
    state={'industry_roster_cache':{'last_attempt':NOW.isoformat()}}
    runtime,_=broaden_config(cfg,state,NOW,FakeHTTP(),0)
    assert len(runtime['naver']['queries'])>=70
    assert cfg['naver']['queries']==['gamejob 신입']
    assert any('아쿠아트리' in q for q in runtime['naver']['queries'])


def test_directory_failure_retains_seed_registry_and_old_last_success():
    state={'industry_roster_cache':{'last_success':NOW.isoformat()}}
    now=NOW+timedelta(days=8)
    fake=FakeHTTP({r:FetchError('robots_disallowed') for _,r,_ in (
        ('kgames','https://www.kgames.or.kr/partnership/partner-list/',()),
        ('kmga','https://www.k-mga.or.kr/content/27',()))})
    cfg,h=broaden_config({'sources':[], 'industry_expansion':{'enabled':True}},state,now,fake)
    assert h['company_search_names']>=70 and len(h['directory_refresh'])==2
    assert state['industry_roster_cache']['last_success']==NOW.isoformat()


def test_homepage_never_published_as_job_from_directory_name(tmp_path):
    # A URL that is only a homepage must not create a calendar event.
    cfg={'sources':[],'industry_expansion':{'enabled':True,'sites_per_run':2}}
    state={'industry_roster_cache':{'last_attempt':NOW.isoformat()}}
    new,h=scan(cfg,state,NOW,http=FakeHTTP(),env={})
    assert not new.get('jobs')
    publish(cfg,new,h,NOW,tmp_path)
    assert (tmp_path/'site/jobs.json').read_text('utf-8').strip()=='[]'
    assert 'BEGIN:VEVENT' not in (tmp_path/'site/calendar.ics').read_text('utf-8')


def test_published_source_catalog_contains_expanded_company_roster(tmp_path):
    cfg={'sources':[],'industry_expansion':{'enabled':True,'sites_per_run':2}}
    state={'industry_roster_cache':{'last_attempt':NOW.isoformat()}}
    new,h=scan(cfg,state,NOW,http=FakeHTTP(),env={})
    publish(cfg,new,h,NOW,tmp_path)
    import json
    catalog=json.loads((tmp_path/'site/source_catalog.json').read_text('utf-8'))
    assert any(x['source_class']=='corporate_discovery' for x in catalog)
    assert any(x['source_class']=='official_careers' for x in catalog)
    assert len(catalog)>=30
