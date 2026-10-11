#!/usr/bin/env python3
"""
Tests for the things that protect the data files.

These simulate failures rather than successes: a process killed mid-save, a
truncated file, two threads writing at once, an import interrupted between its
two renames. Each one corresponds to a way the data could be lost on a phone,
where the OS kills background processes whenever it feels like it.

Run with:
    ./venv/bin/python -m unittest discover tests -v
"""
import csv
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class DataDirTestCase(unittest.TestCase):
    """Each test gets its own throwaway MLS3_DATA_DIR with the sample data."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._old_dir = os.environ.get('MLS3_DATA_DIR')
        os.environ['MLS3_DATA_DIR'] = str(self.tmp)

        for name in ('members.csv', 'households.csv',
                     'prayer_assignments.csv', 'appointments.csv',
                     'message_templates.yaml', 'appointment_types.yaml'):
            source = ROOT / 'data' / name
            if source.exists():
                shutil.copy(source, self.tmp / name)

        import importlib
        import config
        importlib.reload(config)
        import models
        importlib.reload(models)
        from utils import backup
        importlib.reload(backup)
        import utils.check_data
        importlib.reload(utils.check_data)
        import utils.pdf_import
        importlib.reload(utils.pdf_import)

        self.config = config
        self.models = models
        self.backup = backup
        self.check_data = utils.check_data
        self.pdf_import = utils.pdf_import

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._old_dir is None:
            os.environ.pop('MLS3_DATA_DIR', None)
        else:
            os.environ['MLS3_DATA_DIR'] = self._old_dir

    def members_path(self) -> Path:
        return self.tmp / 'members.csv'


class TestAtomicWrites(DataDirTestCase):
    """A save either lands completely or not at all."""

    def test_a_save_killed_partway_leaves_the_original_untouched(self):
        # This is the failure that used to lose half the ward: open(path, 'w')
        # is destructive from the moment it truncates.
        db = self.models.MemberDatabase()
        before = self.members_path().read_bytes()

        real_fsync = os.fsync
        os.fsync = lambda fd: (_ for _ in ()).throw(OSError('process killed'))
        try:
            with self.assertRaises(OSError):
                db.save()
        finally:
            os.fsync = real_fsync

        self.assertEqual(self.members_path().read_bytes(), before)
        self.assertEqual(len(self.models.MemberDatabase().members), len(db.members))

    def test_a_failed_save_leaves_no_staging_file_behind(self):
        db = self.models.MemberDatabase()

        real_fsync = os.fsync
        os.fsync = lambda fd: (_ for _ in ()).throw(OSError('process killed'))
        try:
            with self.assertRaises(OSError):
                db.save()
        finally:
            os.fsync = real_fsync

        self.assertEqual(list(self.tmp.glob('*.tmp')), [])

    def test_a_normal_save_publishes_and_leaves_nothing_staged(self):
        db = self.models.MemberDatabase()
        db.members[0].notes = 'changed'
        db.save()

        self.assertEqual(list(self.tmp.glob('*.tmp')), [])
        self.assertEqual(self.models.MemberDatabase().members[0].notes, 'changed')

    def test_staged_writes_are_not_visible_until_published(self):
        db = self.models.MemberDatabase()
        original = len(db.members)
        db.members = db.members[:1]

        staged_path, final_path = db.stage()
        self.assertTrue(staged_path.exists())
        # Nothing published yet, so readers still see the old contents.
        self.assertEqual(len(self.models.MemberDatabase().members), original)

        self.models.publish([(staged_path, final_path)])
        self.assertEqual(len(self.models.MemberDatabase().members), 1)

    def test_concurrent_saves_never_leave_a_readable_file_broken(self):
        # Flask serves requests on threads and the databases are module-level,
        # so two handlers can save at the same time.
        db = self.models.MemberDatabase()
        expected = len(db.members)
        errors = []

        def writer():
            for _ in range(20):
                try:
                    db.save()
                except Exception as e:                      # pragma: no cover
                    errors.append(e)

        def reader():
            for _ in range(40):
                try:
                    found = len(self.models.MemberDatabase().members)
                    if found != expected:
                        errors.append(AssertionError(
                            f'read {found} members, expected {expected}'))
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(list(self.tmp.glob('*.tmp')), [])

    def test_every_database_writes_durably(self):
        # All four stores share the mechanism; a new one must not be forgotten.
        for factory in (self.models.MemberDatabase, self.models.HouseholdDatabase,
                        self.models.PrayerAssignmentDatabase,
                        self.models.AppointmentDatabase):
            db = factory()
            before = db.csv_path.read_bytes()

            real_fsync = os.fsync
            os.fsync = lambda fd: (_ for _ in ()).throw(OSError('killed'))
            try:
                with self.assertRaises(OSError, msg=factory.__name__):
                    db.save()
            finally:
                os.fsync = real_fsync

            self.assertEqual(db.csv_path.read_bytes(), before, factory.__name__)


class TestRefusesDamagedFiles(DataDirTestCase):
    """A damaged file must fail loudly, not load halfway."""

    def test_a_file_cut_off_mid_row_is_refused(self):
        path = self.members_path()
        data = path.read_bytes()
        path.write_bytes(data[:len(data) // 2])

        with self.assertRaises(self.models.DataIntegrityError) as caught:
            self.models.MemberDatabase()
        self.assertIn('cut off', str(caught.exception))

    def test_an_empty_file_is_refused(self):
        self.members_path().write_bytes(b'')
        with self.assertRaises(self.models.DataIntegrityError):
            self.models.MemberDatabase()

    def test_a_missing_required_column_is_refused(self):
        rows = self._read()
        fields = [f for f in rows[0] if f != 'member_id']
        with open(self.members_path(), 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

        with self.assertRaises(self.models.DataIntegrityError) as caught:
            self.models.MemberDatabase()
        self.assertIn('member_id', str(caught.exception))

    def test_an_unreadable_id_is_refused_and_names_the_line(self):
        rows = self._read()
        rows[2]['member_id'] = 'not-a-number'
        self._write(rows)

        with self.assertRaises(self.models.DataIntegrityError) as caught:
            self.models.MemberDatabase()
        message = str(caught.exception)
        self.assertIn('line 4', message)
        self.assertIn('member_id', message)

    def test_duplicate_ids_are_refused(self):
        rows = self._read()
        rows[1]['member_id'] = rows[0]['member_id']
        self._write(rows)

        with self.assertRaises(self.models.DataIntegrityError) as caught:
            self.models.MemberDatabase()
        self.assertIn('more than one row', str(caught.exception))

    def test_a_header_only_file_loads_as_empty(self):
        # Not damage - a brand new, empty database.
        rows = self._read()
        self._write(rows[:0], fields=list(rows[0]))
        self.assertEqual(self.models.MemberDatabase().members, [])

    def test_a_missing_file_loads_as_empty(self):
        self.members_path().unlink()
        self.assertEqual(self.models.MemberDatabase().members, [])

    def _read(self):
        with open(self.members_path(), newline='') as f:
            return list(csv.DictReader(f))

    def _write(self, rows, fields=None):
        fields = fields or list(rows[0])
        with open(self.members_path(), 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


class TestIntegrityCheck(DataDirTestCase):
    """Damage that parses cleanly but does not hang together."""

    def test_clean_data_passes(self):
        report = self.check_data.check(compare_backup=False)
        self.assertTrue(report.ok, [p.message for p in report.errors])

    def test_counts_are_reported(self):
        report = self.check_data.check(compare_backup=False)
        self.assertEqual(report.counts['members'],
                         len(self.models.MemberDatabase().members))

    def test_a_member_in_a_household_that_is_gone_is_an_error(self):
        db = self.models.MemberDatabase()
        db.members[0].household_id = 99999
        db.save()

        report = self.check_data.check(compare_backup=False)
        self.assertFalse(report.ok)
        self.assertTrue(any('no longer exists' in p.message for p in report.errors))

    def test_an_unrecognised_role_is_an_error(self):
        db = self.models.MemberDatabase()
        db.members[0].household_role = 'parent'
        db.save()

        report = self.check_data.check(compare_backup=False)
        self.assertFalse(report.ok)
        self.assertTrue(any('household role' in p.message for p in report.errors))

    def test_a_prayer_assignment_for_a_missing_member_is_an_error(self):
        assignments = self.models.PrayerAssignmentDatabase()
        if not assignments.assignments:
            self.skipTest('no sample prayer assignments')
        assignments.assignments[0].member_id = 99999
        assignments.save()

        report = self.check_data.check(compare_backup=False)
        self.assertFalse(report.ok)
        self.assertTrue(any('prayer assignment' in p.message for p in report.errors))

    def test_an_appointment_for_a_missing_member_is_an_error(self):
        appointments = self.models.AppointmentDatabase()
        if not appointments.appointments:
            self.skipTest('no sample appointments')
        appointments.appointments[0].member_id = 99999
        appointments.save()

        report = self.check_data.check(compare_backup=False)
        self.assertFalse(report.ok)
        self.assertTrue(any('appointment' in p.message for p in report.errors))

    def test_a_malformed_date_is_a_warning_not_an_error(self):
        db = self.models.MemberDatabase()
        db.members[0].birthday = '03/14/1975'
        db.save()

        report = self.check_data.check(compare_backup=False)
        self.assertTrue(report.ok)
        self.assertTrue(any('YYYY-MM-DD' in p.message for p in report.warnings))

    def test_a_leftover_staging_file_is_reported(self):
        (self.tmp / 'members.csv.tmp').write_text('interrupted\n')
        report = self.check_data.check(compare_backup=False)
        self.assertTrue(any('unfinished save' in p.message for p in report.warnings))

    def test_rows_lost_on_a_row_boundary_are_noticed(self):
        # The load-time guard cannot see this: the file ends cleanly and every
        # row parses. Only the comparison against the last backup catches it.
        self.backup.create(reason='test')
        path = self.members_path()
        lines = path.read_text().splitlines(keepends=True)
        self.assertGreater(len(lines), 6, 'need a few rows to drop some')
        path.write_text(''.join(lines[:3]))

        self.models.MemberDatabase()        # loads without complaint
        report = self.check_data.check()
        self.assertTrue(any('at the last backup' in p.message
                            for p in report.warnings),
                        [p.message for p in report.warnings])

    def test_no_backups_is_itself_worth_mentioning(self):
        report = self.check_data.check()
        self.assertTrue(any('no backups' in p.message.lower()
                            for p in report.warnings))


class TestInterruptedImport(DataDirTestCase):
    """An import killed between its two renames must be noticed."""

    def test_no_marker_means_nothing_to_report(self):
        self.assertIsNone(self.pdf_import.check_interrupted_import())

    def test_a_marker_is_reported_and_names_the_backup(self):
        snapshot = self.backup.create(reason='Before PDF import')
        (self.tmp / '.import-in-progress').write_text(snapshot.timestamp)

        message = self.pdf_import.check_interrupted_import()
        self.assertIsNotNone(message)
        self.assertIn('interrupted', message)
        self.assertIn(snapshot.label, message)

    def test_a_marker_without_a_usable_backup_still_warns(self):
        (self.tmp / '.import-in-progress').write_text('nonsense')
        message = self.pdf_import.check_interrupted_import()
        self.assertIsNotNone(message)
        self.assertIn('interrupted', message)

    def test_the_marker_can_be_cleared(self):
        (self.tmp / '.import-in-progress').write_text('')
        self.pdf_import.clear_interrupted_import()
        self.assertIsNone(self.pdf_import.check_interrupted_import())


class TestBackupTrustworthiness(DataDirTestCase):
    """
    A backup is only useful if it can actually be restored.

    The data directory is typically synced to cloud storage, which makes two
    cases realistic: a snapshot captured mid-upload, and a damaged snapshot
    mirrored outward where it can crowd out good ones.
    """

    def test_a_snapshot_of_healthy_data_is_marked_verified(self):
        snapshot = self.backup.create(reason='test')
        self.assertIs(snapshot.verified, True)
        self.assertEqual(snapshot.verify_problems, [])
        self.assertTrue(snapshot.restorable)
        self.assertEqual(snapshot.status, 'verified')

    def test_counts_come_from_parsing_not_from_counting_lines(self):
        # Household addresses span several lines inside quoted fields.
        snapshot = self.backup.create(reason='test')
        self.assertEqual(snapshot.counts['households.csv'],
                         len(self.models.HouseholdDatabase().households))

    def test_a_snapshot_taken_over_a_damaged_file_is_marked_and_refused(self):
        path = self.members_path()
        data = path.read_bytes()
        path.write_bytes(data[:len(data) // 2])

        snapshot = self.backup.create(reason='over damaged data')
        self.assertIs(snapshot.verified, False)
        self.assertTrue(snapshot.verify_problems)
        self.assertFalse(snapshot.restorable)
        self.assertEqual(snapshot.status, 'damaged')

        with self.assertRaises(ValueError) as caught:
            self.backup.restore(snapshot.timestamp)
        self.assertIn('damaged', str(caught.exception))

    def test_a_snapshot_with_no_manifest_is_incomplete_and_refused(self):
        # The manifest is written last, so its absence means the snapshot never
        # finished - or was copied before it finished syncing.
        good = self.backup.create(reason='test')
        partial = self.backup.backup_root() / '20991231_235959'
        partial.mkdir()
        shutil.copy(good.path / 'members.csv', partial / 'members.csv')

        snapshot = self.backup.get('20991231_235959')
        self.assertFalse(snapshot.complete)
        self.assertFalse(snapshot.restorable)
        self.assertIn('manifest', snapshot.incomplete_reason)

        with self.assertRaises(ValueError) as caught:
            self.backup.restore(snapshot.timestamp)
        self.assertIn('out of step', str(caught.exception))

    def test_a_snapshot_missing_a_promised_file_is_incomplete(self):
        snapshot = self.backup.create(reason='test')
        (snapshot.path / 'households.csv').unlink()

        reread = self.backup.get(snapshot.timestamp)
        self.assertFalse(reread.complete)
        self.assertIn('households.csv', reread.incomplete_reason)
        with self.assertRaises(ValueError):
            self.backup.restore(snapshot.timestamp)

    def test_restoring_an_incomplete_snapshot_cannot_mix_old_and_new_files(self):
        # Restoring only members.csv would leave members pointing at household
        # ids from a different era.
        good = self.backup.create(reason='test')
        before = (self.tmp / 'households.csv').read_bytes()

        partial = self.backup.backup_root() / '20991231_235958'
        partial.mkdir()
        shutil.copy(good.path / 'members.csv', partial / 'members.csv')

        with self.assertRaises(ValueError):
            self.backup.restore('20991231_235958')
        self.assertEqual((self.tmp / 'households.csv').read_bytes(), before)

    def test_a_verified_snapshot_still_restores(self):
        snapshot = self.backup.create(reason='test')
        before = len(self.models.MemberDatabase().members)

        db = self.models.MemberDatabase()
        db.members = db.members[:1]
        db.save()

        self.backup.restore(snapshot.timestamp)
        self.assertEqual(len(self.models.MemberDatabase().members), before)

    def test_prune_never_drops_the_last_verified_snapshot(self):
        # A run of snapshots taken over damaged data must not be able to evict
        # the last copy known to be readable.
        path = self.members_path()
        healthy = path.read_bytes()
        last_good = self.backup.create(reason='last good')

        for i in range(5):
            path.write_bytes(healthy[:len(healthy) // 2])
            self.backup.create(reason=f'damaged {i}')
            path.write_bytes(healthy)

        self.backup.prune(keep=2)
        remaining = {s.timestamp for s in self.backup.list_snapshots()}
        self.assertIn(last_good.timestamp, remaining)

    def test_hand_edited_yaml_is_covered(self):
        # Templates and appointment types are hand-edited, so they are more
        # likely to be broken by a slip than the CSVs and need the same
        # point-in-time restore.
        snapshot = self.backup.create(reason='test')
        self.assertIn('message_templates.yaml', snapshot.files)
        self.assertIn('appointment_types.yaml', snapshot.files)
        self.assertTrue((snapshot.path / 'message_templates.yaml').exists())
        self.assertTrue((snapshot.path / 'appointment_types.yaml').exists())
        self.assertIs(snapshot.verified, True)

    def test_secrets_are_deliberately_not_backed_up(self):
        # Both are regenerable, and copying them into every snapshot would
        # multiply the exposure for nothing.
        covered = self.backup.data_files()
        self.assertNotIn('credentials.json', covered)
        self.assertNotIn('token.pickle', covered)

    def test_yaml_counts_are_parsed_not_line_counted(self):
        snapshot = self.backup.create(reason='test')
        self.assertEqual(snapshot.counts['appointment_types.yaml'],
                         len(self.models.AppointmentTypesDatabase().types))

    def test_a_snapshot_over_a_broken_template_is_refused(self):
        (self.tmp / 'message_templates.yaml').write_text(
            "prayer:\n  invite: 'unterminated\n   bad: [[[\n")

        snapshot = self.backup.create(reason='over broken template')
        self.assertIs(snapshot.verified, False)
        self.assertFalse(snapshot.restorable)
        self.assertTrue(any('message_templates.yaml' in p
                            for p in snapshot.verify_problems))
        with self.assertRaises(ValueError):
            self.backup.restore(snapshot.timestamp)

    def test_an_empty_template_file_is_reported_plainly(self):
        # It parses to None and then fails deep inside the loader, which makes
        # for a baffling message unless it is caught up front.
        (self.tmp / 'message_templates.yaml').write_text('')

        snapshot = self.backup.create(reason='over empty template')
        self.assertIs(snapshot.verified, False)
        self.assertIn('message_templates.yaml: is empty', snapshot.verify_problems)

    def test_restoring_brings_templates_back(self):
        path = self.tmp / 'message_templates.yaml'
        original = path.read_text()
        snapshot = self.backup.create(reason='test')

        path.write_text('prayer:\n  invite: "wrecked"\n')
        self.backup.restore(snapshot.timestamp)

        self.assertEqual(path.read_text(), original)
        self.assertEqual(len(self.models.MessageTemplates().templates), 3)

    def test_retention_is_thirty(self):
        self.assertEqual(self.backup.RETENTION, 30)


MEMBER_PDF = ROOT / 'import-sample3.pdf'
HOUSEHOLD_PDF = ROOT / 'household-sample.pdf'

try:
    from utils.pdf_tables import PdfToolMissing, require_pdftotext
    require_pdftotext()
    HAVE_PDFTOTEXT = True
except (PdfToolMissing, ImportError):
    HAVE_PDFTOTEXT = False


@unittest.skipUnless(HAVE_PDFTOTEXT and MEMBER_PDF.exists() and HOUSEHOLD_PDF.exists(),
                     'sample reports and pdftotext needed')
class TestImportIsTransactional(DataDirTestCase):
    """Members and households must never be left disagreeing."""

    def build(self):
        members = self.models.MemberDatabase()
        households = self.models.HouseholdDatabase()
        plan = self.pdf_import.build_plan(MEMBER_PDF, HOUSEHOLD_PDF,
                                          members, households)
        return plan, members, households

    def test_a_commit_backs_up_before_and_after(self):
        plan, members, households = self.build()
        result = self.pdf_import.commit(plan, members, households)

        self.assertIsNotNone(result['backup'])
        self.assertIsNotNone(result['backup_after'])
        reasons = [s.reason for s in self.backup.list_snapshots()]
        self.assertIn('Before PDF import', reasons)
        self.assertIn('After PDF import', reasons)

    def test_the_after_backup_holds_the_imported_data(self):
        # Without this, damage occurring after an import could only be undone
        # by discarding the import.
        plan, members, households = self.build()
        result = self.pdf_import.commit(plan, members, households)

        after = self.backup.get(result['backup_after']['timestamp'])
        self.assertEqual(after.counts['members.csv'],
                         len(self.models.MemberDatabase().members))

    def test_a_commit_leaves_no_marker_and_no_staging_files(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        self.assertFalse((self.tmp / '.import-in-progress').exists())
        self.assertEqual(list(self.tmp.glob('*.tmp')), [])

    def test_a_commit_reports_the_integrity_of_what_it_wrote(self):
        plan, members, households = self.build()
        result = self.pdf_import.commit(plan, members, households)

        self.assertIn('integrity', result)
        self.assertTrue(result['integrity']['ok'], result['integrity']['errors'])

    def test_nothing_is_published_if_staging_fails(self):
        plan, members, households = self.build()
        before_members = self.members_path().read_bytes()
        before_households = (self.tmp / 'households.csv').read_bytes()

        real_fsync = os.fsync
        os.fsync = lambda fd: (_ for _ in ()).throw(OSError('disk full'))
        try:
            with self.assertRaises(OSError):
                self.pdf_import.commit(plan, members, households)
        finally:
            os.fsync = real_fsync

        # Both live files are exactly as they were.
        self.assertEqual(self.members_path().read_bytes(), before_members)
        self.assertEqual((self.tmp / 'households.csv').read_bytes(), before_households)
        self.assertEqual(list(self.tmp.glob('*.tmp')), [])

    def test_an_import_refuses_to_run_without_a_usable_backup(self):
        # If the "before" snapshot cannot be restored, the import would not be
        # undoable, so it must not happen at all.
        plan, members, households = self.build()
        before_members = self.members_path().read_bytes()

        real_create = self.backup.create

        def unusable(*args, **kwargs):
            snapshot = real_create(*args, **kwargs)
            if snapshot is not None:
                snapshot.verified = False
                snapshot.verify_problems = ['members.csv: pretend damage']
            return snapshot

        self.backup.create = unusable
        try:
            with self.assertRaises(ValueError) as caught:
                self.pdf_import.commit(plan, members, households)
        finally:
            self.backup.create = real_create

        self.assertIn('could not be undone', str(caught.exception))
        self.assertEqual(self.members_path().read_bytes(), before_members)

    def test_the_imported_data_passes_its_own_integrity_check(self):
        plan, members, households = self.build()
        self.pdf_import.commit(plan, members, households)

        report = self.check_data.check()
        self.assertTrue(report.ok, [p.message for p in report.errors])


if __name__ == '__main__':
    unittest.main(verbosity=2)
