"""Independent structural checks. Not a substitute for testing on Apple Calendar."""
from pathlib import Path
import json
import re
import sys


def validate_ics(data:bytes):
    text=data.decode('utf-8')
    assert '\r\n' in text,'ICS requires CRLF'
    assert '\n' not in text.replace('\r\n',''),'Found bare LF'
    assert all(len(line)<=75 for line in data.split(b'\r\n')),'75-octet line folding exceeded'
    text=re.sub(r'\r\n[ \t]','',text)
    assert text.startswith('BEGIN:VCALENDAR\r\n') and text.endswith('END:VCALENDAR\r\n')
    stack=[]
    for line in text.split('\r\n'):
        if line.startswith('BEGIN:'):stack.append(line[6:])
        elif line.startswith('END:'): assert stack.pop()==line[4:],'Unbalanced component'
    assert not stack
    uids=re.findall(r'^UID:(.+)$',text,re.M)
    assert len(uids)==len(set(uids)),'Duplicate UID'
    assert len(uids)==text.count('BEGIN:VEVENT'),'Event missing UID'
    for event in text.split('BEGIN:VEVENT')[1:]:
        assert 'DTSTART' in event and 'SUMMARY:' in event and 'DTSTAMP:' in event
    return len(uids)


def validate(root):
    root=Path(root)
    state=json.loads((root/'data/state.json').read_text())
    assert isinstance(state['jobs'],dict)
    counts={p.name:validate_ics(p.read_bytes()) for p in sorted((root/'site').glob('*.ics'))}
    health=json.loads((root/'site/health.json').read_text())
    assert counts['calendar.ics']==health['calendar_events']
    return counts

if __name__=='__main__': print(json.dumps(validate(sys.argv[1] if len(sys.argv)>1 else '.'),ensure_ascii=False))
