import json
from datetime import date
import pytest
from src.classifier import experience, graduate_eligibility, deadline, classify, analyze, posting_explicitly_closed
from src.collector import Lead

TODAY=date(2026,10,8)
URL='https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=900001'


def html(title='게임 클라이언트 C++ 프로그래머',exp='신입',extra='',closing='채용시 마감',loc='서울 강남구'):
    return f'<html><body><main><h1>{title}</h1><p>경력<br>{exp}</p><p>고용형태<br>정규직</p><p>근무지역<br>{loc}</p><p>마감일<br>{closing}</p><section>{extra}</section></main></body></html>'


def job(exp='신입',title='게임 클라이언트 C++ 프로그래머',extra=''):
    return classify(Lead(title,URL,'테스트 게임사','gamejob'),html(title,exp,extra),TODAY)


@pytest.mark.parametrize('exp,bucket',[
 ('신입','entry'),('경력무관','no_experience_requirement'),('경력 무관','no_experience_requirement'),
 ('신입/경력','entry'),('신입 및 경력','entry'),('경력 0년','entry'),('경력 0~3년','entry'),
 ('경력 0-2년','entry'),('No experience required','entry'),('Entry-level','entry'),('New graduate','entry'),
 ('경력 1년 이상','stretch'),('경력 2년 이상','stretch'),('경력 3년 이상','stretch'),
 ('경력 1~3년','stretch'),('경력 2~5년','stretch'),('경력 3~7년','stretch'),
 ('1-3 years of experience','stretch'),('2+ years experience','stretch'),
 ('학력무관','unknown'),('Junior','unknown'),('경력','unknown'),('경력 3년 이하','unknown'),
])
def test_experience_variants(exp,bucket):
    j=job(exp)
    assert j is not None
    assert j['experience_bucket']==bucket


@pytest.mark.parametrize('exp',['경력 4년 이상','경력 5년 이상','경력 10년','경력 4~7년','5+ years of experience'])
def test_excludes_strict_over_3(exp):
    assert job(exp) is None


def test_education_irrelevant_does_not_cancel_required_years():
    assert job('경력',extra='<h2>자격요건</h2><p>학력무관</p><p>개발 경력 5년 이상 필수</p>') is None


def test_preferred_experience_not_required():
    j=job('신입',extra='<h2>우대사항</h2><p>개발 경력 5년 이상 우대</p>')
    assert j and j['experience_bucket']=='entry'


def test_conflicting_new_grad_and_5_required_is_review():
    j=job('신입',extra='<h2>자격요건</h2><p>관련 경력 5년 이상 필수</p>')
    assert j and j['tier']=='review'


def test_zero_to_three_is_not_three_year_required():
    assert job('경력 0~3년')['min_years']==0


def test_lower_bound_not_upper_bound():
    j=job('경력 1~3년')
    assert (j['min_years'],j['max_years'])==(1,3)


@pytest.mark.parametrize('title',['시니어 게임 프로그래머','Senior Unreal Engineer','Lead Gameplay Programmer','게임 클라이언트 팀장'])
def test_senior_title(title):
    assert job('경력무관',title) is None


@pytest.mark.parametrize('title',['Unreal 캐릭터 아티스트','게임 기획자','언리얼 애니메이터','QA 게임 테스트','C++ 교육생 모집','게임개발 강사','Technical Artist Unreal'])
def test_non_programming_training(title):
    assert job('신입',title) is None


def test_generic_non_game_cpp_not_accepted():
    j=classify(Lead('C++ 의료기기 개발자',URL,'테스트','gamejob'),html('C++ 의료기기 개발자'),TODAY)
    assert j is None


def test_unity_in_secondary_not_dropped():
    j=job('신입','Unity 게임 클라이언트 프로그래머')
    assert j and j['tier']=='secondary'


def test_reject_students_only():
    assert job('신입','게임 클라이언트 인턴 개발자','<p>대학 재학생만 지원 가능</p>') is None


def test_graduates_and_students_allowed():
    j=job('신입','게임 클라이언트 인턴 개발자','<p>대학 재학생 대상, 기졸업자도 지원 가능</p>')
    assert j and '기졸업자 포함' in j['graduate_eligibility']


def test_expected_graduates_do_not_prove_already_graduated_eligibility():
    j=job('신입','게임 클라이언트 인턴 개발자','<p>2027년 졸업예정자</p>')
    assert j and '확인 필요' in j['graduate_eligibility']


@pytest.mark.parametrize('raw,expected',[
 ('마감일: 2027-05-11','2027-05-11'),('접수 마감일 2027.05.11','2027-05-11'),
 ('마감일 2027년 5월 11일','2027-05-11'),('지원기간 2027-04-26 ~ 2027-05-11','2027-05-11'),
 ('개인정보 공시 2027-05-11',None),('마감일 5/11',None),('등록일 2027-05-11',None),
 ('마감일 2027-02-30',None),('마감일 채용시 마감',None),
])
def test_deadline_cases(raw,expected):
    assert deadline(raw)['deadline']==expected


def test_exact_deadline_time():
    d=deadline('마감일 2027-05-11(화) 17:00')
    assert d['deadline_at']=='2027-05-11T17:00:00+09:00'


def test_iso_utc_deadline_is_converted_to_kst():
    d=deadline('',{'@type':'JobPosting','validThrough':'2027-05-11T18:00:00Z'})
    assert d['deadline']=='2027-05-12' and d['deadline_at'].endswith('+09:00')


def test_naive_jsonld_timestamp_is_date_only():
    d=deadline('',{'@type':'JobPosting','validThrough':'2027-05-11T17:00:00'})
    assert d['deadline']=='2027-05-11' and d['deadline_at'] is None


def test_until_filled_ignores_jsonld_placeholder():
    d=deadline('마감일 채용시 마감',{'@type':'JobPosting','validThrough':'2099-12-31'})
    assert d['deadline'] is None


def test_jsonld_organization_title_and_deadline():
    data={'@context':'https://schema.org','@type':'JobPosting','title':'Unreal Gameplay Developer',
      'hiringOrganization':{'@type':'Organization','name':'Fixture Studio'},
      'description':'신입 게임플레이 개발자를 모집합니다. Unreal C++ 개발, 서울 근무. 포트폴리오 필수.',
      'validThrough':'2027-05-11T17:00:00+09:00'}
    body='<html><script type="application/ld+json">'+json.dumps(data)+'</script><main>게임 채용 안내입니다. 자세한 직무 내용은 다음을 확인하십시오.</main></html>'
    j=classify(Lead('게임 프로그래머',URL,'Unknown','gamejob'),body,TODAY)
    assert j and j['company']=='Fixture Studio' and j['deadline_at']=='2027-05-11T17:00:00+09:00'


def test_footer_closed_text_does_not_close_listing():
    body=html()+ '<footer>이벤트 접수가 종료되었습니다.</footer>'
    assert not posting_explicitly_closed(body)


def test_expired_posting_excluded():
    j=classify(Lead('게임 프로그래머',URL,'테스트','gamejob'),html(closing='2026-09-30'),TODAY)
    assert j is None

@pytest.mark.parametrize('title', ['게임 아트 인턴십','캐릭터 모델링 인턴','Game Artist Internship','게임 디자인 인턴'])
def test_art_internship_is_not_programming_internship(title):
    lead=Lead(title,'https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=887766','테스트','gamejob')
    job=classify(lead,'<main><h1>'+title+'</h1><p>신입 경력무관 Unreal 게임 개발팀에서 근무합니다. 기졸업자 및 졸업예정자 지원 가능.</p></main>',date(2026,10,8))
    assert job is None


def test_english_zero_to_three_range():
    result=experience('Experience: 0 to 3 years\nGame programmer role','Game programmer')
    assert result['min_years']==0 and result['max_years']==3
    assert result['experience_bucket']=='entry'
