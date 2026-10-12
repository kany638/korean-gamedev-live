"""Bounded HTTPS transport. No login, proxy rotation, CAPTCHA or robots bypass."""
from __future__ import annotations

import ipaddress
import re
import time
from collections import Counter
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import requests

UA = 'KoreanGameDevLiveCalendar/3.0 (personal vacancy metadata monitor)'
# No generic scraping of these providers, including URLs discovered by search APIs.
AUTH_ONLY = ('indeed.com', 'linkedin.com', 'saramin.co.kr')


class FetchError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)  # Never includes query strings or secret headers.


def public_https(url: str) -> str:
    p = urlparse(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise FetchError('unsafe_url')
    if p.port not in (None, 443):
        raise FetchError('unsafe_port')
    host = p.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.internal')):
        raise FetchError('private_host')
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise FetchError('private_ip')
    except ValueError:
        pass
    return host


def authorization_only(host: str) -> bool:
    return any(host == x or host.endswith('.' + x) for x in AUTH_ONLY)


class PublicHTTP:
    """Robots failures are fail-closed. API calls use an explicit endpoint allowlist."""
    def __init__(self, timeout=12, delay=1.0, max_requests=220, domain_limit=50, session=None, max_seconds=720):
        self.timeout = timeout
        self.started = time.monotonic()
        self.max_seconds = max_seconds
        self.delay = delay
        self.max_requests = max_requests
        self.domain_limit = domain_limit
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.7'})
        self.requests_made = 0
        self.counts = Counter()
        self.last = {}
        self.robots = {}
        self.blocked = set()
        self.final_urls = {}
        self.allowed_greenhouse_boards = set()

    def _one(self, url, params=None, headers=None):
        host = public_https(url)
        if time.monotonic() - self.started > self.max_seconds:
            raise FetchError('runtime_budget_reached')
        if host in self.blocked:
            raise FetchError('host_blocked_this_run')
        if self.requests_made >= self.max_requests or self.counts[host] >= self.domain_limit:
            raise FetchError('request_budget_reached')
        pause = self.delay - (time.monotonic() - self.last.get(host, 0))
        if pause > 0:
            time.sleep(pause)
        self.requests_made += 1
        self.counts[host] += 1
        self.last[host] = time.monotonic()
        try:
            r = self.session.get(url, params=params, headers=headers,
                                 timeout=self.timeout, allow_redirects=False, stream=True)
            if r.status_code in (401, 403, 429):
                self.blocked.add(host)
                raise FetchError(f'http_{r.status_code}')
            data = bytearray()
            for block in r.iter_content(65536):
                data.extend(block)
                if len(data) > 4_000_000:
                    raise FetchError('page_too_large')
            r._content = bytes(data)
            return r
        except requests.RequestException:
            raise FetchError('network_error') from None

    def _robots_allowed(self, url):
        host = public_https(url)
        if host not in self.robots:
            r = self._one('https://' + host + '/robots.txt')
            # Do not follow robots redirects to unrelated domains.
            if r.status_code == 404:
                self.robots[host] = None
            elif r.status_code == 200 and not r.text.lstrip().lower().startswith(('<!doctype', '<html')):
                robot = RobotFileParser()
                robot.parse(r.text.splitlines())
                self.robots[host] = robot
            else:
                raise FetchError('robots_unavailable')
        rp = self.robots[host]
        if rp is not None and not rp.can_fetch(UA, url):
            raise FetchError('robots_disallowed')

    def get(self, url: str, allowed_domains=None) -> str:
        original=url
        for _ in range(5):
            host = public_https(url)
            if authorization_only(host):
                raise FetchError('authorized_integration_required')
            if allowed_domains is not None and not any(host==d or host.endswith('.'+d) for d in allowed_domains):
                raise FetchError('redirect_domain_not_approved')
            self._robots_allowed(url)
            r = self._one(url)
            if r.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, r.headers.get('Location', ''))
                continue
            if r.status_code != 200:
                raise FetchError(f'http_{r.status_code}')
            ctype = r.headers.get('Content-Type', '').lower()
            if not any(x in ctype for x in ('html', 'text', 'json', 'xml', 'rss', 'javascript', 'css')):
                raise FetchError('unsupported_content_type')
            if r.encoding in (None, 'ISO-8859-1'):
                r.encoding = r.apparent_encoding or 'utf-8'
            text = r.text
            if any(s in text[:3000].lower() for s in ('verify you are human', 'cf-chl-', 'captcha challenge')):
                raise FetchError('access_challenge')
            self.final_urls[original]=url
            return text
        raise FetchError('too_many_redirects')

    def api_json(self, url, params=None, headers=None):
        # Documented APIs only: no undocumented private endpoints.
        if url not in ('https://openapi.naver.com/v1/search/webkr.json',
                       'https://oapi.saramin.co.kr/job-search'):
            raise FetchError('api_endpoint_not_approved')
        r = self._one(url, params=params, headers=headers)
        if r.status_code != 200:
            raise FetchError(f'api_http_{r.status_code}')
        try:
            return r.json()
        except ValueError:
            raise FetchError('invalid_api_json') from None

    def greenhouse_json(self, board_token, job_id=None):
        """Official documented, read-only public Job Board API; no application POST."""
        if board_token not in self.allowed_greenhouse_boards or not re.fullmatch(r'[A-Za-z0-9_-]+',board_token):
            raise FetchError('public_api_board_not_approved')
        if job_id is not None and not str(job_id).isdigit():
            raise FetchError('public_api_job_id_invalid')
        url='https://boards-api.greenhouse.io/v1/boards/'+board_token+'/jobs'
        if job_id is not None: url+='/'+str(job_id)
        r=self._one(url,params={'content':'true'} if job_id is None else None)
        if r.status_code!=200: raise FetchError('public_api_http_'+str(r.status_code))
        try: return r.json()
        except ValueError: raise FetchError('public_api_invalid_json') from None
