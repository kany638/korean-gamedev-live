"""Authored fixtures, NOT live employer data or official hidden tests."""
import copy
import json
from pathlib import Path
from datetime import date,timedelta
import pytest
import yaml
from src.collector import (extract_list,configure_domains,normalized_url,career_portals,
    official_detail_url,crawl_lists,greenhouse_records,Lead)
from src.transport import PublicHTTP,FetchError
from src.classifier import classify
from src.monitor import scan
from src.browser import PublicRenderer
from test_pipeline import NOW,HTTP,detail

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config.yaml').read_text())
configure_domains(CFG)
OFFICIAL=[s for s in CFG['sources'] if s['source_class']=='official_careers']

def src(id): return next(copy.deepcopy(s) for s in CFG['sources'] if s['id']==id)

def test_registry_separates_companies_programs_boards():
    from collections import Counter
    assert Counter(s['source_class'] for s in CFG['sources'])=={'official_careers':31,'official_program':3,'job_board':9}
    assert len({s['id'] for s in CFG['sources']})==43

@pytest.mark.parametrize('source',OFFICIAL,ids=[s['id'] for s in OFFICIAL])
def test_every_official_source_has_exact_route_and_provenance(source):
    assert source['url'].startswith('https://') and source['domains']
    assert source['reference_url'] and source['reference_checked']=='2026-10-08'
    assert source['reference_status'] and source['targets']
    assert source['priority']==0
    assert source['mode'] in ('html','public_api')
    assert normalized_url(source['url'])

@pytest.mark.parametrize('url',[
    'https://careers.nexon.com/recruit/123456?corpCodes=AG',
    'https://career.lionheart.co.kr/job/abc12345',
    'https://apply.supercat.co.kr/o/abcdef12',
    'https://job-boards.greenhouse.io/5minlab/jobs/123456',
    'https://recruit.wemade.com/job/abcdefgh',
    'https://www.jobkorea.co.kr/Recruit/GI_Read/123456',
    'https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=999',
    'https://www.pearlabyss.com/ko-KR/Company/Careers/detail?_jobOpeningNo=88',
    'https://webzen.recruiter.co.kr/career/job/12345',
    'https://careers.devsisters.com/ko/position/abcdef12',
])
def test_official_detail_identity(url): assert official_detail_url(url)

@pytest.mark.parametrize('url',[
    'https://careers.nexon.com/recruit?corpCodes=AG',
    'https://recruit.krafton.com/',
    'https://recruit.wemade.com/oz6xlsi9',
    'https://www.hound13.com/en',
    'https://www.neowiz.com/kr/career/browse-job',
    'https://www.pearlabyss.com/ko-KR/Company/Careers/List',
])
def test_corporate_or_list_page_not_a_job(url): assert not official_detail_url(url)


def test_nexongames_corporation_filter_is_not_stripped():
    s=src('nexongames')
    assert 'corpCodes=AG' in normalized_url(s['url'])
    assert s['url']!=src('nexon')['url']


def test_com2us_official_redirect_target_not_wrong_holdings_portal():
    s=src('com2us')
    assert 'com2us.recruiter.co.kr' in s['domains']
    assert not any('com2usholdings' in u for u in [s['url']]+s.get('entry_points',[]))


def test_official_apply_button_uses_nearby_role_heading():
    s=src('hound13')
    html='<main><section><h3>Unreal 게임 클라이언트 프로그래머 신입</h3><a href="https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=901">APPLY</a></section><section><h3>캐릭터 아티스트</h3><a href="https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=902">APPLY</a></section></main>'
    rows=extract_list(html,s)
    assert len(rows)==1 and rows[0].source=='hound13' and rows[0].url.endswith('901')


def test_jsonld_list_is_discovery_not_deadline_verification():
    s=src('devsisters')
    row={'@type':'JobPosting','title':'게임 C++ 프로그래머 신입','url':'https://careers.devsisters.com/ko/position/abcdef12','validThrough':'2099-12-31'}
    rows=extract_list('<script type="application/ld+json">'+json.dumps(row)+'</script>',s)
    assert len(rows)==1 and rows[0].metadata=={}


def test_next_data_extraction_and_unknown_domain_rejection():
    s=src('lionheart')
    data={'props':{'pageProps':{'jobs':[{'title':'Unreal 게임 클라이언트 개발자','url':'https://career.lionheart.co.kr/job/abcdef12'},{'title':'게임 개발자','url':'https://evil.example/jobs/123456'}]}}}
    rows=extract_list('<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script>',s)
    assert len(rows)==1 and rows[0].source=='lionheart'


def test_official_portal_follows_only_declared_domains_not_privacy():
    s=src('nexongames')
    h='<a href="https://careers.nexon.com/recruit?corpCodes=AG">채용공고</a><a href="https://attacker.example/jobs">채용공고</a><a href="/adopt/privacy">개인정보 채용공고</a>'
    assert career_portals(h,'https://www.nexongames.co.kr/adopt/job.php',s)==['https://careers.nexon.com/recruit?corpCodes=AG']


def test_every_html_root_attempted_before_secondary_pages():
    sources=[src('pearlabyss'),src('nexon'),src('gamejob')]
    http=HTTP({s['url']:'<main>JavaScript application</main>' for s in sources})
    leads,h=crawl_lists({'sources':sources},http,env={})
    assert http.calls[:3]==[s['url'] for s in sources]
    assert not leads and all(x['status'] in ('no_extractable_links','parser_or_network_error') for x in h[:-1])


def test_root_failure_does_not_stop_later_company():
    a,b=src('nc'),src('shiftup')
    http=HTTP({a['url']:FetchError('http_403'),b['url']:'<main>Jobs app</main>'})
    _,h=crawl_lists({'sources':[a,b]},http,env={})
    assert b['url'] in http.calls and h[0]['status']=='http_403'


def test_source_order_rotates_within_priority_not_boards_before_companies():
    a,b,c=src('nc'),src('shiftup'),src('gamejob')
    http=HTTP({s['url']:'<main>Jobs app</main>' for s in (a,b,c)})
    crawl_lists({'sources':[a,b,c]},http,env={},run_index=1)
    assert http.calls[:3]==[b['url'],a['url'],c['url']]


def test_http_denial_never_triggers_browser_bypass():
    s=src('shiftup')
    class Renderer:
        def render(self,*args): raise AssertionError('must not render denied page')
    _,h=crawl_lists({'sources':[s]},HTTP({s['url']:FetchError('robots_disallowed')}),env={},renderer=Renderer())
    assert h[0]['status']=='robots_disallowed' and 'render_status' not in h[0]


def test_js_rendered_link_is_discovered_and_still_needs_detail_fetch():
    s=src('shiftup'); url='https://shiftup.co.kr/recruit/job/123456'
    class Renderer:
        def render(self,*args):return f'<main><a href="{url}">Unreal 게임 프로그래머 신입</a></main>'
    leads,h=crawl_lists({'sources':[s]},HTTP({s['url']:'<div id="root"></div>'}),env={},renderer=Renderer())
    assert len(leads)==1 and h[0]['status']=='candidates_found'
    assert h[0]['detail_verified']==0 and h[0]['pages'][-1]['rendered']


def test_renderer_budget_and_missing_dependency_are_reported():
    renderer=PublicRenderer(None,{'enabled':True,'max_pages_per_run':0})
    with pytest.raises(FetchError,match='browser_page_budget_reached'):
        renderer.render(src('nc')['url'],src('nc'),'<html></html>')


def greenhouse_payload(deadline=None):
    row={'id':123456,'title':'C++ 게임 클라이언트 프로그래머 신입','absolute_url':'https://job-boards.greenhouse.io/5minlab/jobs/123456',
         'content':'<p>게임 개발 업무</p><p>경력: 신입 또는 경력무관</p><p>C++ Unreal 게임 클라이언트 프로그래밍</p><p>근무지역: 서울</p>',
         'location':{'name':'서울'},'updated_at':'2099-12-31T12:00:00Z'}
    if deadline: row['application_deadline']=deadline
    return row


def test_greenhouse_public_content_not_updated_at_as_deadline():
    s=src('five_min_lab'); rows=greenhouse_records({'jobs':[greenhouse_payload()]},s)
    assert len(rows)==1
    j=classify(rows[0],None,date(2026,10,8))
    assert j and j['deadline'] is None and j['verification']=='official_public_api'
    assert j['public_api_board']=='5minlab'


def test_greenhouse_documented_application_deadline():
    s=src('five_min_lab'); lead=greenhouse_records({'jobs':[greenhouse_payload('2027-05-11T08:00:00Z')]},s)[0]
    j=classify(lead,None,date(2026,10,8))
    assert j['deadline']=='2027-05-11' and j['deadline_at'] is not None


def test_greenhouse_only_approved_board_read_access():
    h=PublicHTTP(delay=0)
    with pytest.raises(FetchError,match='public_api_board_not_approved'):
        h.greenhouse_json('not-configured')
    h.allowed_greenhouse_boards={'5minlab'}
    with pytest.raises(FetchError,match='public_api_job_id_invalid'):
        h.greenhouse_json('5minlab','../../applications')


def test_official_api_reverification_updates_existing_event():
    s=src('five_min_lab')
    class GH:
        requests_made=0
        def greenhouse_json(self,board,jobid=None):
            self.requests_made+=1
            return {'jobs':[greenhouse_payload('2027-05-11T08:00:00Z')]} if jobid is None else greenhouse_payload('2027-05-12T08:00:00Z')
    state,h=scan({'sources':[s]}, {'jobs':{}},NOW,GH(),env={})
    job=list(state['jobs'].values())[0]
    assert job['deadline']=='2027-05-12' and job['source_class']=='official_careers'
    later,h=scan({'sources':[s]},state,NOW+timedelta(hours=5),GH(),env={})
    assert len(later['jobs'])==1 and h['new_matches']==0


def test_source_history_preserves_previous_success_when_root_fails():
    s=src('shiftup'); url='https://shiftup.co.kr/recruit/job/123456'
    listing=f'<main><a href="{url}">C++ 게임 프로그래머 신입</a></main>'
    state,h=scan({'sources':[s]}, {'jobs':{}},NOW,HTTP({s['url']:listing,url:detail()}),env={})
    old=state['source_history'][s['id']]['last_listing_success']
    state,h=scan({'sources':[s]},state,NOW+timedelta(hours=5),HTTP({s['url']:FetchError('network_error'),url:FetchError('network_error')}),env={})
    assert state['source_history'][s['id']]['last_listing_success']==old
    assert h['sources'][0]['checked_at']!=old


def test_capped_new_company_details_are_queued_for_later():
    s=src('shiftup'); urls=['https://shiftup.co.kr/recruit/job/12345'+str(i) for i in range(3)]
    listing='<main>'+''.join(f'<a href="{u}">C++ 게임 프로그래머 신입</a>' for u in urls)+'</main>'
    http=HTTP({s['url']:listing,**{u:detail() for u in urls}})
    state,h=scan({'sources':[s],'max_details_per_scan':1},{'jobs':{}},NOW,http,env={})
    assert len(state['pending'])==2 and h['deferred_detail_links']==2
    state,h=scan({'sources':[s],'max_details_per_scan':2},state,NOW+timedelta(hours=5),HTTP({s['url']:'<main>empty</main>',**{u:detail() for u in urls}}),env={})
    assert len(state['jobs'])>=2


def test_programme_root_announcements_need_actual_dated_intake():
    s=src('com2us_genius')
    html='<html><title>2027 컴투스 인턴십 GENIUS</title><main>게임 클라이언트 C++ 인턴십<p>경력: 신입</p><p>기졸업자 지원 가능</p><p>모집기간: 2027-05-12 ~ 2027-05-26</p></main></html>'
    rows=extract_list(html,s)
    assert len(rows)==1 and rows[0].url==normalized_url(s['url'])
    j=classify(rows[0],html,date(2027,5,13))
    assert j and j['deadline']=='2027-05-26' and j['tier']=='review'
    assert classify(rows[0],html,date(2027,6,1)) is None


def test_programme_evergreen_information_cannot_become_deadline():
    s=src('com2us_genius')
    html='<html><title>2027 컴투스 인턴십 GENIUS</title><main>게임 클라이언트 C++ 인턴십 안내. 매년 5월에 지원하고 7월부터 근무합니다. 경력: 신입. 기졸업자 지원 가능.</main></html>'
    row=extract_list(html,s)[0]
    assert classify(row,html,date(2027,1,1)) is None
