"""RFC 5545 feed writer for Apple Calendar subscriptions."""
from __future__ import annotations
import hashlib
from datetime import date, datetime, timedelta, timezone


def escape_text(text: str) -> str:
    return str(text or '').replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '').replace(';', '\\;').replace(',', '\\,')


def fold(line: str) -> str:
    # 75 octets per physical iCalendar line; continuation begins with SPACE.
    chunks = []
    buf = ''
    length = 0
    for ch in line:
        b = len(ch.encode('utf-8'))
        if length + b > 75:
            chunks.append(buf)
            buf = ' ' + ch
            length = 1 + b
        else:
            buf += ch
            length += b
    chunks.append(buf)
    return '\r\n'.join(chunks)


def event(job: dict, now: datetime, review_after_days: int = 2) -> list[str]:
    first_seen = date.fromisoformat(job['first_seen'][:10])
    deadline = job.get('deadline')
    event_day = date.fromisoformat(deadline) if deadline else first_seen + timedelta(days=review_after_days)
    uid = hashlib.sha256(job['url'].encode('utf-8')).hexdigest()[:24] + '@gamedev-live.example'
    title = job['title'][:38]
    name = job['company'][:16]
    tag = '마감' if deadline else '검토'
    if job.get('status') == 'closed': tag = '마감됨'
    elif job.get('stale'): tag = '재확인'
    elif job.get('tier') == 'stretch': tag = '도전·' + tag
    summary = f'{name} · {tag} · {title}'
    lines = [
        '실제 공고/API의 마감일' if deadline else '첫 발견 후 검토 알림: 실제 마감일 아님 / 공고 등록일 아님',
        f'회사: {job["company"]}', f'직무: {job["title"]}',
        f'경력: {job.get("experience", "확인 필요")}',
        f'경력 근거: {job.get("experience_evidence", "최소 경력 명시 없음")}',
        f'고용: {job.get("employment", "확인 필요")}',
        f'적합성: {job.get("fit", "확인 필요")}',
        f'기졸업자: {job.get("graduate_eligibility", "확인 필요")}',
        f'근무지: {job.get("location", "확인 필요")}',
        f'확인 방식: {job.get("verification", "확인 필요")}',
        f'최근 원문/API 확인: {job.get("last_verified", "미확인")}',
        f'첫 발견: {job["first_seen"]}',
        f'마감 근거: {job.get("deadline_basis", "미확인")}',
        f'공고 시각: {job.get("deadline_at") or "정확한 시각 미확인; 종일표시는 자정 마감이 아님"}',
        f'출처: {job["url"]}', job.get('notice', ''),
        '모든 사이트/공고의 완전수집 또는 자격 충족을 보장하지 않음. 지원 전 원문 확인.',
    ]
    if job.get('stale'): lines.insert(0, '주의: 최근 원문 재확인 실패/지연. 최신 공고 상태를 직접 확인하십시오.')
    if job.get('status') == 'closed': lines.insert(0, '모집 종료/지원대상 아님을 확인한 공고입니다.')
    if job.get('source') == 'saramin': lines.append('Powered by 취업 사람인 https://www.saramin.co.kr')
    stamp = now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    modified = datetime.fromisoformat(job.get('updated_at', now.isoformat())).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    items = ['BEGIN:VEVENT',f'UID:{uid}',f'DTSTAMP:{stamp}',f'LAST-MODIFIED:{modified}',
             f'SEQUENCE:{int(job.get("revision", 0))}']
    exact = job.get('deadline_at')
    if exact:
        dt = datetime.fromisoformat(exact).astimezone(timezone.utc)
        items += [f'DTSTART:{dt.strftime("%Y%m%dT%H%M%SZ")}',
                  f'DTEND:{(dt+timedelta(minutes=1)).strftime("%Y%m%dT%H%M%SZ")}']
    else:
        items += [f'DTSTART;VALUE=DATE:{event_day.strftime("%Y%m%d")}',
                  f'DTEND;VALUE=DATE:{(event_day+timedelta(days=1)).strftime("%Y%m%d")}']
    items += [f'SUMMARY:{escape_text(summary)}', f'DESCRIPTION:{escape_text(chr(10).join(lines))}',
              f'URL:{job["url"]}', 'TRANSP:TRANSPARENT',
              'STATUS:CANCELLED' if job.get('status')=='closed' else 'STATUS:CONFIRMED']
    if job.get('status') != 'closed':
        # All-day alarms at 09:00 KST the previous day; no midnight alert surprise.
        # UTC offset is fixed for Asia/Seoul, but use ZoneInfo explicitly.
        from zoneinfo import ZoneInfo
        for days in ([2,1] if deadline else [1]):
            alarm_day=event_day-timedelta(days=days)
            alarm=datetime.combine(alarm_day, datetime.min.time()).replace(hour=9,tzinfo=ZoneInfo('Asia/Seoul'))
            if alarm > now:
                items += ['BEGIN:VALARM','ACTION:DISPLAY',f'DESCRIPTION:{escape_text(summary)}',
                          'TRIGGER;VALUE=DATE-TIME:'+alarm.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                          'END:VALARM']
    return items+['END:VEVENT']


def make_ics(jobs: list[dict], now: datetime, review_after_days: int = 2, name='실시간 게임개발 채용공고') -> str:
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Korean GameDev Live v2//Vacancy Feed//KO',
           'CALSCALE:GREGORIAN','METHOD:PUBLISH',f'X-WR-CALNAME:{escape_text(name)}',
           'X-WR-TIMEZONE:Asia/Seoul','REFRESH-INTERVAL;VALUE=DURATION:PT1H','X-PUBLISHED-TTL:PT1H']
    seen=set()
    for job in sorted(jobs,key=lambda x:(x.get('deadline') or x['first_seen'][:10],x.get('company',''))):
        if job['url'] in seen: continue
        seen.add(job['url'])
        lines += event(job,now,review_after_days)
    lines += ['END:VCALENDAR']
    return '\r\n'.join(fold(line) for line in lines)+'\r\n'
