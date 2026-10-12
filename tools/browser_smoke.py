"""Offline dashboard browser QA with authored JSON. No live site/API is contacted."""
import argparse,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from playwright.sync_api import sync_playwright


def main():
    p=argparse.ArgumentParser();p.add_argument('--chromium');p.add_argument('--report',default='docs/v3_browser_results.json');args=p.parse_args()
    results=[]
    initial=(ROOT/'site/index.html').read_text()
    initial=re.sub(r'<script[^>]*src=[^>]*></script>','',initial)
    initial=re.sub(r'<link[^>]*rel="stylesheet"[^>]*>','',initial)
    initial=initial.replace('<head>','<head><base href="https://example.invalid/fixture/">')
    data={x:json.loads((ROOT/'site'/x).read_text()) for x in ('health.json','jobs.json','source_catalog.json')}
    with sync_playwright() as pw:
        options={'headless':True}
        if args.chromium:options['executable_path']=args.chromium
        browser=pw.chromium.launch(**options);page=browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        # Pure local DOM setup; managed browser/network blocks prevent external
        # navigation in this build environment. Do not bypass those blocks.
        page.set_content(initial);page.add_style_tag(content=(ROOT/'site/style.css').read_text())
        page.evaluate('(data)=>{window.__fixture=data;window.fetch=async path=>({ok:true,json:async()=>window.__fixture[path]});}',data)
        page.add_script_tag(content=(ROOT/'site/dashboard.js').read_text())
        page.wait_for_function("document.querySelectorAll('#sources tr').length>=43")
        assert '배포' in page.locator('#banner').inner_text();results.append({'test':'undeployed_warning_visible','passed':True})
        assert page.locator('#sources tr').count()==44;results.append({'test':'all_43_registry_entries_plus_optional_search_visible','passed':True})
        page.select_option('#source-filter','official_careers');assert page.locator('#sources tr').count()==31;results.append({'test':'official_company_filter_31','passed':True})
        page.select_option('#source-filter','official_program');assert page.locator('#sources tr').count()==3;results.append({'test':'official_program_filter_3','passed':True})
        page.select_option('#source-filter','job_board');assert page.locator('#sources tr').count()==9;results.append({'test':'jobboard_filter_9','passed':True})
        assert '채용시장이 비어' in page.locator('#jobs').inner_text();results.append({'test':'empty_results_not_zero_vacancies','passed':True})
        page.select_option('#source-filter','official_careers');page.screenshot(path=str(ROOT/'docs/v3_dashboard_initial.png'),full_page=False)
        assert not errors;results.append({'test':'no_dashboard_javascript_errors','passed':True})
        browser.close()
    report={'scope':'Offline DOM with mocked JSON fetch only. Managed browser blocked navigation; public-page renderer was NOT live-tested. No employer/API, GitHub deployment or iCloud refresh verification.','tests':results,'passed':len(results)}
    (ROOT/args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
