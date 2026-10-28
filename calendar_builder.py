"""EstLat fixtures intersected with the public Delfi TV broadcast schedule."""
import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from icalendar import Alarm, Calendar, Event

LEAGUE = 'https://www.estlatbl.com/en/game-center'
DELFI = 'https://portal-feeds.api.delfi.ee/portal-feeds-proxy/v1/stream-schedule?channel=tv.delfi.ee'
SCHEDULE = 'https://tv.delfi.ee/leht/ulekanded-kava/'
TZ = ZoneInfo('Europe/Tallinn')
UTC = timezone.utc
ESTONIAN = {'BC Pärnu', 'Bigbank/Kalev', 'Keila Basket', 'Keila KK',
            'TalTech/ALEXELA', 'Tartu Ülikool Maks & Moorits', 'Viimsi'}


def normalize(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD', s.casefold())
                if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s)


ALIASES = {normalize(k): normalize(v) for k, v in {
    'Läti Ülikool': 'Latvijas Universitāte', 'Riia Zelli': 'Rīgas Zeļļi',
    'Riia VEF': 'VEF Rīga',
}.items()}


def team(s):
    n = normalize(s)
    return ALIASES.get(n, n)


def parse_league(html):
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select('tr:has(.dateAndTime)')
    if not rows:
        raise ValueError('League HTML has no fixture rows; refusing to replace calendar')
    games = {}
    for row in rows:
        home = row.select_one('.homeTeamNameDesktop').get_text(strip=True)
        away = row.select_one('.visitorTeamNameDesktop').get_text(strip=True)
        date = row.select_one('.dateAndTime').get_text(strip=True)
        match = re.search(r'(\d{2}\.\d{2}\.\d{4}),\s*(\d{2}:\d{2})', date)
        # A fixture with no confirmed time cannot be given a reliable alert.
        if not match:
            raise ValueError(f'Unrecognized fixture time: {date}')
        start = datetime.strptime(' '.join(match.groups()), '%d.%m.%Y %H:%M').replace(tzinfo=TZ)
        gid = re.search(r'gid=(\d+)', str(row)).group(1)
        arena = row.select_one('.arena').get_text(' ', strip=True)
        games[gid] = dict(gid=gid, home=home, away=away, start=start, arena=arena)
    return list(games.values())


def parse_streams(data):
    streams = data['attributes']['data']['streams']
    if not isinstance(streams, list):
        raise ValueError('Unexpected Delfi API schema')
    result = []
    for stream in streams:
        if stream.get('hidden') or stream.get('label') != 'Korvpall':
            continue
        if not stream.get('publishedChannels', {}).get('tv'):
            continue
        parts = re.split(r'\s+[-–—]\s+', stream['title'])
        if len(parts) != 2:
            raise ValueError(f'Unrecognized basketball title: {stream["title"]}')
        start = datetime.fromisoformat(stream['date']['start'].replace('Z', '+00:00'))
        if start.tzinfo is None:
            raise ValueError('Delfi returned a time without timezone')
        result.append(dict(teams={team(p) for p in parts}, start=start,
                           url=stream.get('url') or SCHEDULE))
    return result


def select_games(games, streams):
    selected = []
    for game in games:
        if not ({game['home'], game['away']} & ESTONIAN):
            continue
        matches = [s for s in streams if s['teams'] == {team(game['home']), team(game['away'])}
                   and s['start'].astimezone(TZ).date() == game['start'].date()]
        if len(matches) > 1:
            raise ValueError(f'Ambiguous broadcasts for {game["gid"]}')
        if matches:
            if abs((matches[0]['start'] - game['start']).total_seconds()) > 3600:
                raise ValueError(f'League/Delfi start time conflict for {game["gid"]}')
            selected.append({**game, 'url': matches[0]['url']})
    return selected


def build(games, previous, now):
    records = {}
    for game in games:
        record = {**game, 'start': game['start'].astimezone(UTC).isoformat(), 'status': 'CONFIRMED'}
        records[game['gid']] = record
    # Retain recent history and explicitly cancel broadcasts removed from the schedule.
    for gid, old in previous.items():
        if gid not in records:
            start = datetime.fromisoformat(old['start'])
            if start >= now - timedelta(days=30):
                records[gid] = {**old, 'status': 'CANCELLED' if start > now else old['status']}
    cal = Calendar()
    for key, value in {'prodid': '-//EstLat Delfi Calendar//ET', 'version': '2.0',
                       'calscale': 'GREGORIAN', 'x-wr-calname': 'EstLat · Delfi TV',
                       'x-wr-timezone': 'Europe/Tallinn', 'refresh-interval;value=duration': 'PT6H',
                       'x-published-ttl': 'PT6H'}.items():
        cal.add(key, value)
    for gid, r in sorted(records.items(), key=lambda item: item[1]['start']):
        old = previous.get(gid, {})
        fingerprint = hashlib.sha256(json.dumps({k: r[k] for k in
            ['home', 'away', 'start', 'arena', 'url', 'status']}, sort_keys=True).encode()).hexdigest()
        changed = old.get('fingerprint') != fingerprint
        r['sequence'] = old.get('sequence', -1) + int(changed)
        r['updated'] = now.isoformat() if changed else old['updated']
        r['fingerprint'] = fingerprint
        event = Event()
        event.add('uid', f'estlat-{gid}@estlat-delfi-calendar')
        event.add('dtstamp', datetime.fromisoformat(r['updated']))
        event.add('last-modified', datetime.fromisoformat(r['updated']))
        start = datetime.fromisoformat(r['start'])
        event.add('dtstart', start)
        event.add('dtend', start + timedelta(hours=2))
        event.add('sequence', r['sequence'])
        event.add('status', r['status'])
        event.add('summary', f'{r["home"]} – {r["away"]} · Delfi TV')
        event.add('location', r['arena'])
        event.add('url', r['url'])
        event.add('description', f'EstLat League. Ülekanne: Delfi TV.\n{r["url"]}\n'
                  f'Liiga: {LEAGUE}?gid={gid}\nLõppaeg on hinnanguline (2 tundi).')
        if r['status'] != 'CANCELLED':
            alarm = Alarm()
            alarm.add('action', 'DISPLAY')
            alarm.add('description', 'EstLat mäng algab 15 minuti pärast')
            alarm.add('trigger', -timedelta(minutes=15))
            event.add_component(alarm)
        cal.add_component(event)
    return cal.to_ical(), records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', type=Path)
    parser.add_argument('--output', type=Path, default=Path('docs'))
    args = parser.parse_args()
    if args.fixtures:
        html = (args.fixtures / 'league.html').read_text()
        data = json.loads((args.fixtures / 'delfi.json').read_text())
    else:
        def fetch(url):
            response = requests.get(url, timeout=45, headers={'User-Agent': 'EstLat-Delfi-Calendar/1.0'})
            response.raise_for_status()
            return response
        html = fetch(LEAGUE).text
        data = fetch(DELFI).json()
    games = parse_league(html)
    streams = parse_streams(data)
    selected = select_games(games, streams)
    now = datetime.now(UTC)
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / 'state.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    content, state = build(selected, previous, now)
    # Round-trip validation happens before publishing anything.
    parsed = Calendar.from_ical(content)
    assert len(parsed.walk('VEVENT')) == len(state)
    (args.output / 'calendar.ics.tmp').write_bytes(content)
    (args.output / 'calendar.ics.tmp').replace(args.output / 'calendar.ics')
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    report = dict(updated=now.isoformat(), fixtures=len(games), basketball_streams=len(streams),
                  matched=len(selected), events=len(state), source_league=LEAGUE, source_delfi=DELFI)
    (args.output / 'status.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
