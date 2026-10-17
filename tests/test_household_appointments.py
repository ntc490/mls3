#!/usr/bin/env python3
"""
Tests for appointments made with a whole household.

Members and households are built in memory, and files go to a throwaway
directory, so these run the same with or without real data.

Run with:
    ./venv/bin/python -m unittest discover tests -v
"""
import csv
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import (  # noqa: E402
    AppointmentDatabase, Household, HouseholdDatabase, Member, MemberDatabase,
    MessageTemplates
)
from utils.sms_handler import get_sms_info  # noqa: E402


def person(member_id, first, last='Smith', gender='M', household_id=10,
           role='head', birthday='1980-01-01', **kwargs):
    return Member(member_id=member_id, first_name=first, last_name=last,
                  gender=gender, phone=f'555-000{member_id}', birthday=birthday,
                  recommend_expiration='', household_id=household_id,
                  household_role=role, **kwargs)


class TempDirTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def members_db(self, *members):
        db = MemberDatabase(csv_path=self.tmp / 'members.csv')
        db.members = list(members)
        return db

    def households_db(self, *households):
        db = HouseholdDatabase(csv_path=self.tmp / 'households.csv')
        db.households = list(households)
        return db


class TestHeads(TempDirTestCase):

    def setUp(self):
        super().setUp()
        self.david = person(1, 'David')
        self.lisa = person(2, 'Lisa', gender='F')
        self.kid = person(3, 'Sam', role='dependent', birthday='2014-05-05')
        self.db = self.members_db(self.david, self.lisa, self.kid)

    def ids(self, people):
        return sorted(p.member_id for p in people)

    def test_heads_include_whoever_is_asked_about(self):
        self.assertEqual(self.ids(self.db.get_heads(10)), [1, 2])

    def test_parents_of_a_head_leave_that_head_out(self):
        self.assertEqual(self.ids(self.db.get_parents(1)), [2])

    def test_parents_of_a_child_are_both_heads(self):
        self.assertEqual(self.ids(self.db.get_parents(3)), [1, 2])

    def test_an_inactive_head_is_still_a_head(self):
        self.lisa.active = False
        self.assertEqual(self.ids(self.db.get_heads(10)), [1, 2])

    def test_a_head_who_left_the_ward_is_not(self):
        self.lisa.in_ward = False
        self.assertEqual(self.ids(self.db.get_heads(10)), [1])

    def test_no_household_has_no_heads(self):
        self.assertEqual(self.db.get_heads(None), [])

    def test_households_without_roles_fall_back_to_the_name(self):
        for m in (self.david, self.lisa, self.kid):
            m.household_role = ''
        households = self.households_db(
            Household(household_id=10, name='Smith, David & Lisa', address=''))
        self.assertEqual(self.ids(self.db.get_heads(10, households)), [1, 2])
        self.assertEqual(self.ids(self.db.get_parents(3, households)), [1, 2])


class TestHouseholdColumn(TempDirTestCase):

    def make(self, household):
        db = AppointmentDatabase(csv_path=self.tmp / 'appointments.csv')
        return db.create_appointment(
            member_id=1, appointment_type='Tithing', date=date(2026, 12, 6),
            time='10:00', duration_minutes=10, conductor='Bishop',
            timezone='America/Denver', household=household)

    def test_the_flag_survives_a_save_and_reload(self):
        self.make(household=True)
        self.make(household=False)
        reloaded = AppointmentDatabase(csv_path=self.tmp / 'appointments.csv')
        self.assertEqual([a.household for a in reloaded.appointments],
                         [True, False])

    def test_a_file_from_before_the_column_loads_as_not_household(self):
        path = self.tmp / 'appointments.csv'
        old_columns = [f for f in AppointmentDatabase.FIELDNAMES if f != 'household']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=old_columns)
            writer.writeheader()
            writer.writerow({
                'appointment_id': 1, 'member_id': 1, 'appointment_type': 'Family',
                'datetime_utc': '2026-12-06T17:00:00Z', 'duration_minutes': 30,
                'conductor': 'Bishop', 'state': 'Draft',
                'created_date': '2026-10-17', 'last_updated': '2026-10-17',
            })
        db = AppointmentDatabase(csv_path=path)
        self.assertFalse(db.appointments[0].household)

    def test_update_can_turn_it_on_and_off(self):
        appointment = self.make(household=False)
        db = AppointmentDatabase(csv_path=self.tmp / 'appointments.csv')
        db.update_appointment(appointment.appointment_id, household=True)
        self.assertTrue(db.get_by_id(appointment.appointment_id).household)
        db.update_appointment(appointment.appointment_id, notes='x')
        self.assertTrue(db.get_by_id(appointment.appointment_id).household)
        db.update_appointment(appointment.appointment_id, household=False)
        self.assertFalse(db.get_by_id(appointment.appointment_id).household)


class TestHouseholdMessages(TempDirTestCase):

    def setUp(self):
        super().setUp()
        self.david = person(1, 'David')
        self.lisa = person(2, 'Lisa', gender='F')
        self.kid = person(3, 'Sam', role='dependent', birthday='2014-05-05')
        self.members = self.members_db(self.david, self.lisa, self.kid)
        self.templates = MessageTemplates(ROOT / 'data' / 'message_templates.yaml')
        appointments = AppointmentDatabase(csv_path=self.tmp / 'appointments.csv')
        self.appointment = appointments.create_appointment(
            member_id=1, appointment_type='Tithing', date=date(2026, 12, 6),
            time='10:00', duration_minutes=10, conductor='Bishop',
            timezone='America/Denver', household=True)

    def info(self, who=None):
        return get_sms_info('appointments', 'Tithing_invite', who or self.david,
                            self.templates, self.members, None, self.appointment,
                            conductor='the Bishop')

    def test_both_heads_get_one_text_that_names_them_both(self):
        info = self.info()
        self.assertTrue(info['success'])
        self.assertEqual(info['phone'], '555-0001;555-0002')
        self.assertTrue(info['message'].startswith('Hi David & Lisa, could you meet'),
                        info['message'])

    def test_formal_when_either_head_has_the_flag(self):
        self.lisa.flag = 'blue'
        self.assertTrue(self.info()['message'].startswith('Hi Brother and Sister Smith,'))

    def test_a_head_without_a_phone_is_skipped(self):
        self.lisa.phone = ''
        info = self.info()
        self.assertEqual(info['phone'], '555-0001')
        self.assertIn('David & Lisa', info['message'])

    def test_a_shared_phone_is_texted_once(self):
        self.lisa.phone = self.david.phone
        self.assertEqual(self.info()['phone'], '555-0001')

    def test_no_phones_at_all_is_an_error(self):
        self.david.phone = self.lisa.phone = ''
        info = self.info()
        self.assertFalse(info['success'])
        self.assertIn('Smith household', info['error'])

    def test_picked_through_a_child_it_still_goes_to_the_heads(self):
        info = self.info(self.kid)
        self.assertEqual(info['phone'], '555-0001;555-0002')
        self.assertIn('David & Lisa', info['message'])

    def test_not_a_household_appointment_goes_to_the_member_alone(self):
        self.appointment.household = False
        info = self.info()
        self.assertEqual(info['phone'], '555-0001')
        self.assertTrue(info['message'].startswith('Hi David, could you meet'))

    def test_without_a_household_it_falls_back_to_the_member(self):
        self.david.household_id = None
        info = self.info()
        self.assertEqual(info['phone'], '555-0001')
        self.assertTrue(info['message'].startswith('Hi David, could you meet'))


class TestHistoryAndNames(TempDirTestCase):

    def setUp(self):
        super().setUp()
        self.david = person(1, 'David')
        self.lisa = person(2, 'Lisa', gender='F')
        self.kid = person(3, 'Sam', role='dependent', birthday='2014-05-05')
        self.other = person(4, 'Ann', last='Jones', gender='F', household_id=20)
        self.members = self.members_db(self.david, self.lisa, self.kid, self.other)
        self.appointments = AppointmentDatabase(csv_path=self.tmp / 'appointments.csv')

    def make(self, member_id, household):
        return self.appointments.create_appointment(
            member_id=member_id, appointment_type='Family', date=date(2026, 12, 6),
            time='10:00', duration_minutes=30, conductor='Counselor',
            timezone='America/Denver', household=household)

    def ids_for(self, member_id):
        return [a.appointment_id for a in self.appointments.get_appointments_for_member(
            member_id, self.members)]

    def test_a_household_appointment_is_in_both_heads_history(self):
        appointment = self.make(1, household=True)
        self.assertEqual(self.ids_for(1), [appointment.appointment_id])
        self.assertEqual(self.ids_for(2), [appointment.appointment_id])
        self.assertEqual(self.ids_for(4), [])

    def test_picked_through_a_child_it_is_in_the_childs_and_the_heads_history(self):
        appointment = self.make(3, household=True)
        for member_id in (1, 2, 3):
            self.assertEqual(self.ids_for(member_id), [appointment.appointment_id])

    def test_an_individual_appointment_stays_with_its_member(self):
        self.make(1, household=False)
        self.assertEqual(self.ids_for(2), [])

    def test_without_members_db_only_the_picked_member_matches(self):
        self.make(1, household=True)
        self.assertEqual(len(self.appointments.get_appointments_for_member(2)), 0)

    def test_display_names_shorten_first_names(self):
        from utils.template_expander import display_names
        self.david.first_name = 'David Allen'
        self.assertEqual(display_names([self.david]), 'David Smith')
        self.assertEqual(display_names([self.lisa, self.david]), 'David and Lisa Smith')

    def test_the_calendar_event_is_titled_with_the_household(self):
        from unittest import mock
        import config
        from utils.google_calendar import CalendarSync

        service = mock.MagicMock()
        service.events().insert().execute.return_value = {'id': 'evt'}
        appointment = self.make(1, household=True)
        with mock.patch.object(config, 'COUNSELOR_CALENDAR_ID', 'cal'):
            CalendarSync(service).sync_appointment(
                appointment, self.david, name='David and Lisa Smith')
        body = service.events().insert.call_args.kwargs['body']
        self.assertEqual(body['summary'], '? David and Lisa Smith - Family')


if __name__ == '__main__':
    unittest.main()
