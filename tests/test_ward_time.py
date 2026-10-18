#!/usr/bin/env python3
"""
Tests that times are always the ward's (config.HOME_TIMEZONE), wherever the
phone running MLS3 happens to be.

Files go to a throwaway directory, so these run the same with or without real
data.

Run with:
    ./venv/bin/python -m unittest discover tests -v
"""
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from models import AppointmentDatabase  # noqa: E402
from utils.template_expander import SmartTemplateExpander  # noqa: E402


def clock_at(utc: datetime):
    """Patch config's datetime so now() is this UTC instant"""
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz) if tz else utc.replace(tzinfo=None)
    return mock.patch.object(config, 'datetime', FixedDatetime)


class TestWardClock(unittest.TestCase):

    def test_today_is_the_wards_even_when_utc_is_already_tomorrow(self):
        # 9:30pm Saturday in Denver is 3:30am Sunday UTC
        with clock_at(datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc)):
            self.assertEqual(config.ward_today(), date(2026, 10, 17))
            self.assertEqual(config.ward_now().hour, 21)


class TestAppointmentTimes(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = AppointmentDatabase(csv_path=self.tmp / 'appointments.csv')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, time_str):
        return self.db.create_appointment(
            member_id=1, appointment_type='Tithing', date=date(2026, 12, 6),
            time=time_str, duration_minutes=10, conductor='Bishop')

    def test_a_typed_time_is_read_as_ward_time(self):
        appointment = self.make('10:00')
        self.assertEqual(appointment.datetime_utc, '2026-12-06T17:00:00Z')  # MST
        self.assertEqual(appointment.time_local(config.HOME_TIMEZONE), '10:00 AM')

    def test_changing_only_the_time_of_an_evening_appointment_keeps_its_day(self):
        # 7pm Mountain is already the next day in UTC
        appointment = self.make('19:00')
        self.db.update_appointment(appointment.appointment_id, time='20:00')
        self.assertEqual(appointment.date_local(config.HOME_TIMEZONE), '2026-12-06')
        self.assertEqual(appointment.time_local(config.HOME_TIMEZONE), '08:00 PM')

    def test_smart_dates_count_from_the_wards_today(self):
        appointment = self.make('19:00')
        expander = SmartTemplateExpander(None)
        with mock.patch.object(config, 'ward_today', return_value=date(2026, 12, 5)):
            self.assertEqual(expander._calculate_smart_date(appointment), 'tomorrow')
        with mock.patch.object(config, 'ward_today', return_value=date(2026, 12, 6)):
            self.assertEqual(expander._calculate_smart_date(appointment), 'today')


if __name__ == '__main__':
    unittest.main()
