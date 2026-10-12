"""Optional public-page rendering with no auth, cookies, proxy or access bypass.

All HTTP(S) browser resources are fetched through the SAME bounded robots-aware
transport; unapproved hosts, POST, downloads and images/media/fonts are blocked.
Thus a public page dependent on a disallowed API can remain unreadable, honestly.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse
from .transport import FetchError


class PublicRenderer:
    def __init__(self,http,config):
        self.http=http; self.config=config; self.used=0
        self._pw=None; self._browser=None; self.blocked_resources=0

    def render(self,url,source,initial_html):
        if not self.config.get('enabled',False): raise FetchError('browser_disabled')
        if self.used>=int(self.config.get('max_pages_per_run',24)):
            raise FetchError('browser_page_budget_reached')
        self.used+=1
        allowed=list(source.get('domains',[]))+list(source.get('browser_resource_domains',[]))
        def allowed_url(u):
            host=urlparse(u).hostname or ''
            return any(host==d or host.endswith('.'+d) for d in allowed)
        if not allowed_url(url): raise FetchError('browser_domain_not_approved')
        try:
            if self._browser is None:
                from playwright.sync_api import sync_playwright
                self._pw=sync_playwright().start()
                options={'headless':True}
                if self.config.get('executable_path'): options['executable_path']=self.config['executable_path']
                self._browser=self._pw.chromium.launch(**options)
        except Exception:
            self.close(); raise FetchError('browser_not_installed_or_unavailable') from None
        context=self._browser.new_context(service_workers='block',accept_downloads=False,
                locale='ko-KR',timezone_id='Asia/Seoul')
        page=context.new_page()
        cache={url:initial_html}; blocked=[]
        def route_handler(route):
            req=route.request; uri=req.url
            if req.method!='GET' or req.resource_type in ('image','media','font') or not allowed_url(uri):
                self.blocked_resources+=1; route.abort(); return
            try:
                body=cache.get(uri)
                if body is None:
                    body=self.http.get(uri,allowed_domains=allowed)
                    cache[uri]=body
                resource=req.resource_type
                ctype='text/javascript' if resource=='script' else 'text/css' if resource=='stylesheet' else 'application/json' if resource in ('xhr','fetch') and body.lstrip().startswith(('{','[')) else 'text/html'
                route.fulfill(status=200,content_type=ctype,body=body)
            except FetchError as e:
                blocked.append(e.code); self.blocked_resources+=1; route.abort()
            except Exception:
                blocked.append('resource_failed'); self.blocked_resources+=1; route.abort()
        context.route('**/*',route_handler)
        try:
            page.goto(url,wait_until='domcontentloaded',timeout=int(self.config.get('timeout_ms',18000)))
            page.wait_for_timeout(int(self.config.get('settle_ms',1800)))
            html=page.content()
            if any(x in html[:5000].lower() for x in ('verify you are human','cf-chl-','captcha challenge')):
                raise FetchError('browser_access_challenge')
            return html
        except FetchError: raise
        except Exception as exc:
            self.last_error_type=type(exc).__name__
            raise FetchError('browser_render_incomplete') from None
        finally: context.close()

    def close(self):
        if self._browser is not None:
            try: self._browser.close()
            except Exception: pass
        if self._pw is not None:
            try: self._pw.stop()
            except Exception: pass
        self._browser=None; self._pw=None
