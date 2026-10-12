import json
from datetime import date
from pathlib import Path
import pytest
import yaml
from src.collector import normalized_url, extract_list, saramin_records, naver_records, crawl_lists, Lead
from src.classifier import classify
from src.transport import PublicHTTP, FetchError, public_https
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('u,expected',[
 ('http://gamejob.co.kr/recruit/GI_READ/View?utm_source=bad&GI_No=123','https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=123'),
 ('https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=777&utm_source=x','https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=777'),
 ('https://www.jobkorea.co.kr/Recruit/GI_Read/123?utm_campaign=x','https://www.jobkorea.co.kr/Recruit/GI_Read/123'),
 ('https://kr.indeed.com/viewjob?jk=abc&utm_source=test','https://kr.indeed.com/viewjob?jk=abc'),
 ('https://evil.com/job/1',''),('javascript:alert(1)',''),('https://name:secret@www.gamejob.co.kr/',''),
])
def test_url_identity(u,expected): assert normalized_url(u)==expected


def test_gamejob_html_adapter():
    s={'id':'gamejob','name':'게임잡','kind':'gamejob','url':'https://www.gamejob.co.kr/Recruit/joblist'}
    h='<table><tr><td>테스트 스튜디오</td><td><a href="/Recruit/GI_Read/View?GI_No=888">C++ 게임 프로그래머 신입</a></td></tr></table>'
    rows=extract_list(h,s)
    assert len(rows)==1 and rows[0].company=='테스트 스튜디오'


def test_jobkorea_html_adapter():
    s={'id':'jobkorea','kind':'jobkorea','url':'https://www.jobkorea.co.kr/recruit/joblist'}
    h='<a href="/Recruit/GI_Read/123456">경력무관 게임 클라이언트 개발자</a>'
    rows=extract_list(h,s)
    assert len(rows)==1 and rows[0].url.endswith('/123456')


def test_pearl_locale():
    s={'id':'pearlabyss','kind':'pearlabyss','company':'펄어비스','url':'https://www.pearlabyss.com/ko-KR/Company/Careers/List'}
    h='<a href="/Company/Careers/detail?_jobOpeningNo=77">게임플레이 프로그래머 모집 상시채용 경력 과천</a>'
    rows=extract_list(h,s)
    assert rows[0].url=='https://www.pearlabyss.com/ko-KR/Company/Careers/detail?_jobOpeningNo=77'


def api_record(code='0',low=0,high=0,close='2'):
    return {'jobs':{'job':[{'id':'333','url':'https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=333',
      'active':1,'company':{'detail':{'name':'Fixture Studio'}},
      'position':{'title':'게임 클라이언트 C++ 개발자','industry':{'name':'게임'},
          'location':{'name':'서울'},'job-type':{'name':'정규직'},
          'experience-level':{'code':code,'min':low,'max':high,'name':'경력무관' if code=='0' else f'경력 {low}~{high}년'}},
      'expiration-date':'2099-12-31T23:59:59+09:00','close-type':{'code':close}}]}}


def test_saramin_authorized_metadata_no_html_needed():
    lead=saramin_records(api_record())[0]
    j=classify(lead,None,date(2026,10,8))
    assert j and j['experience_bucket']=='no_experience_requirement'
    assert j['verification']=='authorized_api_metadata' and j['deadline'] is None


def test_saramin_lower_bound_is_stretch():
    j=classify(saramin_records(api_record('2',1,3))[0],None,date(2026,10,8))
    assert j and j['min_years']==1 and j['tier']=='stretch'


def test_saramin_explicit_close_type():
    j=classify(saramin_records(api_record(close='1'))[0],None,date(2026,10,8))
    assert j['deadline']=='2099-12-31'


def test_saramin_error_not_successful_zero():
    with pytest.raises(FetchError): saramin_records({'code':2,'message':'Invalid access key'})


def test_naver_snippet_is_not_trusted_metadata():
    src=[{'id':'gamejob','domains':['gamejob.co.kr']}]
    records=naver_records({'items':[{'title':'게임 C++ 프로그래머','link':'https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=88',
                                   'description':'마감일 2027-05-11'}]},src)
    assert len(records)==1 and records[0].metadata=={}


def test_optional_apis_disabled_without_keys():
    cfg={'sources':[{'id':'saramin','name':'사람인','url':'https://oapi.saramin.co.kr/guide/job-search','mode':'api'}]}
    class NoRequests:
        def __getattr__(self,n): raise AssertionError('Should not call network')
    leads,h=crawl_lists(cfg,NoRequests(),env={})
    assert not leads and all(x['status']=='not_configured_api_key_required' for x in h)


def test_indeed_registry_is_not_claimed_scraper():
    cfg=yaml.safe_load((ROOT/'config.yaml').read_text())
    indeed=next(s for s in cfg['sources'] if s['id']=='indeed')
    assert indeed['mode']=='authorized_only'
    with pytest.raises(FetchError,match='authorized_integration_required'):
        PublicHTTP().get('https://kr.indeed.com/viewjob?jk=abc')


@pytest.mark.parametrize('url',['http://example.com/','https://127.0.0.1/','https://localhost/','https://foo.local/','https://user:pass@example.com/','https://example.com:8080/'])
def test_private_or_unsafe_urls(url):
    with pytest.raises(FetchError):public_https(url)


def test_all_requested_boards_have_explicit_modes():
    cfg=yaml.safe_load((ROOT/'config.yaml').read_text())
    ids={x['id'] for x in cfg['sources']}
    assert {'gamejob','jobkorea','saramin','indeed','wanted','incruit','linkedin','jumpit','rocketpunch'}<=ids
    assert all(s.get('mode') for s in cfg['sources'])


class Response:
    def __init__(self,text='',status=200,headers=None):
        self.text=text;self.status_code=status;self.headers=headers or {'Content-Type':'text/html'}
        self.encoding='utf-8'
    def iter_content(self,n):yield self.text.encode()


class Session:
    def __init__(self,responses):self.headers={};self.responses=responses;self.calls=[]
    def get(self,url,**kw):self.calls.append(url);return self.responses[url]


def test_robots_denial_stops_detail_request():
    ses=Session({'https://www.gamejob.co.kr/robots.txt':Response('User-agent: *\nDisallow: /Recruit/\n')})
    client=PublicHTTP(session=ses,delay=0)
    with pytest.raises(FetchError,match='robots_disallowed'):
        client.get('https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=1')
    assert len(ses.calls)==1


def test_robots_unavailable_fails_closed():
    ses=Session({'https://www.gamejob.co.kr/robots.txt':Response('',500)})
    with pytest.raises(FetchError,match='robots_unavailable'):
        PublicHTTP(session=ses,delay=0).get('https://www.gamejob.co.kr/Recruit/joblist')


def test_api_error_cannot_leak_query_key():
    url='https://oapi.saramin.co.kr/job-search'
    ses=Session({url:Response('',403)})
    with pytest.raises(FetchError) as error:
        PublicHTTP(session=ses,delay=0).api_json(url,params={'access-key':'PRIVATE_TEST_KEY'})
    assert 'PRIVATE_TEST_KEY' not in str(error.value)
