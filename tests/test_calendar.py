import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from icalendar import Calendar
from calendar_builder import build, parse_league, parse_streams, select_games, TZ

FIXTURES = Path(__file__).parent / 'fixtures'

class CalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = parse_league((FIXTURES / 'league.html').read_text())
        cls.streams = parse_streams(json.loads((FIXTURES / 'delfi.json').read_text()))
        cls.selected = select_games(cls.games, cls.streams)
        cls.now = datetime(2026, 10, 28, 21, tzinfo=timezone.utc)

    def test_real_sources_and_exclusion(self):
        self.assertEqual(len(self.games), 161)
        self.assertEqual(len(self.selected), 7)
        titles = [(g['home'], g['away']) for g in self.selected]
        self.assertIn(('Bigbank/Kalev', 'Rīgas Zeļļi'), titles)
        self.assertIn(('TalTech/ALEXELA', 'Latvijas Universitāte'), titles)
        self.assertFalse(any('Iraklis' in str(g) or 'Manchester' in str(g) for g in self.selected))

    def test_ical_timezone_alarm_and_utf8(self):
        raw, state = build(self.selected, {}, self.now)
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
        self.assertTrue(all(len(line) <= 75 for line in raw.split(b'\r\n')))
        events = Calendar.from_ical(raw).walk('VEVENT')
        self.assertEqual(len(events), 7)
        for e in events:
            self.assertEqual(e.walk('VALARM')[0].decoded('TRIGGER'), -timedelta(minutes=15))
            self.assertEqual(e.decoded('DTEND') - e.decoded('DTSTART'), timedelta(hours=2))
        game = next(e for e in events if 'Keila KK' in str(e['SUMMARY']))
        self.assertEqual(game.decoded('DTSTART').astimezone(TZ).strftime('%Y-%m-%d %H:%M'), '2026-10-31 18:00')
        self.assertEqual(datetime(2026, 7, 1, 18, tzinfo=TZ).utcoffset(), timedelta(hours=3))
        self.assertEqual(datetime(2026, 10, 31, 18, tzinfo=TZ).utcoffset(), timedelta(hours=2))

    def test_stable_uid_updates_and_cancellation(self):
        raw, state = build(self.selected, {}, self.now)
        again, _ = build(self.selected, state, self.now + timedelta(hours=6))
        self.assertEqual(raw, again)
        games = copy.deepcopy(self.selected)
        games[-1]['start'] += timedelta(minutes=30)
        changed, new = build(games, state, self.now + timedelta(hours=6))
        gid = games[-1]['gid']
        self.assertEqual(new[gid]['sequence'], state[gid]['sequence'] + 1)
        cancelled, new = build([], state, self.now)
        self.assertTrue(any(r['status'] == 'CANCELLED' for r in new.values()))
        self.assertEqual(set(state), set(new))

    def test_source_failures(self):
        with self.assertRaises(ValueError):
            parse_league('<html>maintenance</html>')
        with self.assertRaises(KeyError):
            parse_streams({'error': 'unavailable'})
        streams = copy.deepcopy(self.streams)
        for stream in streams:
            stream['start'] += timedelta(hours=2)
        with self.assertRaises(ValueError):
            select_games(self.games, streams)

if __name__ == '__main__':
    unittest.main()
