#!/usr/bin/env python3
"""
Tests for the PDF import.

Run with:
    ./venv/bin/python -m unittest discover tests -v

The fixtures are the real church reports in the repository root. They hold real
member data, so they are gitignored and not shipped; tests that need them skip
when they are absent.

    import-sample.pdf    member list, WITH the Address column (24 pages)
    import-sample2.pdf   a second print of the same report, to prove stability
    import-sample3.pdf   member list, WITHOUT Address - the default columns
    household-sample.pdf household report (13 pages)
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MEMBER_PDF = ROOT / 'import-sample.pdf'
MEMBER_PDF_2 = ROOT / 'import-sample2.pdf'
MEMBER_PDF_NO_ADDRESS = ROOT / 'import-sample3.pdf'
HOUSEHOLD_PDF = ROOT / 'household-sample.pdf'

# What the sample ward actually contains, checked by hand against the reports.
EXPECTED_PEOPLE = 342
EXPECTED_HOUSEHOLDS = 145
EXPECTED_HEADS = 237
EXPECTED_DEPENDENTS = 105

needs_member_pdf = unittest.skipUnless(
    MEMBER_PDF.exists(), 'import-sample.pdf not present')
needs_no_address_pdf = unittest.skipUnless(
    MEMBER_PDF_NO_ADDRESS.exists(), 'import-sample3.pdf not present')
needs_household_pdf = unittest.skipUnless(
    HOUSEHOLD_PDF.exists(), 'household-sample.pdf not present')


try:
    from utils.pdf_tables import PdfToolMissing, join_cell, require_pdftotext, Word
    require_pdftotext()
    HAVE_PDFTOTEXT = True
except (PdfToolMissing, ImportError):
    HAVE_PDFTOTEXT = False

needs_pdftotext = unittest.skipUnless(
    HAVE_PDFTOTEXT, 'pdftotext not installed (pkg install poppler)')


@needs_pdftotext
class TestCellJoining(unittest.TestCase):
    """How a cell's wrapped lines are put back together."""

    def test_email_wrapping_loses_no_characters(self):
        # Emails wrap mid-token, so the pieces must join with nothing between.
        words = [Word(10.0, 20.0, 430.0, 'Barbara.anderson111@comcast.ne'),
                 Word(22.0, 32.0, 430.0, 't')]
        self.assertEqual(join_cell(words, 'email'),
                         'Barbara.anderson111@comcast.net')

    def test_hyphenated_name_rejoins_without_a_space(self):
        # "Joe-Courage" breaks at its own hyphen across two lines.
        words = [Word(10.0, 20.0, 41.0, 'Velasco,'), Word(10.0, 20.0, 80.0, 'Camden'),
                 Word(10.0, 20.0, 120.0, 'Joe-'), Word(22.0, 32.0, 41.0, 'Courage')]
        self.assertEqual(join_cell(words, 'name'), 'Velasco, Camden Joe-Courage')

    def test_ordinary_wrapped_name_keeps_its_space(self):
        words = [Word(10.0, 20.0, 41.0, 'Andreason,'), Word(10.0, 20.0, 90.0, 'Adelle'),
                 Word(22.0, 32.0, 41.0, 'Zayla')]
        self.assertEqual(join_cell(words, 'name'), 'Andreason, Adelle Zayla')

    def test_words_are_ordered_by_position_not_arrival(self):
        words = [Word(10.0, 20.0, 90.0, 'Barbara'), Word(10.0, 20.0, 41.0, 'Anderson,')]
        self.assertEqual(join_cell(words, 'name'), 'Anderson, Barbara')


@needs_pdftotext
@needs_member_pdf
class TestMemberList(unittest.TestCase):
    """The member-list report, in its with-Address form."""

    @classmethod
    def setUpClass(cls):
        from utils.pdf_member_list import parse_member_list
        cls.report = parse_member_list(MEMBER_PDF)

    def test_record_count_matches_the_printed_total(self):
        self.assertEqual(len(self.report.members), EXPECTED_PEOPLE)
        self.assertEqual(self.report.declared_count, EXPECTED_PEOPLE)

    def test_address_column_is_detected_when_present(self):
        self.assertIn('address', self.report.columns)
        for required in ('name', 'gender', 'birth_date', 'phone'):
            self.assertIn(required, self.report.columns)

    def test_every_person_has_the_fields_we_import(self):
        for member in self.report.members:
            self.assertTrue(member.name, 'a record came through with no name')
            self.assertIn(member.gender, ('M', 'F'), member.name)
            self.assertTrue(member.birth_date, member.name)

    def test_printed_age_agrees_with_the_birth_date(self):
        # Disagreement means a row was misread, so it must not appear here.
        # Checked as of the print date: the Age column was right when the
        # report was printed, not necessarily today.
        as_of = self.report.printed_on
        self.assertIsNotNone(as_of, 'the print date should be readable')
        for member in self.report.members:
            if member.printed_age is None:
                continue
            self.assertEqual(member.computed_age(as_of), member.printed_age,
                             member.name)

    def test_parse_is_clean(self):
        self.assertEqual(self.report.warnings, [])

    def test_print_date_is_read(self):
        self.assertRegex(self.report.print_date, r'^\d{1,2} \w{3} \d{4}$')

    def test_page_straddling_rows_are_rejoined_in_the_right_direction(self):
        # A row split across a page break must merge toward the page it
        # continues onto. Merging the wrong way fuses two people into one
        # record with doubled fields and raises no error, so it is checked by
        # name rather than only by count.
        by_name = {m.name: m for m in self.report.members}

        julianna = by_name.get('Andreason, Julianna Rose')
        matti = by_name.get('Andreason, Matti Lanae')
        self.assertIsNotNone(julianna, 'a straddling record went missing')
        self.assertIsNotNone(matti, 'a straddling record went missing')

        self.assertEqual(julianna.birth_date, '2011-09-19')
        self.assertEqual(julianna.phone, '801-514-2646')
        self.assertEqual(matti.birth_date, '2007-08-09')
        self.assertEqual(matti.phone, '385-612-3363')

        # Fused records show up as doubled values in a single field.
        for member in self.report.members:
            self.assertLessEqual(len(member.raw_birth_date.split()), 3, member.name)

    def test_hyphenated_name_survives_the_line_break(self):
        names = {m.name for m in self.report.members}
        self.assertIn('Velasco, Camden Joe-Courage', names)

    def test_no_duplicate_people(self):
        keys = [m.key for m in self.report.members]
        self.assertEqual(len(keys), len(set(keys)))


@needs_pdftotext
@needs_member_pdf
class TestPhoneNormalization(unittest.TestCase):
    """
    Phone numbers are put into one form at parse time.

    Parentheses and spaces have to be percent-encoded in an SMS URI, and
    without this every number in the ward changes format on the first import,
    burying the few that genuinely changed.
    """

    @classmethod
    def setUpClass(cls):
        from utils.pdf_member_list import parse_member_list
        cls.report = parse_member_list(MEMBER_PDF)

    def test_no_phone_contains_a_bracket_or_a_space(self):
        for member in self.report.members:
            self.assertNotIn('(', member.phone, member.name)
            self.assertNotIn(')', member.phone, member.name)
            self.assertNotIn(' ', member.phone, member.name)

    def test_numbers_keep_their_digits(self):
        phones = [m.phone for m in self.report.members if m.phone]
        self.assertTrue(phones)
        for phone in phones:
            self.assertRegex(phone, r'^[\d-]+$')

    def test_the_form_matches_the_existing_convention(self):
        known = {m.name: m.phone for m in self.report.members}
        self.assertEqual(known.get('Anderson, Barbara'), '801-419-2648')

    def test_an_international_number_is_not_forced_into_a_us_shape(self):
        # One number in the sample ward is "027 618 2094".
        from utils.pdf_tables import normalize_phone
        self.assertEqual(normalize_phone('027 618 2094'), '027-618-2094')

    def test_an_already_normalized_number_is_unchanged(self):
        from utils.pdf_tables import normalize_phone
        self.assertEqual(normalize_phone('801-555-0101'), '801-555-0101')
        self.assertEqual(normalize_phone(''), '')


@needs_pdftotext
@needs_no_address_pdf
class TestMemberListWithoutAddress(unittest.TestCase):
    """The same report printed with the default columns, which omit Address."""

    @classmethod
    def setUpClass(cls):
        from utils.pdf_member_list import parse_member_list
        cls.report = parse_member_list(MEMBER_PDF_NO_ADDRESS)

    def test_columns_are_read_from_this_report_not_assumed(self):
        self.assertNotIn('address', self.report.columns)
        self.assertEqual(self.report.columns[:4],
                         ['name', 'gender', 'age', 'birth_date'])

    def test_record_count_still_matches(self):
        self.assertEqual(len(self.report.members), EXPECTED_PEOPLE)
        self.assertEqual(self.report.declared_count, EXPECTED_PEOPLE)

    @needs_member_pdf
    def test_produces_the_same_people_as_the_with_address_report(self):
        # Dropping a column must not change a single imported value.
        from utils.pdf_member_list import parse_member_list
        other = parse_member_list(MEMBER_PDF)

        mine = {m.key: (m.name, m.gender, m.birth_date, m.phone)
                for m in self.report.members}
        theirs = {m.key: (m.name, m.gender, m.birth_date, m.phone)
                  for m in other.members}
        self.assertEqual(mine, theirs)


@needs_pdftotext
@unittest.skipUnless(MEMBER_PDF.exists() and MEMBER_PDF_2.exists(),
                     'both member-list prints needed')
class TestRepeatedPrints(unittest.TestCase):
    def test_two_prints_of_one_report_parse_identically(self):
        from utils.pdf_member_list import parse_member_list
        first = parse_member_list(MEMBER_PDF)
        second = parse_member_list(MEMBER_PDF_2)
        self.assertEqual(
            [(m.name, m.gender, m.birth_date, m.phone) for m in first.members],
            [(m.name, m.gender, m.birth_date, m.phone) for m in second.members],
        )


@needs_pdftotext
@needs_household_pdf
class TestHouseholdList(unittest.TestCase):
    """The household report, which supplies structure and head/dependent roles."""

    @classmethod
    def setUpClass(cls):
        from utils.pdf_household_list import parse_household_list
        cls.report = parse_household_list(HOUSEHOLD_PDF)

    def test_household_and_people_counts(self):
        self.assertEqual(len(self.report.households), EXPECTED_HOUSEHOLDS)
        self.assertEqual(len(self.report.all_members), EXPECTED_PEOPLE)

    def test_roles_come_from_the_indent(self):
        from utils.pdf_household_list import HEAD
        people = self.report.all_members
        heads = [m for m in people if m.role == HEAD]
        self.assertEqual(len(heads), EXPECTED_HEADS)
        self.assertEqual(len(people) - len(heads), EXPECTED_DEPENDENTS)

    def test_every_household_has_one_or_two_heads(self):
        for household in self.report.households:
            self.assertIn(len(household.heads), (1, 2), household.name)

    def test_first_person_of_a_household_is_not_lost_to_the_previous_one(self):
        # The household-name line sits a few points above its first member, so
        # rows are clustered with a tolerance. Without it every household loses
        # its first person to the household above.
        first = self.report.households[0]
        self.assertEqual(first.name, 'Anderson, Bryan & Barbara')
        self.assertEqual([m.raw_name for m in first.members], ['Bryan', 'Barbara'])

    def test_two_word_name_at_head_level_is_one_person(self):
        # "Samantha Charlene" spans both indent levels; taking the indent per
        # word instead of per line would invent an extra dependent.
        household = self._by_name('Bateman, Brad Ray & Samantha Charlene')
        self.assertEqual(len(household.members), 2)
        self.assertEqual([m.role for m in household.members], ['head', 'head'])
        self.assertEqual(household.members[1].raw_name, 'Samantha Charlene')

    def test_dependent_with_a_different_surname_keeps_it(self):
        household = self._by_name('Butterfield, Chad & Debbie')
        landon = next(m for m in household.members if 'Landon' in m.raw_name)
        self.assertEqual(landon.full_name, 'Savage, Landon Scott')
        self.assertEqual(landon.role, 'dependent')

    def test_head_with_a_different_surname_keeps_it(self):
        household = self._by_name('Campbell, Brayden & Hunter')
        hunter = next(m for m in household.members if 'Hunter' in m.raw_name)
        self.assertEqual(hunter.full_name, 'Glad, Hunter')
        self.assertEqual(hunter.role, 'head')

    def test_bare_first_name_inherits_the_household_surname(self):
        household = self._by_name('Anderson, Jack & Rachel')
        easton = next(m for m in household.members if m.raw_name == 'Easton')
        self.assertEqual(easton.full_name, 'Anderson, Easton')

    def test_household_without_an_address_is_kept(self):
        household = self._by_name('Barton, Linda')
        self.assertEqual(household.address, '')
        self.assertEqual(len(household.members), 2)

    def test_nobody_is_in_two_households(self):
        keys = [m.key for m in self.report.all_members]
        self.assertEqual(len(keys), len(set(keys)))

    def test_parse_is_clean(self):
        self.assertEqual(self.report.warnings, [])

    def _by_name(self, name):
        for household in self.report.households:
            if household.name == name:
                return household
        self.fail(f'household {name!r} was not found')


@needs_pdftotext
@needs_household_pdf
@needs_no_address_pdf
class TestReportsAgree(unittest.TestCase):
    """The two reports must describe the same ward."""

    @classmethod
    def setUpClass(cls):
        from utils.pdf_household_list import parse_household_list
        from utils.pdf_member_list import parse_member_list
        cls.members = parse_member_list(MEMBER_PDF_NO_ADDRESS)
        cls.households = parse_household_list(HOUSEHOLD_PDF)

    def test_every_person_appears_in_both_reports(self):
        member_keys = {m.key for m in self.members.members}
        household_keys = {m.key for m in self.households.all_members}
        self.assertEqual(member_keys - household_keys, set())
        self.assertEqual(household_keys - member_keys, set())

    def test_genders_and_ages_agree(self):
        as_of = self.members.printed_on
        by_key = {m.key: m for m in self.members.members}
        for person in self.households.all_members:
            record = by_key[person.key]
            self.assertEqual(person.gender, record.gender, record.name)
            if person.printed_age is not None:
                self.assertEqual(person.printed_age, record.computed_age(as_of),
                                 record.name)

    def test_no_head_of_household_is_a_minor(self):
        from utils.pdf_household_list import HEAD
        as_of = self.members.printed_on
        by_key = {m.key: m for m in self.members.members}
        for person in self.households.all_members:
            if person.role == HEAD:
                self.assertGreaterEqual(by_key[person.key].computed_age(as_of), 18,
                                        person.full_name)

    def test_many_dependents_are_adults(self):
        # The whole reason roles are read rather than inferred: an age test
        # would call every one of these people a parent.
        from utils.pdf_household_list import HEAD
        by_key = {m.key: m for m in self.members.members}
        as_of = self.members.printed_on
        adult_dependents = [
            p for p in self.households.all_members
            if p.role != HEAD and by_key[p.key].computed_age(as_of) >= 18
        ]
        self.assertGreater(len(adult_dependents), 20)


@needs_pdftotext
@needs_member_pdf
class TestRejectsBadInput(unittest.TestCase):

    def test_a_short_read_is_refused(self):
        # If the parse ever drops people, the count printed on the report will
        # not match and the import must abort rather than quietly lose members.
        from utils.pdf_member_list import parse_member_list, _validate

        report = parse_member_list(MEMBER_PDF)
        report.members.pop()

        with self.assertRaises(ValueError) as caught:
            _validate(report, MEMBER_PDF)
        message = str(caught.exception)
        self.assertIn('341', message)
        self.assertIn('342', message)

    def test_a_pdf_that_is_not_a_church_report_is_refused(self):
        # Anything without the expected table shape should say so plainly
        # rather than fail deep inside the parser.
        import subprocess
        from utils.pdf_member_list import parse_member_list

        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / 'other.pdf'
            built = subprocess.run(
                ['qpdf', '--pages', str(MEMBER_PDF), '1-2', '--',
                 str(MEMBER_PDF), str(other)],
                capture_output=True)
            if built.returncode != 0 or not other.exists():
                self.skipTest('qpdf not available to build the fixture')

            with self.assertRaises(ValueError) as caught:
                parse_member_list(other)
            self.assertIn('church report', str(caught.exception))

    @needs_household_pdf
    def test_member_list_is_not_accepted_as_the_household_report(self):
        from utils.pdf_household_list import parse_household_list
        with self.assertRaises(ValueError) as caught:
            parse_household_list(MEMBER_PDF)
        self.assertIn('household', str(caught.exception).lower())

    @needs_household_pdf
    def test_reports_are_identified_by_their_columns(self):
        from utils.pdf_import import identify_reports
        found = identify_reports([HOUSEHOLD_PDF, MEMBER_PDF])
        self.assertEqual(found['errors'], [])
        self.assertEqual(found['member'], MEMBER_PDF)
        self.assertEqual(found['household'], HOUSEHOLD_PDF)

    @needs_household_pdf
    def test_two_of_the_same_report_is_rejected(self):
        from utils.pdf_import import identify_reports
        found = identify_reports([MEMBER_PDF, MEMBER_PDF])
        self.assertTrue(found['errors'])
        self.assertIn('member list', found['errors'][0].lower())


class DataDirTestCase(unittest.TestCase):
    """Base for tests that write: each gets a throwaway MLS3_DATA_DIR."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._old_dir = os.environ.get('MLS3_DATA_DIR')
        os.environ['MLS3_DATA_DIR'] = str(self.tmp)

        for name in ('members.csv', 'households.csv',
                     'prayer_assignments.csv', 'appointments.csv'):
            source = ROOT / 'data' / name
            if source.exists():
                shutil.copy(source, self.tmp / name)

        import config
        import importlib
        importlib.reload(config)
        import models
        importlib.reload(models)
        from utils import backup
        importlib.reload(backup)
        import utils.pdf_import
        importlib.reload(utils.pdf_import)

        self.config = config
        self.models = models
        self.backup = backup
        self.pdf_import = utils.pdf_import

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._old_dir is None:
            os.environ.pop('MLS3_DATA_DIR', None)
        else:
            os.environ['MLS3_DATA_DIR'] = self._old_dir


class TestBackup(DataDirTestCase):

    def test_snapshot_captures_every_data_file(self):
        snapshot = self.backup.create(reason='test')
        self.assertIsNotNone(snapshot)
        for name in ('members.csv', 'households.csv',
                     'prayer_assignments.csv', 'appointments.csv'):
            self.assertTrue((snapshot.path / name).exists(), name)
        self.assertTrue((snapshot.path / 'manifest.json').exists())

    def test_row_counts_handle_multi_line_addresses(self):
        # Household addresses contain newlines inside quoted fields, so counting
        # lines would overstate the number of households.
        snapshot = self.backup.create(reason='test')
        households = self.models.HouseholdDatabase()
        self.assertEqual(snapshot.counts['households.csv'], len(households.households))

    def test_restore_puts_the_data_back(self):
        members = self.models.MemberDatabase()
        before = len(members.members)
        snapshot = self.backup.create(reason='test')

        members.members = members.members[:1]
        members.save()
        self.assertEqual(len(self.models.MemberDatabase().members), 1)

        self.backup.restore(snapshot.timestamp)
        self.assertEqual(len(self.models.MemberDatabase().members), before)

    def test_restoring_is_itself_undoable(self):
        first = self.backup.create(reason='one')
        self.backup.restore(first.timestamp)
        reasons = [s.reason for s in self.backup.list_snapshots()]
        self.assertTrue(any('Before restoring' in r for r in reasons))

    def test_retention_prunes_the_oldest(self):
        for _ in range(self.backup.RETENTION + 3):
            self.backup.create(reason='churn')
        self.assertLessEqual(len(self.backup.list_snapshots()), self.backup.RETENTION)

    def test_a_bogus_timestamp_is_refused(self):
        with self.assertRaises(ValueError):
            self.backup.restore('../../../etc')


@needs_pdftotext
@needs_no_address_pdf
@needs_household_pdf
class TestImportPlan(DataDirTestCase):
    """End-to-end: plan, commit, and what must survive it."""

    def build(self):
        members = self.models.MemberDatabase()
        households = self.models.HouseholdDatabase()
        plan = self.pdf_import.build_plan(
            MEMBER_PDF_NO_ADDRESS, HOUSEHOLD_PDF, members, households)
        return plan, members, households

    def test_first_import_adds_everyone_and_retires_the_rest(self):
        plan, members, households = self.build()
        self.assertEqual(plan.errors, [])
        counts = plan.counts
        self.assertEqual(counts['add'], EXPECTED_PEOPLE)
        self.assertEqual(counts['left_ward'], len(members.members))

    def test_commit_then_reimport_changes_nothing(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        again, members2, households2 = self.build()
        self.assertEqual(again.counts['unchanged'], EXPECTED_PEOPLE)
        self.assertFalse(again.changes_anything)

    @needs_member_pdf
    def test_either_member_list_layout_gives_the_same_result(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        members2 = self.models.MemberDatabase()
        households2 = self.models.HouseholdDatabase()
        with_address = self.pdf_import.build_plan(
            MEMBER_PDF, HOUSEHOLD_PDF, members2, households2)
        self.assertFalse(with_address.changes_anything)

    def test_households_and_roles_are_stored(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        stored_households = self.models.HouseholdDatabase()
        in_ward = [m for m in stored.members if m.in_ward]

        self.assertEqual(len(in_ward), EXPECTED_PEOPLE)
        self.assertEqual(sum(1 for m in in_ward if m.household_role == 'head'),
                         EXPECTED_HEADS)
        self.assertEqual(sum(1 for m in in_ward if m.household_role == 'dependent'),
                         EXPECTED_DEPENDENTS)
        self.assertFalse([m for m in in_ward if m.household_id is None])

        # Every household on the report is stored, and everyone in the ward
        # sits in one of them. Households that predate the import are left
        # alone - members who have left still point at them - so the stored
        # total may be higher than the report's.
        from utils.pdf_household_list import parse_household_list
        reported = {h.name for h in parse_household_list(HOUSEHOLD_PDF).households}
        stored_names = {h.name for h in stored_households.households}
        self.assertEqual(reported - stored_names, set())

        reported_ids = {h.household_id for h in stored_households.households
                        if h.name in reported}
        self.assertEqual(len(reported_ids), EXPECTED_HOUSEHOLDS)
        self.assertTrue(all(m.household_id in reported_ids for m in in_ward))

    def test_adult_children_are_not_treated_as_parents(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        stored_households = self.models.HouseholdDatabase()
        glad = next(h for h in stored_households.households
                    if h.name.startswith('Glad,'))
        household_members = stored.get_household_members(glad.household_id)

        adult_child = next(m for m in household_members
                           if m.first_name == 'Haydon')
        self.assertGreaterEqual(adult_child.age, 18)
        self.assertEqual(adult_child.household_role, 'dependent')

        parents = stored.get_parents(adult_child.member_id, stored_households)
        self.assertEqual(sorted(p.first_name for p in parents),
                         ['Charity', 'Jason'])

    def test_household_ids_are_stable_across_imports(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)
        first = {h.name: h.household_id
                 for h in self.models.HouseholdDatabase().households}

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)
        second = {h.name: h.household_id
                  for h in self.models.HouseholdDatabase().households}

        self.assertEqual(first, second)

    def test_absent_members_leave_the_ward_but_keep_everything(self):
        # Absence from the reports means they are off the ward's records, which
        # is all the import may conclude. The row stays, the history stays, and
        # `active` - the user's own judgement - is not touched.
        before = self.models.MemberDatabase()
        original_ids = {m.member_id for m in before.members}
        kept = before.get_by_id(min(original_ids))
        kept.last_prayer_date = '2026-01-11'
        kept.notes = 'keep me'
        kept.flag = 'blue'
        kept.dont_ask_prayer = True
        kept.active = True
        before.save()

        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        after = self.models.MemberDatabase()
        survivor = after.get_by_id(kept.member_id)
        self.assertIsNotNone(survivor, 'an absent member was deleted')
        self.assertFalse(survivor.in_ward, 'should be off the ward records')
        self.assertTrue(survivor.active, 'the import wrote the user\'s own flag')
        self.assertEqual(survivor.last_prayer_date, '2026-01-11')
        self.assertEqual(survivor.notes, 'keep me')
        self.assertEqual(survivor.flag, 'blue')
        self.assertTrue(survivor.dont_ask_prayer)

    def test_someone_out_of_the_ward_is_hidden_from_every_list(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        gone = next(m for m in stored.members if m.in_ward)
        gone.in_ward = False
        stored.save()

        stored = self.models.MemberDatabase()
        self.assertNotIn(gone.member_id,
                         [m.member_id for m in stored.get_active_members()])
        self.assertNotIn(gone.member_id,
                         [m.member_id for m in stored.search(gone.first_name)])
        if gone.household_id:
            self.assertNotIn(gone.member_id,
                             [m.member_id for m in
                              stored.get_household_members(gone.household_id)])

    def test_a_manually_deactivated_member_is_left_deactivated(self):
        # `active` is the user's own flag, set from the Members page to control
        # who appears in lists. An import must not switch someone back on just
        # because the church still lists them - that silently undoes the
        # decision, and on a 342-person import nobody would notice.
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        someone = next(m for m in stored.members if m.in_ward)
        someone.active = False
        stored.save()

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)

        after = self.models.MemberDatabase().get_by_id(someone.member_id)
        self.assertFalse(after.active, 'the import turned a member back on')

    def test_moving_out_and_back_preserves_the_active_flag(self):
        # The case that motivated splitting the flag: someone moves out of the
        # ward while church-inactive, then moves back. They should come back
        # exactly as the user last judged them, not quietly reinstated.
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        wanderer = next(m for m in stored.members if m.in_ward)
        wanderer.active = False          # the user's judgement
        wanderer.in_ward = False         # and then they move away
        wanderer.last_prayer_date = '2026-02-02'
        stored.save()

        # The reports still list them, so the next import brings them back.
        plan2, members2, households2 = self.build()
        returning = [c for c in plan2.member_changes
                     if c.member_id == wanderer.member_id]
        self.assertEqual(len(returning), 1)
        self.assertEqual(returning[0].fields.get('in_ward'), ('False', 'True'))
        self.assertNotIn('active', returning[0].fields)

        self.pdf_import.commit(plan2, members2, households2)
        after = self.models.MemberDatabase().get_by_id(wanderer.member_id)
        self.assertTrue(after.in_ward, 'should be back on the records')
        self.assertFalse(after.active, 'the import reinstated them')
        self.assertEqual(after.last_prayer_date, '2026-02-02')

    def test_two_strangers_sharing_a_birthday_are_not_fused(self):
        # Gender and birth date alone are not an identity. Without a name
        # check, one person leaving and an unrelated person of the same gender
        # and birthday arriving are merged, and the newcomer silently inherits
        # the member id, prayer history, notes and flags of someone who left.
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        victim = next(m for m in stored.members if m.in_ward and m.birthday)
        victim.first_name, victim.last_name = 'Totally', 'Departed'
        victim.notes = 'a different human being'
        stored.save()

        plan2, _, _ = self.build()
        self.assertEqual(plan2.by_action(self.pdf_import.RENAME), [])
        self.assertEqual(plan2.counts['add'], 1)
        self.assertEqual(plan2.counts['left_ward'], 1)

    def test_a_misspelt_surname_is_still_a_rename(self):
        self._assert_rename(lambda m: setattr(m, 'last_name', m.last_name + 'ff'))

    def test_a_married_name_is_still_a_rename(self):
        # Surname replaced outright, first name intact.
        self._assert_rename(lambda m: setattr(m, 'last_name', 'Zimmerman'))

    def test_a_misspelt_first_name_is_still_a_rename(self):
        self._assert_rename(lambda m: setattr(m, 'first_name', m.first_name + 'e'))

    def _assert_rename(self, mutate):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        target = next(m for m in stored.members if m.in_ward and m.birthday)
        mutate(target)
        stored.save()

        plan2, _, _ = self.build()
        self.assertEqual(len(plan2.by_action(self.pdf_import.RENAME)), 1)
        self.assertEqual(plan2.counts['add'], 0)
        self.assertEqual(plan2.counts['left_ward'], 0)

    def test_two_members_with_the_same_name_are_reported(self):
        # Only one of them can be matched to a report row, so the other is
        # silently skipped by every import unless it is called out.
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        first, second = [m for m in stored.members if m.in_ward][:2]
        second.first_name, second.last_name = first.first_name, first.last_name
        stored.save()

        plan2, _, _ = self.build()
        self.assertTrue(any('more than one member' in w for w in plan2.warnings),
                        plan2.warnings)

    def test_a_household_phone_entered_by_hand_is_kept(self):
        # Eight households in a typical report have no phone. An absent value
        # means "not printed", not "deleted".
        from utils.pdf_household_list import parse_household_list
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        phoneless = [h.name for h in parse_household_list(HOUSEHOLD_PDF).households
                     if not h.phone]
        self.assertTrue(phoneless, 'expected some households with no phone')

        stored = self.models.HouseholdDatabase()
        target = next(h for h in stored.households if h.name == phoneless[0])
        target.phone = '801-555-9999'
        stored.save()

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)

        after = next(h for h in self.models.HouseholdDatabase().households
                     if h.name == phoneless[0])
        self.assertEqual(after.phone, '801-555-9999')

    def test_a_household_address_entered_by_hand_is_kept(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.HouseholdDatabase()
        target = next(h for h in stored.households if h.name == 'Barton, Linda')
        target.address = '12 Hand Entered Ln\nRiverton UT'
        stored.save()

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)

        after = next(h for h in self.models.HouseholdDatabase().households
                     if h.name == 'Barton, Linda')
        self.assertEqual(after.address, '12 Hand Entered Ln\nRiverton UT')

    def test_a_household_keeps_its_id_and_email_through_a_head_change(self):
        # A death or a marriage changes both the head set and the name at once,
        # which defeats the first two matching rules. Rebuilding the household
        # under a new id would drop its email, which the report has no source
        # for.
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored_hh = self.models.HouseholdDatabase()
        stored_m = self.models.MemberDatabase()
        target = next(h for h in stored_hh.households
                      if h.name == 'Andreason, Austin & Coral')
        original_id = target.household_id
        target.name = 'Andreason, Coral'
        target.email = 'andreason@example.com'
        stored_hh.save()
        for m in stored_m.members:
            if m.household_id == original_id and m.first_name == 'Austin':
                m.household_role = 'dependent'
        stored_m.save()

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)

        rebuilt = next(h for h in self.models.HouseholdDatabase().households
                       if h.name == 'Andreason, Austin & Coral')
        self.assertEqual(rebuilt.household_id, original_id)
        self.assertEqual(rebuilt.email, 'andreason@example.com')

    def test_a_member_phone_entered_by_hand_is_kept(self):
        # Some people have no phone on the report but a number you tracked down.
        from utils.pdf_member_list import parse_member_list
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        no_phone = [m.name for m in parse_member_list(MEMBER_PDF_NO_ADDRESS).members
                    if not m.phone]
        self.assertTrue(no_phone, 'expected some people with no phone')

        last, first = [p.strip() for p in no_phone[0].split(',', 1)]
        stored = self.models.MemberDatabase()
        target = next(m for m in stored.members
                      if m.last_name == last and m.first_name == first)
        target.phone = '801-555-1234'
        stored.save()

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)

        after = self.models.MemberDatabase().get_by_id(target.member_id)
        self.assertEqual(after.phone, '801-555-1234')

    def test_absent_members_are_still_deactivated(self):
        # The flag is only ever turned off by absence from the reports.
        plan, members, households = self.build()
        self.assertEqual(plan.counts['left_ward'], len(members.members))

    def test_mls3_data_survives_an_update(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        someone = next(m for m in stored.members if m.in_ward)
        someone.last_prayer_date = '2026-02-01'
        someone.notes = 'likes mornings'
        someone.aka = 'Bud'
        someone.flag = 'yellow'
        someone.skip_until = '2026-12-01'
        someone.phone = 'stale'
        stored.save()

        plan2, members2, households2 = self.build()
        self.pdf_import.commit(plan2, members2, households2)

        after = self.models.MemberDatabase().get_by_id(someone.member_id)
        self.assertEqual(after.last_prayer_date, '2026-02-01')
        self.assertEqual(after.notes, 'likes mornings')
        self.assertEqual(after.aka, 'Bud')
        self.assertEqual(after.flag, 'yellow')
        self.assertEqual(after.skip_until, '2026-12-01')
        self.assertNotEqual(after.phone, 'stale')   # the report is authoritative here

    def test_a_corrected_spelling_keeps_one_record_and_its_history(self):
        # Otherwise this reads as one arrival plus one departure, stranding the
        # person's prayer history on a deactivated row.
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        stored = self.models.MemberDatabase()
        someone = next(m for m in stored.members if m.in_ward and m.birthday)
        original_id = someone.member_id
        someone.last_name = someone.last_name + 'ff'
        someone.last_prayer_date = '2026-03-08'
        stored.save()
        total_before = len(stored.members)

        plan2, members2, households2 = self.build()
        self.assertEqual(len(plan2.by_action(self.pdf_import.RENAME)), 1)
        self.assertEqual(plan2.counts['add'], 0)
        self.assertEqual(plan2.counts['left_ward'], 0)

        self.pdf_import.commit(plan2, members2, households2)
        after = self.models.MemberDatabase()
        self.assertEqual(len(after.members), total_before)
        self.assertEqual(after.get_by_id(original_id).last_prayer_date, '2026-03-08')

    def test_commit_takes_a_backup_first(self):
        plan, members, households = self.build()
        result = self.pdf_import.commit(plan, members, households)
        self.assertIsNotNone(result['backup'])
        self.assertTrue(self.backup.get(result['backup']['timestamp']))

    def test_an_import_can_be_undone(self):
        before = len(self.models.MemberDatabase().members)
        plan, members, households = self.build()
        result = self.pdf_import.commit(plan, members, households)
        self.assertNotEqual(len(self.models.MemberDatabase().members), before)

        self.backup.restore(result['backup']['timestamp'])
        self.assertEqual(len(self.models.MemberDatabase().members), before)

    @needs_member_pdf
    def test_mismatched_reports_are_refused(self):
        # Two member lists describe no households. build_plan reports problems
        # rather than raising, so they can be shown on the page, but the plan
        # must carry an error and must not be committable.
        members = self.models.MemberDatabase()
        households = self.models.HouseholdDatabase()
        plan = self.pdf_import.build_plan(MEMBER_PDF, MEMBER_PDF, members, households)

        self.assertTrue(plan.errors)
        with self.assertRaises(ValueError):
            self.pdf_import.commit(plan, members, households)

    def test_a_plan_with_errors_cannot_be_committed(self):
        members = self.models.MemberDatabase()
        households = self.models.HouseholdDatabase()
        plan = self.pdf_import.ImportPlan()
        plan.errors.append('something is wrong')
        with self.assertRaises(ValueError):
            self.pdf_import.commit(plan, members, households)


if __name__ == '__main__':
    unittest.main(verbosity=2)
