"""Rule-based suitability extraction, not an AI hiring/eligibility guarantee.

All text is untrusted data. There is no LLM, code execution or auto-application.
Experience, education, role, source verification, and deadlines are distinct.
"""
from __future__ import annotations
import json
import html as html_lib
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .collector import Lead

TZ=ZoneInfo('Asia/Seoul')
PROGRAMMER=re.compile(r'프로그래머|프로그래밍|개발자|개발직|엔지니어|programmer|engineer|developer',re.I)
GAME=re.compile(r'게임|game|Unreal|언리얼|UE[45]|게임플레이',re.I)
TECH=re.compile(r'C\+\+|Unreal|언리얼|UE\s?[45]|게임플레이|gameplay',re.I)
OTHER_ROLE=re.compile(r'기획자|게임\s*기획|게임\s*디자인|(?:아트|art)\s*인턴|\bartist\b|캐릭터\s*모델링|디자이너|아티스트|애니메이터|모델러|이펙터|원화|마케팅|인사팀|리크루터|고객\s*센터|\bQA\b|technical artist|테크니컬\s*아티스트',re.I)
SENIOR=re.compile(r'\b(senior|principal|staff|lead)\b|시니어|팀장|수석|실장|테크\s*리드',re.I)
PROGRAM=re.compile(r'인턴십|인턴|공채|채용연계|넥토리얼|NexTorial|GENIUS|internship',re.I)
TRAINING=re.compile(r'국비|아카데미|교육생|부트캠프|강사|튜터|교육과정',re.I)
FULLDATE=r'(20\d{2})\s*(?:[./-]|년\s*)\s*(\d{1,2})\s*(?:[./-]|월\s*)\s*(\d{1,2})(?:일)?'
DATE_RE=re.compile(FULLDATE)


def normalize(text):
    return re.sub(r'\s+',' ',text or '').strip()


def plain(html):
    return BeautifulSoup(str(html or ''),'html.parser').get_text('\n',strip=True)


def value(obj):
    if isinstance(obj,dict):
        return str(obj.get('name',obj.get('value','')))
    return str(obj or '')


def label_value(raw,label):
    lines=[x.strip() for x in raw.splitlines() if x.strip()]
    for i,line in enumerate(lines):
        if line.rstrip(':： ') == label:
            return lines[i+1][:300] if i+1<len(lines) else ''
        match=re.match(r'^'+re.escape(label)+r'\s*[:：]\s*(.+)$',line)
        if match:
            return match[1][:300]
    return ''


def required_section(raw):
    # Preferred requirements cannot become mandatory years of experience.
    text=re.split(r'우대사항|우대\s*요건|우대조건|Preferred Qualifications|Nice to have|Benefits|복리후생',raw,maxsplit=1,flags=re.I)[0]
    return '\n'.join(x for x in text.splitlines() if not re.search(r'우대|preferred|nice.to.have',x,re.I))[:10000]


def _years(text):
    """Return minimum, maximum, evidence. Upper bounds alone have no known minimum."""
    text=text.replace('–','~').replace('—','~').replace('～','~')
    patterns=[
        (r'(\d{1,2})\s*(?:~|-|to)\s*(\d{1,2})\s*(?:년|years?)', 'range'),
        (r'(\d{1,2})\s*년\s*(?:~|-)\s*(\d{1,2})\s*년','range'),
        (r'(\d{1,2})\s*년\s*(이하|미만)','upper'),
        (r'(?:up to|less than)\s*(\d{1,2})\s*years?','upper'),
        (r'(\d{1,2})\s*\+?\s*(?:년|years?)\s*(?:이상|경력|experience|of experience|\+)?','min'),
    ]
    for pat,kind in patterns:
        matches=list(re.finditer(pat,text,re.I))
        # Ignore durations of internships/contracts and graduation dates.
        matches=[m for m in matches if not re.search(r'인턴\s*기간|계약\s*기간|졸업|19\d{2}|20\d{2}',text[max(0,m.start()-12):m.end()])]
        if not matches:
            continue
        if kind=='range':
            m=max(matches,key=lambda m:int(m[1])); low,high=int(m[1]),int(m[2])
            return (low,high,m[0]) if low<=high else (None,None,'conflicting experience range')
        if kind=='upper':
            return None,int(matches[0][1]),matches[0][0]
        m=max(matches,key=lambda m:int(m[1]))
        return int(m[1]),None,m[0]
    return None,None,''


def experience(raw,title,structured=None):
    field=label_value(raw,'경력') or label_value(raw,'Experience') or ''
    required=required_section(raw)
    # Mandatory body years matter even when the header says '신입/경력'.
    context=title+'\n'+field+'\n'+required
    # Only lines that look like experience requirements; no employment duration.
    lines=[x for x in context.splitlines() if re.search(r'경력|experience|years|신입|junior|entry|graduate|\d\s*[~\-]\s*\d\s*년',x,re.I)]
    relevant='\n'.join(lines)
    low,high,evidence=_years(relevant)
    explicit_entry=bool(re.search(r'신입|경력\s*없[어음]|경험\s*없[어음]|무경력|no\s+(?:prior\s+)?(?:work\s+)?experience|entry[ -]?level|new\s*grad(?:uate)?|fresh\s*grad',context,re.I))
    irrelevant=bool(re.search(r'경력\s*무관|경험\s*무관|experience\s*(?:not required|irrelevant)',context,re.I))
    # DO NOT match bare '무관': 학력무관 is not 경력무관.
    if structured:
        code=str(structured.get('code',''))
        if code in ('0','1','3'):
            irrelevant=irrelevant or code=='0'
            explicit_entry=explicit_entry or code in ('1','3')
        if low is None and code=='2':
            try:
                low=int(structured['min'])
                high=int(structured['max']) if structured.get('max') not in (None,'') else None
                evidence=f'API 경력 최소 {low}년 / 최대 {high}'
            except (KeyError,TypeError,ValueError):
                pass
    out={'min_years':low,'max_years':high,'experience_evidence':evidence}
    if low is not None and low>3:
        if explicit_entry or irrelevant:
            return dict(out,experience_bucket='unknown',experience='신입 표시와 경력 필수요건 충돌 · 확인 필요',eligible=True)
        return dict(out,experience_bucket='excluded',experience=f'경력 {low}년 이상 필수',eligible=False)
    if low is not None and 1<=low<=3:
        # A mixed intake may explicitly offer a new-graduate path.
        if explicit_entry and re.search(r'신입\s*[/·ㆍ,및]\s*경력|신입\s*및\s*경력|신입\s*또는\s*경력',title+' '+field):
            return dict(out,experience_bucket='mixed',experience='신입/경력 병행 · 개별 직무 조건 확인',eligible=True)
        if explicit_entry and '신입' in title and not field:
            return dict(out,experience_bucket='unknown',experience='신입 제목과 경력 조건 충돌 · 확인 필요',eligible=True)
        return dict(out,experience_bucket='stretch',experience=f'경력 {low}년'+(f'~{high}년' if high is not None else ' 이상')+' 요구 · 도전 지원',eligible=True)
    if irrelevant:
        return dict(out,experience_bucket='no_experience_requirement',experience='경력무관',eligible=True)
    if explicit_entry or low==0:
        return dict(out,experience_bucket='entry',experience='신입 / 경력 0년 지원 경로',eligible=True)
    if re.search(r'\bjunior\b|주니어',title,re.I):
        return dict(out,experience_bucket='unknown',experience='주니어 · 최소 경력 별도 확인',eligible=True)
    return dict(out,experience_bucket='unknown',experience='경력 최소요건 확인 필요',eligible=True)


def graduate_eligibility(raw,is_intern):
    scope=required_section(raw)
    graduates=bool(re.search(r'기\s*졸업자|졸업생|졸업자\s*(?:및|또는|도|,|/|포함)|graduates\s*(?:welcome|eligible)',scope,re.I))
    student_only=bool(re.search(r'재학생\s*만|재학생에\s*한함|재학\s*중인\s*(?:학부생|대학생)|학부\s*재학생\s*대상|대학\s*재학생\s*대상|휴학생에\s*한함|current students only',scope,re.I))
    if student_only and not graduates:
        return '재학생 전용 · 기졸업자 부적합',False
    if graduates:
        return '기졸업자 포함 문구 확인 · 기타 조건은 원문 확인',True
    if is_intern:
        return '인턴 졸업자 자격 확인 필요 (졸업예정만으로 기졸업 자격 확정 불가)',True
    return '재학생 전용 제한 미발견 · 학위/비자 등은 원문 확인',True


def _date_match(m):
    try:
        return date(int(m[1]),int(m[2]),int(m[3])).isoformat()
    except ValueError:
        return None


def iso_deadline(text):
    if not text:
        return None,None
    text=str(text).strip()
    if re.fullmatch(r'20\d{2}-\d{2}-\d{2}',text):
        try: return date.fromisoformat(text).isoformat(),None
        except ValueError: return None,None
    try:
        stamp=datetime.fromisoformat(text.replace('Z','+00:00'))
        if stamp.tzinfo is not None:
            kst=stamp.astimezone(TZ)
            return kst.date().isoformat(),kst.isoformat()
        # Timezone missing: retain date only; do not invent an exact instant.
        return stamp.date().isoformat(),None
    except ValueError:
        return None,None


def deadline(raw,structured=None):
    """Use a labelled full-year end date or a JobPosting's validThrough only."""
    d=None; exact=None; evidence='마감일 미확인'; until=False
    # A close-type override is stronger than placeholder expiration timestamps.
    if structured and structured.get('_trusted_adapter')=='saramin_api':
        kind=str(structured.get('close-type',{}).get('code',''))
        if kind in ('2','3','4'):
            return {'deadline':None,'deadline_at':None,'deadline_basis':'API 상시/채용시 · placeholder 날짜 무시','until_filled':True}
        if kind=='1':
            d,exact=iso_deadline(structured.get('expiration-date'))
            if d is None:
                try:
                    stamp=datetime.fromtimestamp(int(structured['expiration-timestamp']),TZ)
                    d,exact=stamp.date().isoformat(),stamp.isoformat()
                except (KeyError,TypeError,ValueError,OverflowError,OSError):
                    pass
            evidence='사람인 API 접수 마감일 (close-type=1)'
    else:
        labelled=re.search(r'(?:접수\s*마감일|지원\s*마감일|마감일|접수\s*마감|Application Deadline)\s*[:：]?\s*('+FULLDATE+r')',raw,re.I)
        if labelled:
            # Inner full-date capture begins at group 2.
            d=_date_match((None,labelled[2],labelled[3],labelled[4]))
            suffix=raw[labelled.end():labelled.end()+35]
            tm=re.match(r'\s*(?:\([^)]{1,4}\))?\s*(\d{1,2}):(\d{2})',suffix)
            if tm and d and int(tm[1])<24 and int(tm[2])<60:
                exact=datetime.fromisoformat(d+f'T{int(tm[1]):02}:{tm[2]}:00').replace(tzinfo=TZ).isoformat()
                evidence='공고 마감일/시각 문구 · 한국 공고의 현지시각(KST)'
            else:
                evidence='공고의 명시적 마감일 · 시각 미확인'
        if not d:
            period=re.search(r'(?:접수\s*기간|모집\s*기간|지원\s*기간|Application period)\s*[:：]?([^\n]{0,250}(?:\n[^\n]{0,150})?)',raw,re.I)
            if period:
                dates=list(DATE_RE.finditer(period[1]))
                if len(dates)>=2 and re.search(r'~|～|–|부터| to ',period[1]):
                    d=_date_match(dates[1]); evidence='공고 지원기간 종료일 · 시각 미확인'
        until=bool(re.search(r'(?:마감일|접수\s*기간)?\s*[:：]?\s*(?:채용\s*시\s*마감|상시\s*채용|until filled|open until filled)',raw,re.I))
        if not d and not until and structured and structured.get('@type')=='JobPosting':
            d,exact=iso_deadline(structured.get('validThrough'))
            if d: evidence='공고 JobPosting.validThrough'
    return {'deadline':d,'deadline_at':exact,'deadline_basis':evidence,'until_filled':until}


def extract_posting(html):
    soup=BeautifulSoup(html,'html.parser')
    structured=None
    def walk(x):
        if isinstance(x,list):
            for y in x: yield from walk(y)
        if isinstance(x,dict):
            if x.get('@type')=='JobPosting' or ('JobPosting' in x.get('@type',[]) if isinstance(x.get('@type'),list) else False):
                yield x
            if '@graph' in x: yield from walk(x['@graph'])
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            structured=next(walk(json.loads(s.string or s.get_text())),None)
            if structured: break
        except (ValueError,TypeError):
            pass
    for bad in soup(['script','style','nav','footer','aside','header']):
        bad.decompose()
    scope=soup.select_one('[itemtype="https://schema.org/JobPosting"]') or soup.select_one('main') or soup
    raw=scope.get_text('\n',strip=True)
    raw=re.split(r'본\s*채용정보는|기업뉴스|추천\s*채용정보|함께\s*본\s*공고',raw,maxsplit=1)[0]
    h=scope.find('h1')
    title=h.get_text(' ',strip=True) if h else ''
    if structured:
        title=plain(structured.get('title','')) or title
        raw+='\n'+plain(structured.get('description',''))
    return raw[:30000],title,structured


def posting_explicitly_closed(html):
    raw,_,_=extract_posting(html)
    return bool(re.search(r'채용이\s*마감|접수가\s*종료|모집이\s*종료|마감되었습니다|no longer accepting applications|position has been filled',raw[:3500],re.I))


def analyze(lead:Lead,html:str|None,asof:date):
    api=lead.metadata if lead.metadata.get('_trusted_adapter')=='saramin_api' else None
    gh=lead.metadata.get('record') if lead.metadata.get('_trusted_adapter')=='greenhouse_public_api' else None
    if gh is not None:
        # Full official public API content is not a search snippet. Updated_at is
        # deliberately NOT used as an application deadline.
        structured_job={'@context':'https://schema.org','@type':'JobPosting',
            'title':gh.get('title',lead.title),'description':html_lib.unescape(gh.get('content','')),
            'hiringOrganization':{'name':lead.company}}
        if gh.get('application_deadline'):
            structured_job['validThrough']=gh['application_deadline']
        location=gh.get('location',{}).get('name','')
        html='<main><h1>'+html_lib.escape(str(structured_job['title']))+'</h1><p>근무지역<br>'+html_lib.escape(str(location))+'</p>'+structured_job['description']+'</main><script type="application/ld+json">'+json.dumps(structured_job,ensure_ascii=False).replace('</',r'<\/')+'</script>'
    structured=None
    title=lead.title
    company=lead.company
    if api:
        if str(api.get('active','1'))!='1':
            return None,'closed'
        pos=api.get('position',{})
        raw='\n'.join([title,'경력',value(pos.get('experience-level')),
            '근무지역',value(pos.get('location')),'고용형태',value(pos.get('job-type')),
            '업종',value(pos.get('industry')),'학력',value(pos.get('required-education-level')),
            '직무',value(pos.get('job-code'))])
        structured=api
    else:
        if not html:
            return None,'unreadable'
        raw,actual_title,structured=extract_posting(html)
        if actual_title and (PROGRAMMER.search(actual_title) or PROGRAM.search(actual_title)):
            title=actual_title[:180]
        if len(raw)<40:
            return None,'unreadable'
        if posting_explicitly_closed(html):
            return None,'closed'
        if structured:
            org=structured.get('hiringOrganization',{})
            if isinstance(org,dict) and org.get('name'):
                company=plain(org['name'])
    if TRAINING.search(title): return None,'training_not_job'
    if SENIOR.search(title): return None,'senior_title'
    has_programmer=bool(PROGRAMMER.search(title))
    # Unreal artist/QA != Unreal programmer. Include QA automation only as secondary.
    if OTHER_ROLE.search(title) and not has_programmer:
        return None,'non_programming_role'
    program=bool(PROGRAM.search(title)) and not has_programmer
    if not has_programmer and not program and not re.search(r'클라이언트.*(?:C\+\+|UE5)|(?:C\+\+|UE5).*클라이언트',title,re.I):
        return None,'role_unclear_or_not_programming'
    if not program and not GAME.search(title+'\n'+raw[:2500]):
        return None,'not_game_development'
    xp=experience(raw,title,api.get('position',{}).get('experience-level') if api else None)
    if not xp['eligible']: return None,'experience_over_3'
    employment=label_value(raw,'고용형태') or value(structured.get('employmentType')) if structured else label_value(raw,'고용형태')
    is_intern=bool(re.search(r'인턴|intern',title+' '+employment,re.I))
    grad,eligible=graduate_eligibility(raw,is_intern)
    if not eligible: return None,'students_only'
    close=deadline(raw,structured)
    if lead.metadata.get('_discovery_kind')=='dated_program_page' and not close['deadline']:
        return None,'program_dates_unconfirmed'
    if close['deadline'] and close['deadline']<asof.isoformat():
        return None,'expired'
    location=label_value(raw,'근무지역') or label_value(raw,'근무지')
    if not location and structured and structured.get('jobLocation'):
        loc=structured['jobLocation']; loc=loc[0] if isinstance(loc,list) and loc else loc
        if isinstance(loc,dict):
            address=loc.get('address',{})
            location=' '.join(str(address.get(k,'')) for k in ('addressCountry','addressRegion','addressLocality')) if isinstance(address,dict) else str(address)
    if re.search(r'미국|일본|싱가포르|베트남|United States|Japan',location or '',re.I) and not re.search(r'한국|서울|경기|원격|remote',location or '',re.I):
        return None,'outside_target_country'
    role_text=title+' '+raw[:2500]
    secondary=bool(re.search(r'Unity|유니티|C#|HTML5|Cocos|서버|backend|게임\s*툴|tools programmer',role_text,re.I)) and not TECH.search(title)
    if program:
        fit='모집 프로그램 · 프로그래밍 직무 및 졸업자 자격 확인'; tier='review'; score=30
    elif secondary:
        fit='보조 분야 · Unity/C#/서버/툴 등 기술스택 확인'; tier='secondary'; score=55
    elif TECH.search(role_text):
        fit='C++ / Unreal / 게임플레이 우선'; tier='primary'; score=90
    else:
        fit='게임 클라이언트/엔진/프로그래밍 · 스택 확인'; tier='primary'; score=75
    if xp['experience_bucket']=='unknown': tier='review'; score=min(score,60)
    elif xp['experience_bucket']=='stretch' and tier=='primary': tier='stretch'; score=min(score,80)
    if is_intern and '확인 필요' in grad and tier=='primary': tier='review'
    # General API metadata may omit the actual detailed required qualifications.
    verification='official_public_api' if gh is not None else 'authorized_api_metadata' if api else 'direct_page_parsed'
    note='API 요약 필드만 확인. 상세 지원조건/포트폴리오/졸업자 제한은 원문 검토.' if api else '자동 규칙 분류. 학위/비자/졸업연도 등 최종 자격은 원문 검토.'
    job=dict(title=normalize(title)[:180],company=normalize(company)[:90],url=lead.url,
        source=lead.source,location=normalize(location) or '근무지 확인 필요',
        employment=normalize(employment) or ('인턴 · 전환 여부 확인' if is_intern else '고용형태 확인 필요'),
        graduate_eligibility=grad,fit=fit,tier=tier,score=score,
        type='program' if program else 'internship' if is_intern else 'job',
        verification=verification,notice=note,**close,**{k:v for k,v in xp.items() if k!='eligible'})
    if gh is not None:
        job['public_api_board']=lead.metadata['board_token']
        job['public_api_job_id']=str(gh.get('id',''))
    return job,'matched'


def classify(lead,html,asof):
    return analyze(lead,html,asof)[0]
