import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from services.sci_service import build_availability_windows, generate_growth_hypotheses


class SciHelperTests(unittest.TestCase):
    def test_build_availability_windows_creates_gaps_between_events(self):
        now = datetime(2026, 6, 7, 9, 0, tzinfo=UTC)
        events = [
            {
                "id": "evt-1",
                "start": "2026-06-07T10:00:00+00:00",
                "end": "2026-06-07T11:00:00+00:00",
            },
            {
                "id": "evt-2",
                "start": "2026-06-07T13:00:00+00:00",
                "end": "2026-06-07T14:00:00+00:00",
            },
        ]

        windows = build_availability_windows(events, now=now)

        self.assertGreaterEqual(len(windows), 2)
        self.assertEqual(windows[0].start_at, now)
        self.assertEqual(windows[0].end_at, datetime(2026, 6, 7, 10, 0, tzinfo=UTC))
        self.assertEqual(windows[1].start_at, datetime(2026, 6, 7, 11, 0, tzinfo=UTC))
        self.assertEqual(windows[1].end_at, datetime(2026, 6, 7, 13, 0, tzinfo=UTC))

    def test_build_availability_windows_filters_short_slots(self):
        now = datetime(2026, 6, 7, 9, 0, tzinfo=UTC)
        events = [
            {
                "id": "evt-1",
                "start": "2026-06-07T09:20:00+00:00",
                "end": "2026-06-07T09:40:00+00:00",
            }
        ]

        windows = build_availability_windows(events, now=now)

        self.assertTrue(all((window.end_at - window.start_at) >= timedelta(minutes=45) for window in windows))

    def test_generate_growth_hypotheses_returns_actionable_entries(self):
        hypotheses = generate_growth_hypotheses(
            "Increase company leverage and booked meetings",
            ["Founder has too many reactive follow-ups"],
            ["founder scheduling", "offer clarity"],
        )

        self.assertEqual(len(hypotheses), 3)
        self.assertTrue(all(hypothesis.title for hypothesis in hypotheses))
        self.assertTrue(all(hypothesis.next_action for hypothesis in hypotheses))


if __name__ == "__main__":
    unittest.main()
