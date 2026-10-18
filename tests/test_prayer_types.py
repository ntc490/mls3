#!/usr/bin/env python3
"""
Tests that every prayer assignment is an opening or a closing prayer, and that
two on the same Sunday are opposites.

Files go to a throwaway directory, so these run the same with or without real
data.

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

from models import Member, MessageTemplates, PrayerAssignmentDatabase  # noqa: E402

SUNDAY = date(2026, 10, 25)
NEXT_SUNDAY = date(2026, 11, 1)


class PrayerTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / 'prayer_assignments.csv'

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def db(self):
        return PrayerAssignmentDatabase(csv_path=self.path)


class TestCreating(PrayerTestCase):

    def test_the_first_slot_is_opening_and_the_second_closing(self):
        db = self.db()
        self.assertEqual(db.create_assignment(1, SUNDAY).prayer_type, 'Opening')
        self.assertEqual(db.create_assignment(2, SUNDAY).prayer_type, 'Closing')

    def test_a_free_type_that_is_asked_for_is_used(self):
        db = self.db()
        self.assertEqual(db.create_assignment(1, SUNDAY, 'Closing').prayer_type, 'Closing')
        self.assertEqual(db.create_assignment(2, SUNDAY).prayer_type, 'Opening')

    def test_a_type_already_taken_that_sunday_is_not(self):
        db = self.db()
        db.create_assignment(1, SUNDAY, 'Opening')
        self.assertEqual(db.create_assignment(2, SUNDAY, 'Opening').prayer_type, 'Closing')

    def test_undecided_is_no_longer_a_type(self):
        db = self.db()
        self.assertEqual(db.create_assignment(1, SUNDAY, 'Undecided').prayer_type, 'Opening')

    def test_other_sundays_do_not_count(self):
        db = self.db()
        db.create_assignment(1, SUNDAY, 'Opening')
        self.assertEqual(db.create_assignment(2, NEXT_SUNDAY).prayer_type, 'Opening')


class TestMoving(PrayerTestCase):

    def test_moving_onto_a_sunday_with_the_same_prayer_takes_the_other(self):
        db = self.db()
        db.create_assignment(1, SUNDAY, 'Opening')
        moving = db.create_assignment(2, NEXT_SUNDAY, 'Opening')
        db.update_assignment(moving.assignment_id, date=SUNDAY)
        self.assertEqual(db.get_by_id(moving.assignment_id).prayer_type, 'Closing')

    def test_moving_onto_a_sunday_with_both_prayers_is_refused(self):
        db = self.db()
        db.create_assignment(1, SUNDAY)
        db.create_assignment(2, SUNDAY)
        moving = db.create_assignment(3, NEXT_SUNDAY, 'Opening')
        with self.assertRaises(ValueError):
            db.update_assignment(moving.assignment_id, date=SUNDAY)
        unchanged = self.db().get_by_id(moving.assignment_id)
        self.assertEqual((unchanged.date, unchanged.prayer_type),
                         (NEXT_SUNDAY.strftime('%Y-%m-%d'), 'Opening'))

    def test_moving_onto_an_empty_sunday_keeps_the_prayer(self):
        db = self.db()
        moving = db.create_assignment(2, SUNDAY, 'Closing')
        db.update_assignment(moving.assignment_id, date=NEXT_SUNDAY)
        self.assertEqual(db.get_by_id(moving.assignment_id).prayer_type, 'Closing')


class TestOlderFiles(PrayerTestCase):

    def write(self, rows):
        with open(self.path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=PrayerAssignmentDatabase.FIELDNAMES)
            writer.writeheader()
            for assignment_id, prayer_type, state in rows:
                writer.writerow({
                    'assignment_id': assignment_id, 'member_id': assignment_id,
                    'date': '2026-10-25', 'prayer_type': prayer_type, 'state': state,
                    'created_date': '2026-10-01', 'last_updated': '2026-10-01',
                })

    def types(self):
        return [a.prayer_type for a in self.db().assignments]

    def test_undecided_takes_the_opposite_of_its_sunday(self):
        self.write([(1, 'Closing', 'Invited'), (2, 'Undecided', 'Draft')])
        self.assertEqual(self.types(), ['Closing', 'Opening'])

    def test_two_undecided_become_opening_then_closing(self):
        self.write([(1, 'Undecided', 'Invited'), (2, 'Undecided', 'Draft')])
        self.assertEqual(self.types(), ['Opening', 'Closing'])

    def test_completed_assignments_are_left_as_they_were(self):
        self.write([(1, 'Undecided', 'Completed')])
        self.assertEqual(self.types(), ['Undecided'])

    def test_settling_does_not_write_the_file(self):
        self.write([(1, 'Undecided', 'Draft')])
        before = self.path.read_text()
        self.db()
        self.assertEqual(self.path.read_text(), before)


class TestMessages(PrayerTestCase):

    def test_the_invite_names_the_prayer(self):
        templates = MessageTemplates(ROOT / 'data' / 'message_templates.yaml')
        member = Member(member_id=1, first_name='David', last_name='Smith', gender='M',
                        phone='', birthday='1980-01-01', recommend_expiration='')
        db = self.db()
        opening = db.create_assignment(1, SUNDAY)
        closing = db.create_assignment(2, SUNDAY)
        for assignment, word in ((opening, 'opening'), (closing, 'closing')):
            for name in ('invite', 'invite_parent', 'reminder', 'reminder_parent'):
                text = templates.expand_smart('prayer', name, member, assignment,
                                              parent_greeting='Brother Smith',
                                              child_name='Sam')
                self.assertIn(f'the {word} prayer', text, name)
                self.assertNotIn('opening or closing', text, name)


if __name__ == '__main__':
    unittest.main()
