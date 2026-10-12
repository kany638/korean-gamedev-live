"""Write deployment-independent collection status into the GitHub run summary."""
import json,os
from pathlib import Path
h=json.loads(Path('site/health.json').read_text('utf-8'))
lines=['# Recruitment monitor status','',f"Run status: **{h['run_status']}**",f"Detail records parsed: **{h['verified_detail_records']}**; new matches: **{h['new_matches']}**; changed: **{h['changed_matches']}**.",'','A green deploy proves hosting, not exhaustive job collection. Review each source below.','','|Source|Class|List/API status|Links|Details parsed|Matches|','|---|---|---|---:|---:|---:|']
for s in h['sources']:
    vals=[s['id'],s.get('source_class','unknown'),s['status'],s.get('discovered',0),s.get('detail_verified',0),s.get('matched',0)]
    lines.append('|'+ '|'.join(str(v).replace('|','/') for v in vals)+'|')
text='\n'.join(lines)+'\n'
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write(text)
else:print(text)
if not h['verified_detail_records']:print('::warning::No detailed postings verified in this run. Check source-health reporting; do not interpret zero matches as zero vacancies.')
