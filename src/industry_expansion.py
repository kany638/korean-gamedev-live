"""Broad, honest Korean game-studio discovery based on a sourced seed roster.

A member-directory entry is *not* an active job or a verified careers page.
Only safe, public HTTPS company homepages become rotating discovery sources.
Directory responses cannot insert credentialed, private, or unsupported URLs.
An optional, authorized Naver API supplies search discovery for name-only studios.
"""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import yaml
from bs4 import BeautifulSoup

from .transport import FetchError, public_https

ROOT = Path(__file__).resolve().parents[1]

DIRECTORIES = (
    ('kgames', 'https://www.kgames.or.kr/partnership/partner-list/', ('kgames.or.kr',)),
    ('kmga', 'https://www.k-mga.or.kr/content/27', ('k-mga.or.kr',)),
)
# A game-industry association also lists agencies, advertising suppliers and
# non-development companies. These are not assumed to hire game programmers.
EXCLUDED = (
    '메가존', 'morisawa', '모리사와', '인크로스', '원스토어', 'discord',
    'sk플래닛', '알리바바', '마케팅', '광고', '미디어', '아카데미',
    '라티스글로벌', '대학', '학원', '아트트리', '메타엠', '교육',
    '스폰서', 'YANGO', '법무', '도브러너', '플리더스', '행사',
)


def company_key(name):
    # Normalization for duplicate discovery, not a legal corporate identity.
    s = str(name or '').strip().lower()
    s = re.sub(r'^(?:\(주\)|㈜|주식회사\s*|\(유\)|유한회사\s*)', '', s)
    s = re.sub(r'\s+', '', s)
    return s


def homepage_https(url):
    """Fail closed on unsafe URLs, non-web protocols, credentialed or private hosts.

    Original association members sometimes provide HTTP homepages. Upgrade to
    HTTPS but do not claim the upgraded page works until it is actually fetched.
    """
    if not isinstance(url, str):
        return None
    value = url.strip()
    if not value.startswith(('http://', 'https://')):
        return None
    p = urlparse(value)
    try:
        if p.username or p.password or p.port not in (None, 80, 443) or not p.hostname:
            return None
    except ValueError:
        return None
    try:
        public_https('https://' + p.hostname + '/')
    except FetchError:
        return None
    host = p.hostname.lower()
    if host in ('www.google.com', 'forms.gle', 'www.naver.com', 'naver.com', 'youtube.com'):
        return None
    # Avoid automating marketing tracking URLs embedded in association profiles.
    return urlunparse(('https', host, p.path or '/', '', '', ''))


def active_developer_name(name):
    if not isinstance(name, str):
        return False
    name = name.strip()
    return 2 <= len(name) <= 90 and not any(ex.lower() in name.lower() for ex in EXCLUDED)


def parse_kgames_directory(html):
    """Extract association-listed names and *attached* homepage links only.

    Never infer a URL by matching the company name to a random internet domain.
    """
    soup = BeautifulSoup(html, 'html.parser')
    seen = {}
    for heading in soup.select('h3,h4,h5,h6'):
        name = heading.get_text(' ', strip=True)
        if not active_developer_name(name):
            continue
        parent = heading
        url = None
        # Use nearby content only. A link elsewhere on the page is not proof.
        for _ in range(3):
            parent = parent.parent
            if parent is None or parent.name in ('body', 'html'):
                break
            if len(parent.get_text(' ', strip=True)) > 450 or len(parent.select('h3,h4,h5,h6')) > 1:
                break
            anchors = parent.select('a[href]')
            for anchor in anchors:
                candidate = homepage_https(anchor.get('href', ''))
                if candidate and not (urlparse(candidate).hostname or '').endswith('kgames.or.kr'):
                    url = candidate
                    break
            if url:
                break
        if url:
            seen[company_key(name)] = {'name': name, 'website': url, 'evidence': 'kgames_live', 'focus': 'studio'}
    return list(seen.values())


def parse_kmga_directory(html):
    """Member names are discovery candidates, NOT verified official career URLs."""
    soup = BeautifulSoup(html, 'html.parser')
    rows = {}
    for tr in soup.select('table tr'):
        cells = tr.select('td')
        if len(cells) < 2:
            continue
        # The table normally labels its first cell (부회장사 / 이사사).
        if not re.search(r'부회장사|이사사|회원사', cells[0].get_text(' ', strip=True)):
            continue
        candidates = [c.get_text(' ', strip=True) for c in cells[1:3]]
        name = next((c for c in candidates if active_developer_name(c) and len(c) < 75), None)
        if not name:
            continue
        rows[company_key(name)] = {'name': name, 'evidence': 'kmga_live', 'focus': 'unknown'}
    return list(rows.values())


def base_registry(path=None):
    path = Path(path) if path else ROOT / 'industry_registry.yaml'
    data = yaml.safe_load(path.read_text('utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('companies'), list):
        raise ValueError('industry_registry_schema_invalid')
    result = {}
    for row in data['companies']:
        if not isinstance(row, dict) or not active_developer_name(row.get('name')):
            continue
        safe_url = homepage_https(row.get('website'))
        r = {'name': row['name'], 'evidence': row.get('evidence', 'seed'),
             'focus': row.get('focus', 'unknown')}
        if safe_url:
            r['website'] = safe_url
            r['career_verified'] = row.get('career_verified') is True
        result[company_key(row['name'])] = r
    return result


def _get(http, url, domains):
    # Lightweight fakes used in tests only take a URL; production PublicHTTP
    # enforces robots, HTTPS, content-type and the per-source domain allowlist.
    from .transport import PublicHTTP
    if isinstance(http, PublicHTTP):
        return http.get(url, allowed_domains=domains)
    return http.get(url)


def broaden_config(config, state, now, http, run_index=0):
    """Return runtime config and coverage metrics while preserving original state.

    On each run attempt a rotating set of additional published company homepages.
    On a slower cadence try refreshed industry-association directories.
    Fresh *names* from directories with no official site are search-only.
    """
    cfg = copy.deepcopy(config)
    opts = cfg.get('industry_expansion', {})
    if not opts.get('enabled', False):
        return cfg, {'enabled': False, 'company_roster': 0}
    registry = base_registry()
    cache = state.setdefault('industry_roster_cache', {})
    # Preserve prior association discoveries if a later refresh fails.
    for row in cache.get('companies', []):
        if isinstance(row, dict) and active_developer_name(row.get('name')):
            key = company_key(row['name'])
            if key not in registry:
                registry[key] = row
    directory_health = []
    last = cache.get('last_attempt', '')
    refresh_hours = max(24, int(opts.get('directory_refresh_hours', 168)))
    try:
        from datetime import datetime
        last_age = (now - datetime.fromisoformat(last)).total_seconds()/3600 if last else 1e9
    except (ValueError, TypeError):
        last_age = 1e9
    if last_age >= refresh_hours:
        for did, url, domains in DIRECTORIES:
            try:
                html = _get(http, url, domains)
                new = parse_kgames_directory(html) if did == 'kgames' else parse_kmga_directory(html)
                for row in new:
                    k = company_key(row['name'])
                    # Real website URL is added only when explicitly linked.
                    if k not in registry or (not registry[k].get('website') and row.get('website')):
                        registry[k] = row
                directory_health.append({'name': did, 'status': 'directory_parsed', 'members_extracted': len(new)})
            except FetchError as e:
                directory_health.append({'name': did, 'status': e.code, 'members_extracted': 0})
            except Exception:
                directory_health.append({'name': did, 'status': 'directory_parse_or_network_error', 'members_extracted': 0})
        cache['companies'] = [r for r in registry.values() if r.get('evidence', '').endswith('_live')]
        cache['last_attempt'] = now.isoformat()
        if any(x['status'] == 'directory_parsed' for x in directory_health):
            cache['last_success'] = now.isoformat()
        cache['last_health'] = directory_health
    else:
        directory_health = cache.get('last_health', [])
    existing_domains = set()
    for s in cfg['sources']:
        for d in s.get('domains', []):
            existing_domains.add((d[4:] if d.startswith('www.') else d).lower())
    expanded = []
    seen_roots = set()
    search_names = []
    for key, row in sorted(registry.items()):
        search_names.append(row['name'])
        website = row.get('website')
        if not website:
            continue
        host = urlparse(website).hostname or ''
        root = host[4:] if host.startswith('www.') else host
        if root in seen_roots or any(root == d or root.endswith('.' + d) for d in existing_domains):
            continue
        seen_roots.add(root)
        sid = 'studio_' + hashlib.sha256(root.encode()).hexdigest()[:12]
        direct_career = row.get('career_verified') is True
        expanded.append({
            'id': sid, 'name': row['name'] + ' · 홈페이지 경로 탐색',
            'company': row['name'], 'url': website, 'domains': [root],
            'targets': [row['name']], 'source_class': 'official_careers' if direct_career else 'corporate_discovery',
            'mode': 'html', 'kind': 'official', 'priority': 0 if direct_career else 3,
            'max_pages': max(1, min(3, int(opts.get('pages_per_homepage', 2)))),
            'max_portals': 2 if direct_career else 1, 'render_js': True,
            'reference_url': 'https://www.kgames.or.kr/partnership/partner-list/',
            'reference_status': row.get('evidence', 'seed'),
            'note': 'Verified employer careers page; successful live extraction still unproven.' if direct_career else 'Industry directory/homepage discovery only. NOT verified as a careers page.',
            '_rotating_roster': not direct_career,
            '_active_this_run': direct_career,
        })
    # Every source is shown in diagnostics; only N rotating sites get requests.
    per_run = max(1, int(opts.get('sites_per_run', 18)))
    active = set()
    rotating = [s for s in expanded if s['_rotating_roster']]
    if rotating:
        start = (run_index * per_run) % len(rotating)
        active = {rotating[(start+i) % len(rotating)]['id'] for i in range(min(per_run, len(rotating)))}
    for s in rotating:
        s['_active_this_run'] = s['id'] in active
    cfg['sources'].extend(expanded)
    ncfg = cfg.get('naver', {})
    # Search queries do not turn snippets into verified calendar deadlines.
    if ncfg.get('enabled') and opts.get('add_company_search_queries', True):
        originals = list(ncfg.get('queries', []))
        terms = ['"' + n + '" 게임 클라이언트 C++ 신입 채용' for n in search_names]
        # Preserve query rotation across runs rather than fetching just the
        # first N companies or always scanning the same few domains.
        ncfg['queries'] = originals + list(dict.fromkeys(terms))
    return cfg, {
        'enabled': True,
        'source_registry_entries': len(cfg['sources']),
        'original_official_careers': sum(s.get('source_class')=='official_careers' for s in cfg['sources']),
        'additional_homepages_registered': len(rotating),
        'additional_direct_careers_registered': len(expanded)-len(rotating),
        'additional_homepages_scheduled_this_run': len(active),
        'company_search_names': len(search_names),
        'name_only_companies': sum(not r.get('website') for r in registry.values()),
        'directory_refresh': directory_health,
        'directory_last_success': cache.get('last_success'),
        'claim': 'Registered/homepage discovery is not confirmed careers coverage. Source-health lists successes and failures.'
    }
