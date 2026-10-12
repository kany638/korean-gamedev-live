import json
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from src.monitor import scan,publish,published_jobs,choose_queue,read_json
from src.collector import Lead
from src.calendar_feed import make_ics
from src.transport import FetchError
from tools.validate_output import validate,validate_ics

NOW=datetime(2026,10,8,8,12,tzinfo=ZoneInfo('Asia/Seoul'))
LIST='https://www.gamejob.co.kr/Recruit/joblist'
URL='https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=900001'
TITLE='게임 C++ 클라이언트 프로그래머'
SOURCE={'id':'gamejob','name':'게임잡','mode':'html','kind':'gamejob','url':LIST}
CFG={'sources':[SOURCE],'max_listing_pages_per_source':1,'max_details_per_scan':8}
PAGE=f'<table><tr><td>테스트 스튜디오</td><td><a href="{URL}">{TITLE}</a></td></tr></table>'


def detail(exp='신입',date='2027-05-11',text=''):
    return f'<main><h1>{TITLE}</h1><p>경력<br>{exp}</p><p>고용형태<br>정규직</p><p>근무지역<br>서울</p><p>마감일<br>{date}</p><p>{text}</p></main>'


class HTTP:
    def __init__(self,pages):self.pages=pages;self.requests_made=0;self.calls=[]
    def get(self,url):
        self.requests_made+=1;self.calls.append(url)
        obj=self.pages[url]
        if isinstance(obj,Exception):raise obj
        return obj


def initial():
    return scan(CFG,{'jobs':{}},NOW,HTTP({LIST:PAGE,URL:detail()}),env={})


def test_full_simulated_scan_creates_persistent_state_and_calendar(tmp_path):
    state,health=initial()
    publish(CFG,state,health,NOW,tmp_path)
    counts=validate(tmp_path)
    assert counts['calendar.ics']==1
    assert counts['entry.ics']==1
    assert health['verified_detail_records']==1 and health['new_matches']==1
    assert read_json(tmp_path/'data/state.json',{})['jobs'][URL]['min_years'] is None


def test_second_identical_scan_keeps_uid_and_sequence():
    state,h=initial()
    a=make_ics(published_jobs(state,NOW,CFG),NOW)
    later=NOW+timedelta(hours=5)
    state2,h2=scan(CFG,state,later,HTTP({LIST:PAGE,URL:detail()}),env={})
    b=make_ics(published_jobs(state2,later,CFG),later)
    assert next(x for x in a.splitlines() if x.startswith('UID:')) in b
    assert state2['jobs'][URL]['revision']==0
    assert h2['new_matches']==0


def test_deadline_changed_event_moves_same_uid():
    state,h=initial();later=NOW+timedelta(hours=5)
    old=make_ics(published_jobs(state,NOW,CFG),NOW)
    state,h=scan(CFG,state,later,HTTP({LIST:PAGE,URL:detail(date='2027-05-15')}),env={})
    new=make_ics(published_jobs(state,later,CFG),later)
    assert 'DTSTART;VALUE=DATE:20270515' in new
    assert next(x for x in old.splitlines() if x.startswith('UID:')) in new
    assert state['jobs'][URL]['revision']==1 and h['changed_matches']==1


def test_reverification_not_dependent_on_remaining_in_listing():
    state,h=initial();http=HTTP({LIST:'<main>목록 비어있음</main>',URL:detail(date='2027-05-16')})
    newer,h=scan(CFG,state,NOW+timedelta(hours=5),http,env={})
    assert URL in http.calls and newer['jobs'][URL]['deadline']=='2027-05-16'


def test_all_network_failures_preserve_events_and_last_verification():
    state,h=initial();older=state['jobs'][URL]['last_verified']
    later=NOW+timedelta(hours=72)
    newer,h=scan(CFG,state,later,HTTP({LIST:FetchError('network_error'),URL:FetchError('network_error')}),env={})
    assert newer['jobs'][URL]['last_verified']==older
    assert h['run_status']=='degraded_no_verified_details'
    assert published_jobs(newer,later,CFG)[0]['stale'] is True


def test_closed_posting_emits_cancellation():
    state,h=initial();later=NOW+timedelta(hours=5)
    newer,h=scan(CFG,state,later,HTTP({LIST:PAGE,URL:detail(text='채용이 마감되었습니다')}),env={})
    ics=make_ics(published_jobs(newer,later,CFG),later)
    assert 'STATUS:CANCELLED' in ics and 'BEGIN:VALARM' not in ics
    assert newer['jobs'][URL]['status']=='closed'


def test_transient_404_does_not_immediately_close():
    state,h=initial()
    first,h=scan(CFG,state,NOW+timedelta(hours=5),HTTP({LIST:PAGE,URL:FetchError('http_404')}),env={})
    assert first['jobs'][URL]['status']=='open'
    second,h=scan(CFG,first,NOW+timedelta(hours=12),HTTP({LIST:PAGE,URL:FetchError('http_404')}),env={})
    assert second['jobs'][URL]['status']=='closed'


def test_rejected_records_do_not_starve_new_requests():
    lead=Lead(TITLE,URL,'T','gamejob')
    state={'jobs':{},'rejected':{URL:{'last_attempt':NOW.isoformat(),'reason':'experience_over_3'}}}
    assert choose_queue([lead],state,NOW+timedelta(hours=5),10)==[]
    assert choose_queue([lead],state,NOW+timedelta(hours=13),10)==[lead]


def test_old_jobs_get_reserved_slots_when_new_board_has_many_links():
    state,h=initial();later=NOW+timedelta(hours=5)
    new=[Lead(TITLE,'https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No='+str(i),'T','gamejob') for i in range(100,200)]
    selected=choose_queue(new,state,later,4)
    assert len(selected)==4 and any(x.url==URL for x in selected)


def test_three_daily_refresh_opportunities_reverify():
    state,h=initial()
    for hour in (13,20):
        t=NOW.replace(hour=hour)
        state,h=scan(CFG,state,t,HTTP({LIST:PAGE,URL:detail()}),env={})
        assert h['verified_detail_records']==1


def test_corrupt_state_does_not_silently_become_empty(tmp_path):
    p=tmp_path/'broken.json';p.write_text('{broken')
    with pytest.raises(json.JSONDecodeError):read_json(p,{})


def test_review_event_is_not_fake_deadline():
    state,h=scan(CFG,{'jobs':{}},NOW,HTTP({LIST:PAGE,URL:detail(date='채용시 마감')}),env={})
    ics=make_ics(published_jobs(state,NOW,CFG),NOW)
    unfolded=ics.replace('\r\n ','')
    assert '실제 마감일 아님' in unfolded
    assert 'DTSTART;VALUE=DATE:20261010' in ics


def test_ics_utf8_folding_and_escaping():
    state,h=initial();j=state['jobs'][URL]
    j['title']='긴 제목, 세미콜론; 테스트 '+ '한글'*100
    ics=make_ics([j],NOW)
    assert validate_ics(ics.encode())==1
    assert '\\,' in ics and '\\;' in ics


def test_exact_time_event_not_midnight():
    state,h=scan(CFG,{'jobs':{}},NOW,HTTP({LIST:PAGE,URL:detail(date='2027-05-11 17:00')}),env={})
    ics=make_ics(published_jobs(state,NOW,CFG),NOW)
    assert 'DTSTART:20270511T080000Z' in ics


def test_alerts_at_previous_morning_not_midnight():
    state,h=initial()
    ics=make_ics(published_jobs(state,NOW,CFG),NOW)
    assert 'TRIGGER;VALUE=DATE-TIME:20270510T000000Z' in ics


def test_one_uid_per_canonical_url_even_duplicate_records():
    state,h=initial();j=state['jobs'][URL]
    assert validate_ics(make_ics([j,j],NOW).encode())==1


def test_source_with_no_visible_links_is_not_claimed_working():
    state,h=scan(CFG,{'jobs':{}},NOW,HTTP({LIST:'<html>JavaScript app</html>'}),env={})
    assert h['sources'][0]['status']=='no_extractable_links'
    assert h['run_status']=='degraded_no_verified_details'


def test_default_workflow_schedule_and_no_paid_provider():
    import yaml
    root=Path(__file__).resolve().parents[1]
    workflow=yaml.load((root/'.github/workflows/update-live-calendar.yml').read_text(),Loader=yaml.BaseLoader)
    assert workflow['on']['schedule'][0]['cron']=='12 4,11,23 * * *'
    assert workflow['jobs']['scan']['runs-on']=='ubuntu-latest'
    cfg=yaml.safe_load((root/'config.yaml').read_text())
    # These are user-configurable opt-ins, not permanently disabled settings.
    assert isinstance(cfg['naver']['enabled'], bool)
    assert isinstance(cfg['saramin']['enabled'], bool)
    assert len(cfg['naver']['queries'])>=24
    assert cfg['naver']['max_queries_per_run']==24


def test_legacy_state_can_be_reverified_without_losing_first_seen(tmp_path):
    state={'jobs':{URL:{'title':TITLE,'company':'Legacy','source':'gamejob','url':URL,'first_seen':NOW.isoformat()}}}
    newer,health=scan(CFG,state,NOW+timedelta(hours=5),HTTP({LIST:PAGE,URL:detail()}),env={})
    publish(CFG,newer,health,NOW+timedelta(hours=5),tmp_path)
    assert newer['jobs'][URL]['first_seen']==NOW.isoformat()
    assert validate(tmp_path)['calendar.ics']==1


@pytest.mark.parametrize('naver_enabled,saramin_enabled', [
    (False, False), (True, False), (False, True), (True, True),
])
def test_optional_api_flags_do_not_issue_requests_without_credentials(naver_enabled, saramin_enabled):
    """Enabling either adapter is valid, but credentials are still mandatory."""
    from src.collector import crawl_lists

    class NoNetwork:
        def __getattr__(self, name):
            raise AssertionError('Missing API credentials must not cause network access')

    config = {
        'sources': [{
            'id': 'saramin', 'name': '사람인', 'mode': 'api',
            'url': 'https://oapi.saramin.co.kr/guide/job-search',
            'domains': ['saramin.co.kr'],
        }],
        'naver': {'enabled': naver_enabled, 'queries': ['언리얼 신입']},
        'saramin': {'enabled': saramin_enabled},
    }
    leads, health = crawl_lists(config, NoNetwork(), env={})
    assert leads == []
    assert {row['id'] for row in health} == {'naver', 'saramin'}
    assert all(row['status'] == 'not_configured_api_key_required' for row in health)
