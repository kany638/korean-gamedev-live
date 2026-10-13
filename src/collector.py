"""Public HTML discovery plus optional documented Saramin/Naver adapters.

A configured source is not a successfully monitored source. Every run reports
fetch/parse/detail status separately. Search snippets never become deadlines.
"""
from __future__ import annotations

import os
import json
import time
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode
from bs4 import BeautifulSoup
from .transport import PublicHTTP, FetchError, authorization_only

KNOWN_DOMAINS = {
    'gamejob.co.kr', 'jobkorea.co.kr', 'saramin.co.kr', 'indeed.com',
    'wanted.co.kr', 'incruit.com', 'jumpit.saramin.co.kr', 'linkedin.com',
    'rocketpunch.com', 'pearlabyss.com', 'careers.nexon.com',
    'rct.smilegate.com', 'neowiz.com', 'recruit.krafton.com', 'career.netmarble.com',
    'career.lionheart.co.kr', 'recruit.kakaogames.com', 'welcom2us.com',
    'recruit.webzen.co.kr', 'shiftup.co.kr', 'careers.ncsoft.com',
    'jobs.lever.co', 'career.greetinghr.com', 'job-boards.greenhouse.io',
    'recruit.wemade.com', 'devsisters.com', 'careers.devsisters.com',
    'recruit.com2us.com', 'recruit.kog.co.kr', 'kog.co.kr', 'nexon-tutorial.com',
}
TITLE_HINT = re.compile(
    r'프로그래머|프로그래밍|개발자|개발직|엔지니어|클라이언트|언리얼|Unreal|UE[45]|C\+\+|'
    r'게임플레이|Gameplay|engineer|programmer|developer|채용연계|인턴|intern|'
    r'공채|넥토리얼|NexTorial|GENIUS', re.I)
BAD_NAV = re.compile(r'개인정보|채용문의|회사소개|지원현황|로그인|지원서 작성|인재풀 등록')
ID_PARAMS = {'gi_no','_jobopeningno','rec_idx','id','jobid','job_id','announcementid',
             'seq','companyid','jopenid','no','idx','recruitno','jobno','jk','jobpostingid',
             'postingid','announcement_no','anno_id','annoId','recruit_idx','page','sitecode'}


@dataclass(frozen=True)
class Lead:
    title: str
    url: str
    company: str
    source: str
    metadata: dict = field(default_factory=dict, compare=False)
    # Trusted adapter metadata only; search snippets never certify a posting.


def configure_domains(config: dict) -> None:
    """Only operator-configured public careers/ATS domains enter the discovery allowlist."""
    for source in config.get('sources', []):
        for domain in source.get('domains', []):
            domain = domain.lower().strip('.')
            if re.fullmatch(r'[a-z0-9.-]+', domain) and '.' in domain:
                KNOWN_DOMAINS.add(domain)


def host_allowed(host: str) -> bool:
    return any(host == d or host.endswith('.' + d) for d in KNOWN_DOMAINS) or host.endswith('.recruiter.co.kr')


def normalized_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or p.username or p.password or p.port not in (None,80,443):
        return ''
    host = (p.hostname or '').lower()
    if not host_allowed(host):
        return ''
    if host in ('gamejob.co.kr','m.gamejob.co.kr'):
        host = 'www.gamejob.co.kr'
    if host == 'pearlabyss.com':
        host = 'www.pearlabyss.com'
    path = p.path.rstrip('/') or '/'
    pairs = parse_qsl(p.query)
    if 'gamejob.co.kr' in host:
        number = next((v for k,v in pairs if k.lower() == 'gi_no' and v.isdigit()), None)
        if number:
            return 'https://www.gamejob.co.kr/Recruit/GI_Read/View?GI_No=' + number
    if host.endswith('saramin.co.kr'):
        number = next((v for k,v in pairs if k.lower() == 'rec_idx' and v.isdigit()), None)
        if number:
            return 'https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=' + number
    # Keep meaningful query identifiers/filters; stripping corpCodes or gh_jid can
    # silently switch employers or collapse different postings into one event.
    tracking = {'gclid','fbclid','msclkid','ref','referrer','source','tracking','utm_source'}
    secret = {'access-key','access_key','token','auth','password','key','signature'}
    if any(k.lower() in secret for k,v in pairs):
        return ''
    keep = [(k,v) for k,v in pairs if not k.lower().startswith('utm_') and k.lower() not in tracking]
    fragment = p.fragment if p.fragment.startswith(('/', '!/')) else ''
    return urlunparse(('https',host,path,'',urlencode(sorted(keep)),fragment))


def candidate_title(title: str) -> bool:
    return 3 <= len(title) <= 230 and bool(TITLE_HINT.search(title)) and not BAD_NAV.search(title)


def clean_text(value: str) -> str:
    return BeautifulSoup(value or '', 'html.parser').get_text(' ', strip=True)


def extract_list(html: str, source: dict, page_url=None) -> list[Lead]:
    origin = page_url or source['url']
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    kind = source.get('kind', 'html')
    patterns = [re.compile(x,re.I) for x in source.get('patterns', [])]
    for a in soup.select('a[href]'):
        href = urljoin(origin,a['href'])
        title = a.get_text(' ',strip=True)
        if kind == 'official' and not candidate_title(title):
            title = nearby_title(a) or title
        if not candidate_title(title):
            continue
        if kind == 'gamejob' and not re.search(r'/Recruit/GI_Read/View\?GI_No=\d+',href,re.I):
            continue
        if kind == 'jobkorea' and not re.search(r'/Recruit/GI_Read/\d+',href,re.I):
            continue
        if kind == 'pearlabyss':
            if not re.search(r'/Company/Careers/(detail|view)',href,re.I):
                continue
            p=urlparse(href)
            if p.path.lower().startswith('/company/careers/'):
                href=urlunparse(('https','www.pearlabyss.com','/ko-KR'+p.path,'',p.query,''))
            title=re.split(r'상시채용|20\d{2}[-./]\d{1,2}[-./]\d{1,2}',title,maxsplit=1)[0].strip()
        if kind == 'official':
            if not source_host_allowed(href,source) or not official_detail_url(href, origin):
                continue
        elif kind not in ('gamejob','jobkorea','pearlabyss'):
            if not patterns or not any(p.search(href) for p in patterns):
                continue
        url=normalized_url(href)
        if not url or url==normalized_url(origin):
            continue
        company=source.get('company') or '회사 원문 확인'
        row=a.find_parent('tr') if source.get('source_class','job_board')=='job_board' else None
        if row:
            cells=row.find_all('td',recursive=False)
            if cells:
                name=cells[0].get_text(' ',strip=True)
                if name and len(name)<80 and name!=title:
                    company=name
        found[url]=Lead(title[:180],url,company,source['id'])
    if kind in ('official','pearlabyss'):
        for lead in embedded_leads(soup,source,origin):
            found.setdefault(lead.url,lead)
    if source.get('source_class')=='official_program':
        for heading in soup.find_all(['title','h1','h2']):
            title=heading.get_text(' ',strip=True)
            if re.search(r'20\d{2}',title) and re.search(r'인턴|공채|넥토리얼|GENIUS|NexTorial',title,re.I) and len(title)<180:
                url=normalized_url(origin)
                if url:
                    found[url]=Lead(title,url,source.get('company','회사 원문 확인'),source['id'],{'_discovery_kind':'dated_program_page'})
                break
    return list(found.values())


def next_pages(html, origin):
    soup=BeautifulSoup(html,'html.parser')
    urls=[]
    for a in soup.select('a[href]'):
        title=a.get_text(' ',strip=True)
        if not (title.isdigit() or title in ('다음','Next','next','>','›')):
            continue
        href=urljoin(origin,a['href'])
        p,q=urlparse(href),urlparse(origin)
        if p.scheme=='https' and p.netloc==q.netloc and p.path==q.path and href!=origin:
            urls.append(href)
    return list(dict.fromkeys(urls))


def source_status(source, status, found=0, **extra):
    return dict(id=source['id'],name=source['name'],url=source['url'],mode=source['mode'],
                source_class=source.get('source_class','job_board'), status=status,discovered=found,
                detail_attempts=0,detail_verified=0,matched=0,pages=[],**extra)


def saramin_records(data) -> list[Lead]:
    """Only API-provided metadata; closure type controls whether a date is real."""
    if not isinstance(data,dict) or 'jobs' not in data:
        raise FetchError('api_error_or_schema_change')
    jobs=data['jobs'].get('job',[])
    if isinstance(jobs,dict):
        jobs=[jobs]
    found=[]
    for j in jobs:
        pos=j.get('position',{})
        title=clean_text(pos.get('title',''))
        url=normalized_url(j.get('url',''))
        if not title or not url:
            continue
        metadata=dict(j)
        metadata['_trusted_adapter']='saramin_api'
        company=j.get('company',{}).get('detail',{}).get('name','회사 원문 확인')
        found.append(Lead(title,url,company,'saramin',metadata))
    return found


def saramin_discovery(source,cfg,http,secret):
    leads=[]
    returned=0
    # Conservative default: at most 120 records/run -> 360 records/3 scheduled runs.
    # Provider's actual granted quota/terms take precedence. Manual reruns also count.
    cap=min(120,int(cfg.get('max_records_per_run',120)))
    for keyword in cfg.get('keywords',['언리얼','게임개발','게임프로그래머','클라이언트']):
        if returned>=cap:
            break
        data=http.api_json('https://oapi.saramin.co.kr/job-search',params={
            'access-key':secret,'keywords':keyword,'count':min(30,cap-returned),
            'start':0,'sort':'ud','fields':'posting-date,expiration-date'},
            headers={'Accept':'application/json'})
        rows=saramin_records(data)
        returned+=len(data.get('jobs',{}).get('job',[]))
        leads.extend(rows)
    return leads,returned


def naver_records(data,sources):
    found=[]
    for item in data.get('items',[]):
        title=clean_text(item.get('title',''))
        url=normalized_url(item.get('link',''))
        if not url or not candidate_title(title):
            continue
        host=urlparse(url).hostname or ''
        source=next((s for s in sources if any(host==d or host.endswith('.'+d) for d in s.get('domains',[]))),None)
        # Search discovery is not enough to claim a role/deadline verified.
        if source:
            found.append(Lead(title[:180],url,source.get('company') or '회사 원문 확인',source['id']))
    return found



# Employer navigation and embedded data are discovery only. Each candidate still
# needs a detail request or a documented official API response before publication.
CAREERS_NAV = re.compile(r'\bapply\b|채용\s*공고|진행\s*중.*채용|채용\s*중|모집\s*공고|입사\s*지원|채용정보|채용안내|인재채용|전체\s*공고|채용사이트|채용페이지|recruit|careers?|job\s*openings?|open\s*positions?|join\s*us|vacanc|지원하기|공고\s*확인하기',re.I)


TRUSTED_PUBLIC_JOB_LINK_HOSTS = ('job-boards.greenhouse.io', 'boards.greenhouse.io',
                                 'jobs.lever.co', 'career.greetinghr.com',
                                 'gamejob.co.kr', 'recruiter.co.kr')


def source_host_allowed(url, source):
    host = (urlparse(url).hostname or '').lower()
    if any(host == d or host.endswith('.'+d) for d in source.get('domains',[(urlparse(source['url']).hostname or '')])):
        return True
    # A genuine employer careers/homepage may link to a separately hosted ATS.
    # Do not follow arbitrary cross-domain links; only known public job portals
    # actually linked by the employer and still subject to transport/robots.
    return source.get('source_class') in ('official_careers', 'corporate_discovery') and any(
        host == d or host.endswith('.'+d) for d in TRUSTED_PUBLIC_JOB_LINK_HOSTS)


def official_detail_url(url, origin=''):
    """Conservative posting identities, not generic corporate/recruitment roots."""
    if not normalized_url(url) or normalized_url(url)==normalized_url(origin): return False
    p=urlparse(url); path=p.path.lower(); query={k.lower():v for k,v in parse_qsl(p.query)}
    if any(query.get(k) for k in ('gi_no','_jobopeningno','rec_idx','gh_jid','postingid','jobpostingid','recruitno','jobno','jobid','job_id','anno_id','announcementid','seq','jopenid')):
        return True
    if query.get('id') and re.search(r'job|recruit|career|position|posting|announcement',path): return True
    if re.search(r'/(?:jobs?|position|positions|recruit|recruitment|posting|postings|o|gi_read)/[a-z0-9_-]{5,}(?:/|$)',path):
        last=path.rstrip('/').split('/')[-1]
        return last not in {'careers','career','recruit','recruitment','positions','opening','openings','jobopening','jobopenings','announce','index.html','index.php','list','home','info','search'}
    return bool(re.search(r'/(?:detail|view|detail-job)/[a-z0-9_-]{3,}(?:/|$)',path))


def nearby_title(anchor):
    """Some official sites label links APPLY and put the actual role beside them."""
    parent=anchor.parent
    for _ in range(3):
        if parent is None: break
        text=parent.get_text(' ',strip=True)
        headings=parent.find_all(['h1','h2','h3','h4','strong'],recursive=True)
        for h in headings:
            title=h.get_text(' ',strip=True)
            if candidate_title(title): return title
        if headings: return ''
        # Never copy an entire jobs page into a single invented role title.
        if len(text)<=200 and candidate_title(text): return text
        if len(text)>900: break
        parent=parent.parent
    return ''


def embedded_leads(soup,source,origin):
    found={}; visited=0
    def walk(obj,depth=0):
        nonlocal visited
        visited+=1
        if depth>16 or visited>12000: return
        if isinstance(obj,dict):
            title=next((obj[k] for k in ('title','jobTitle','positionTitle','recruitTitle','name') if isinstance(obj.get(k),str) and candidate_title(obj[k])),None)
            rawurl=next((obj[k] for k in ('url','absolute_url','detailUrl','jobUrl','href','link') if isinstance(obj.get(k),str)),None)
            if title and rawurl:
                url=normalized_url(urljoin(origin,rawurl))
                if url and source_host_allowed(url,source) and official_detail_url(url,origin):
                    found[url]=Lead(clean_text(title)[:180],url,source.get('company','회사 원문 확인'),source['id'])
            for v in obj.values(): walk(v,depth+1)
        elif isinstance(obj,list):
            for v in obj[:3000]: walk(v,depth+1)
    for script in soup.find_all('script'):
        if script.get('type')=='application/ld+json' or script.get('id')=='__NEXT_DATA__':
            try: walk(json.loads(script.string or script.get_text()))
            except (ValueError,TypeError,RecursionError): pass
    return list(found.values())


def career_portals(html,origin,source):
    found=[]
    for a in BeautifulSoup(html,'html.parser').select('a[href]'):
        text=a.get_text(' ',strip=True) or a.get('aria-label','')
        raw=urljoin(origin,a['href'])
        if BAD_NAV.search(text) or not CAREERS_NAV.search(text): continue
        url=normalized_url(raw)
        if url and source_host_allowed(url,source) and url!=normalized_url(origin) and not official_detail_url(url,origin):
            found.append(url)
    return list(dict.fromkeys(found))


def greenhouse_records(data,source):
    if not isinstance(data,dict) or not isinstance(data.get('jobs'),list):
        raise FetchError('official_api_schema_changed')
    found=[]
    for row in data['jobs']:
        title=clean_text(row.get('title','')); url=normalized_url(row.get('absolute_url',''))
        if not url or not candidate_title(title): continue
        if not source_host_allowed(url,source): continue
        if not isinstance(row.get('content'),str): continue
        found.append(Lead(title[:180],url,source.get('company','회사 원문 확인'),source['id'],
            {'_trusted_adapter':'greenhouse_public_api','record':row,'board_token':source['board_token']}))
    return found


def crawl_lists(config: dict,http,env=None,renderer=None,run_index=0):
    """Phase 1 touches every configured root; phase 2 follows portals/pages/rendering.

    Budgets and access failures are explicit. No zero-link response certifies an
    empty job market or exhaustive company coverage.
    """
    configure_domains(config)
    env=os.environ if env is None else env
    leads={}; health=[]; extras=[]; sources=config['sources']; started=time.monotonic()
    def budget_ok(): return time.monotonic()-started < config.get('max_listing_runtime_seconds',720)
    # Official employers first, rotation prevents the same late source always
    # losing out when network or browser budgets are exhausted.
    ordered=[]
    for priority in sorted({s.get('priority',2) for s in sources}):
        group=[s for s in sources if s.get('priority',2)==priority]
        offset=run_index%len(group)
        ordered.extend(group[offset:]+group[:offset])
    def store(records,h):
        for lead in records: leads.setdefault(lead.url,lead)
        h['discovered']=len({x.url for x in leads.values() if x.source==h['id']})
    def fetch_page(s,h,url):
        attempt={'url':url,'status':'attempting','rendered':False}
        h['pages'].append(attempt)
        try:
            html=http.get(url,allowed_domains=s.get('domains')) if isinstance(http,PublicHTTP) else http.get(url)
            final=getattr(http,'final_urls',{}).get(url,url)
            attempt.update(status='html_received',final_url=final)
            store(extract_list(html,s,final),h)
            return html,final
        except FetchError as e: attempt['status']=e.code; h['status']=e.code
        except Exception: attempt['status']='parser_or_network_error'; h['status']='parser_or_network_error'
        return None,url
    for s in ordered:
        h=source_status(s,'not_attempted'); health.append(h); mode=s['mode']
        if s.get('_rotating_roster') and not s.get('_active_this_run'):
            h['status']='scheduled_rotation_skip'
            h['note']='Listed for broad discovery; scheduled for another rotation. NOT checked on this run.'
            continue
        if mode in ('manual','authorized_only'):
            h['status']='manual_or_authorized_source_required'; continue
        if mode=='api':
            cfg=config.get('saramin',{})
            if not cfg.get('enabled',False) or not env.get('SARAMIN_ACCESS_KEY'):
                h['status']='not_configured_api_key_required'; continue
            if not budget_ok(): h['status']='listing_time_budget_reached'; continue
            try:
                records,returned=saramin_discovery(s,cfg,http,env['SARAMIN_ACCESS_KEY'])
                store(records,h); h.update(status='api_response_received',records_returned=returned)
            except FetchError as e: h['status']=e.code
            except Exception: h['status']='api_schema_error'
            continue
        if not budget_ok(): h['status']='listing_time_budget_reached'; continue
        if mode=='public_api' and s.get('kind')=='greenhouse':
            try:
                data=http.greenhouse_json(s['board_token'])
                store(greenhouse_records(data,s),h)
                h.update(status='official_api_response_received',records_returned=len(data['jobs']))
            except FetchError as e: h['status']=e.code
            except Exception: h['status']='official_api_schema_error'
            continue
        html,origin=fetch_page(s,h,s['url'])
        if html is not None:
            h['status']='candidates_found' if h['discovered'] else 'no_extractable_links'
            extras.append((s,h,html,origin))
        # A configured alternate (for a renamed/redirected official portal) can be
        # checked even if one route fails; it is not a CAPTCHA/robots bypass.
        elif s.get('entry_points'):
            extras.append((s,h,None,origin))
    # Every root is attempted in company-first order. For *secondary* page
    # discovery, reserve scarce rendering capacity for important job boards,
    # official internship programmes and known employer career routes before
    # generic corporate homepages. Otherwise 30 JS-only company roots can use
    # all browser slots before GameJob/JobKorea is considered.
    board_first = {'gamejob': 0, 'jobkorea': 1, 'saramin': 2, 'wanted': 3, 'incruit': 4}
    extras.sort(key=lambda x: (
        0 if x[0]['id'] in board_first else
        1 if x[0].get('source_class') == 'official_program' else
        2 if x[0].get('source_class') == 'official_careers' else
        3 if x[0].get('source_class') == 'job_board' else 4,
        board_first.get(x[0]['id'], 100), x[0].get('priority', 2)
    ))
    for s,h,first_html,origin in extras:
        cap=int(s.get('max_pages',config.get('max_listing_pages_per_source',3)))
        remaining=max(0,cap-len(h['pages'])); seen={p['url'] for p in h['pages']}
        html_pages=[(first_html,origin)] if first_html is not None else []
        urls=list(s.get('entry_points',[]))
        portals=0
        if first_html is not None:
            linked=career_portals(first_html,origin,s)[:s.get('max_portals',2)]
            urls+=linked+next_pages(first_html,origin); portals+=len(linked)
        while urls and remaining and budget_ok():
            url=urls.pop(0)
            if url in seen or not source_host_allowed(url,s): continue
            seen.add(url); remaining-=1
            html,final=fetch_page(s,h,url)
            if html is not None:
                html_pages.append((html,final))
                linked=career_portals(html,final,s)[:max(0,s.get('max_portals',2)-portals)]
                urls+=linked+next_pages(html,final); portals+=len(linked)
        # Only public HTML received successfully is eligible for JS rendering.
        # Never retry a denied HTTP request using a browser to get around it.
        if not h['discovered'] and renderer and s.get('render_js') and budget_ok():
            for html,url in html_pages:
                try:
                    rendered=renderer.render(url,s,html)
                    h['pages'].append({'url':url,'status':'rendered_received','rendered':True})
                    store(extract_list(rendered,s,url),h)
                    # Rendering may expose the official outbound ATS link.
                    if remaining:
                        for portal in career_portals(rendered,url,s)[:remaining]:
                            if portal in seen: continue
                            seen.add(portal); remaining-=1
                            ph,final=fetch_page(s,h,portal)
                            if ph is not None and not h['discovered']:
                                try:
                                    rendered2=renderer.render(final,s,ph)
                                    h['pages'].append({'url':final,'status':'rendered_received','rendered':True})
                                    store(extract_list(rendered2,s,final),h)
                                except FetchError as e: h['render_status']=e.code
                    if h['discovered']: break
                except FetchError as e: h['render_status']=e.code
                except Exception: h['render_status']='browser_error'
        h['status']='candidates_found' if h['discovered'] else h['status'] if h['status'] not in ('not_attempted','candidates_found') else 'no_extractable_links'
        h['note']='Bounded public-root/portal/detail discovery; not full-site coverage. Zero links does not establish zero vacancies.'
    ncfg=config.get('naver',{})
    nsrc={'id':'naver','name':'네이버 웹문서 API · 발견만','url':'https://developers.naver.com/docs/serviceapi/search/web/web.md','mode':'api','source_class':'search_discovery'}
    nh=source_status(nsrc,'not_configured_api_key_required');health.append(nh)
    if ncfg.get('enabled',False) and all(env.get(x) for x in ('NAVER_CLIENT_ID','NAVER_CLIENT_SECRET')):
        queries=ncfg.get('queries',[]); cap=int(ncfg.get('max_queries_per_run',24)); errors=0; num=0
        offset=(run_index*cap)%len(queries) if queries else 0
        rotated=(queries[offset:]+queries[:offset])[:cap]
        for query in rotated:
            if not budget_ok(): errors+=1; break
            try:
                data=http.api_json('https://openapi.naver.com/v1/search/webkr.json',
                    params={'query':query,'display':30,'start':1},
                    headers={'X-Naver-Client-Id':env['NAVER_CLIENT_ID'],'X-Naver-Client-Secret':env['NAVER_CLIENT_SECRET']})
                if 'items' not in data: raise FetchError('search_api_error')
                rows=naver_records(data,sources); num+=len(rows)
                for lead in rows: leads.setdefault(lead.url,lead)
            except Exception: errors+=1
        nh.update(status='discovery_only_partial' if errors else 'discovery_only',discovered=num,query_errors=errors)
    return list(leads.values()),health
