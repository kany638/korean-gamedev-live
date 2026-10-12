"""Check public deployment artifacts after publishing; does not verify Apple sync.
Usage: python tools/verify_deployment.py https://USERNAME.github.io/korean-gamedev-live/
"""
from __future__ import annotations
import argparse,json,sys
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
from validate_output import validate_ics


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('base_url');a=p.parse_args()
    u=urlparse(a.base_url)
    if u.scheme!='https' or not u.hostname or not u.hostname.endswith('.github.io') or u.username or u.password or u.port not in (None,443):
        p.error('Provide your public HTTPS *.github.io site URL, with no credentials.')
    base=a.base_url.rstrip('/')+'/'
    result={'hosting_accessible':False,'collection_has_verified_detail':False,'apple_icloud_sync':'not_tested','source_coverage':'not_exhaustive'}
    try:
        payload={}
        for name in ('health.json','jobs.json','calendar.ics'):
            r=requests.get(base+name,timeout=25,allow_redirects=False)
            r.raise_for_status()
            if 300<=r.status_code<400:raise ValueError('Unexpected redirect; use final deployed URL')
            payload[name]=r.content if name.endswith('.ics') else r.json()
        h=payload['health.json'];count=validate_ics(payload['calendar.ics'])
        if count!=h['calendar_events'] or count!=len(payload['jobs.json']):raise ValueError('Event count mismatch')
        result.update(hosting_accessible=True,calendar_events=count,run_status=h['run_status'],
                      latest_scan=h.get('last_scan_kst'),verified_detail_records=h.get('verified_detail_records',0),
                      collection_has_verified_detail=bool(h.get('verified_detail_records')),
                      sources=h.get('sources',[]))
        last=h.get('last_scan_kst')
        result['scan_older_than_36_hours']=not last or (datetime.now(timezone.utc)-datetime.fromisoformat(last)).total_seconds()>36*3600
    except Exception as exc:
        # No tokens or private URLs are ever part of error output.
        result['error_type']=type(exc).__name__
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['hosting_accessible'] and result['collection_has_verified_detail'] and not result['scan_older_than_36_hours'] else 2

if __name__=='__main__':sys.exit(main())
