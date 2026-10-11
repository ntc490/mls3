#!/usr/bin/env python3
"""
Integrity check for the MLS3 data files.

Atomic writes stop a file from being half-written; this catches the other kind
of damage - data that parses fine but does not hang together. A member pointing
at a household that no longer exists, an appointment for someone who was
deleted, a household with nobody in charge of it.

Also compares the current record counts against the newest backup, which is the
one check that can notice a file truncated exactly on a row boundary - the case
the load-time guard in models.py cannot see.

Run from the command line:
    python utils/check_data.py

or from the Import page, which runs it automatically after an import.
"""
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from models import (
    AppointmentDatabase, HouseholdDatabase, MemberDatabase,
    PrayerAssignmentDatabase,
)
from utils import backup

ERROR = 'error'
WARNING = 'warning'

VALID_ROLES = ('', 'head', 'dependent')

# A drop larger than this since the last backup is reported. Deactivating
# members does not remove rows, so a real shrink means rows were lost.
COUNT_DROP_THRESHOLD = 0.10


@dataclass
class Problem:
    severity: str
    message: str

    def to_dict(self) -> dict:
        return {'severity': self.severity, 'message': self.message}


@dataclass
class Report:
    problems: List[Problem]
    counts: dict

    @property
    def errors(self) -> List[Problem]:
        return [p for p in self.problems if p.severity == ERROR]

    @property
    def warnings(self) -> List[Problem]:
        return [p for p in self.problems if p.severity == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            'ok': self.ok,
            'counts': self.counts,
            'errors': [p.message for p in self.errors],
            'warnings': [p.message for p in self.warnings],
        }


def check(members_db: MemberDatabase = None,
          households_db: HouseholdDatabase = None,
          assignments_db: PrayerAssignmentDatabase = None,
          appointments_db: AppointmentDatabase = None,
          compare_backup: bool = True) -> Report:
    """
    Check the data for inconsistencies.

    Databases already loaded by the app can be passed in; anything omitted is
    loaded from disk.
    """
    members_db = members_db if members_db is not None else MemberDatabase()
    households_db = households_db if households_db is not None else HouseholdDatabase()
    assignments_db = assignments_db if assignments_db is not None else PrayerAssignmentDatabase()
    appointments_db = appointments_db if appointments_db is not None else AppointmentDatabase()

    problems: List[Problem] = []
    members = members_db.members
    households = households_db.households

    counts = {
        'members': len(members),
        'active_members': sum(1 for m in members if m.active),
        'households': len(households),
        'assignments': len(assignments_db.assignments),
        'appointments': len(appointments_db.appointments),
    }

    member_ids = {m.member_id for m in members}
    household_ids = {h.household_id for h in households}

    _check_duplicates(problems, [m.member_id for m in members], 'member')
    _check_duplicates(problems, [h.household_id for h in households], 'household')
    _check_duplicates(problems,
                      [a.assignment_id for a in assignments_db.assignments],
                      'prayer assignment')
    _check_duplicates(problems,
                      [a.appointment_id for a in appointments_db.appointments],
                      'appointment')

    # Members pointing at households that are gone. Appointments and prayer
    # assignments pointing at members that are gone. Each would show up in the
    # app as a blank name or a crash rather than as an obvious problem.
    orphans = [m for m in members if m.household_id and m.household_id not in household_ids]
    if orphans:
        problems.append(Problem(ERROR, _listing(
            f"{len(orphans)} member(s) belong to a household that no longer exists",
            [f"{m.full_name} (household {m.household_id})" for m in orphans])))

    bad_assignments = [a for a in assignments_db.assignments if a.member_id not in member_ids]
    if bad_assignments:
        problems.append(Problem(ERROR, _listing(
            f"{len(bad_assignments)} prayer assignment(s) are for a member who no longer exists",
            [f"assignment {a.assignment_id} -> member {a.member_id}" for a in bad_assignments])))

    bad_appointments = [a for a in appointments_db.appointments if a.member_id not in member_ids]
    if bad_appointments:
        problems.append(Problem(ERROR, _listing(
            f"{len(bad_appointments)} appointment(s) are for a member who no longer exists",
            [f"appointment {a.appointment_id} -> member {a.member_id}" for a in bad_appointments])))

    bad_roles = [m for m in members if m.household_role not in VALID_ROLES]
    if bad_roles:
        problems.append(Problem(ERROR, _listing(
            f"{len(bad_roles)} member(s) have an unrecognised household role",
            [f"{m.full_name} ({m.household_role!r})" for m in bad_roles])))

    nameless = [m for m in members if not m.first_name and not m.last_name]
    if nameless:
        problems.append(Problem(ERROR,
                                f"{len(nameless)} member(s) have no name at all."))

    # Below here nothing is broken, but something is probably worth a look.
    bad_genders = [m for m in members if m.active and m.gender not in ('M', 'F')]
    if bad_genders:
        problems.append(Problem(WARNING, _listing(
            f"{len(bad_genders)} active member(s) have no gender recorded",
            [m.full_name for m in bad_genders])))

    bad_dates = [
        (m, field, value)
        for m in members
        for field, value in (('birthday', m.birthday),
                             ('last prayer date', m.last_prayer_date),
                             ('skip until', m.skip_until))
        if value and not _is_iso_date(value)
    ]
    if bad_dates:
        problems.append(Problem(WARNING, _listing(
            f"{len(bad_dates)} date(s) are not in YYYY-MM-DD form",
            [f"{m.full_name}: {field} = {value!r}" for m, field, value in bad_dates])))

    occupied = {m.household_id for m in members if m.active and m.household_id}
    headless = [
        h for h in households
        if h.household_id in occupied
        and not any(m.household_id == h.household_id and m.active
                    and m.household_role == 'head' for m in members)
    ]
    if headless:
        problems.append(Problem(WARNING, _listing(
            f"{len(headless)} household(s) have no head of household, so parents "
            f"cannot be looked up for anyone in them",
            [h.name for h in headless])))

    empty = [h for h in households
             if not any(m.household_id == h.household_id for m in members)]
    if empty:
        problems.append(Problem(WARNING,
                                f"{len(empty)} household(s) have nobody in them. "
                                f"Harmless, but they can be tidied up."))

    if compare_backup:
        _compare_with_backup(problems, counts)

    _check_stray_temp_files(problems)

    return Report(problems=problems, counts=counts)


def _check_duplicates(problems: List[Problem], ids: List[int], label: str) -> None:
    seen, duplicates = set(), set()
    for value in ids:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        problems.append(Problem(ERROR, _listing(
            f"{len(duplicates)} {label} id(s) are used more than once",
            [str(d) for d in sorted(duplicates)])))


def _compare_with_backup(problems: List[Problem], counts: dict) -> None:
    """
    Notice records that have gone missing since the last backup.

    This is the only check that can see a file truncated exactly on a row
    boundary, which parses cleanly and looks entirely normal.
    """
    snapshots = backup.list_snapshots()
    if not snapshots:
        problems.append(Problem(WARNING,
                                "There are no backups yet. Run an import, or "
                                "take one from the Import page."))
        return

    newest = snapshots[0]
    pairs = [
        ('members', 'members.csv'),
        ('households', 'households.csv'),
        ('assignments', 'prayer_assignments.csv'),
        ('appointments', 'appointments.csv'),
    ]
    for key, filename in pairs:
        was = newest.counts.get(filename)
        if not was:
            continue
        now = counts.get(key, 0)
        if now < was * (1 - COUNT_DROP_THRESHOLD):
            problems.append(Problem(WARNING,
                f"{filename} holds {now} rows but had {was} at the last backup "
                f"({newest.label}). Members are deactivated rather than deleted, "
                f"so a drop this large may mean rows were lost."))


def _check_stray_temp_files(problems: List[Problem]) -> None:
    """A leftover .tmp file means a save was interrupted."""
    leftovers = sorted(p.name for p in config.DATA_DIR.glob('*.csv.tmp'))
    if leftovers:
        problems.append(Problem(WARNING,
            f"Found an unfinished save: {', '.join(leftovers)}. The live data is "
            f"intact - these can be deleted."))


def _is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, '%Y-%m-%d')
        return True
    except (ValueError, TypeError):
        return False


def _listing(summary: str, examples: List[str], limit: int = 5) -> str:
    shown = '; '.join(examples[:limit])
    if len(examples) > limit:
        shown += f"; and {len(examples) - limit} more"
    return f"{summary}: {shown}."


if __name__ == '__main__':
    from models import DataIntegrityError

    try:
        report = check()
    except DataIntegrityError as e:
        print(f"CANNOT READ THE DATA: {e}")
        sys.exit(2)

    print(f"Data directory: {config.DATA_DIR}")
    for key, value in report.counts.items():
        print(f"  {key:16} {value}")

    for problem in report.errors:
        print(f"ERROR:   {problem.message}")
    for problem in report.warnings:
        print(f"warning: {problem.message}")

    if report.ok and not report.warnings:
        print("Everything checks out.")
    sys.exit(1 if report.errors else 0)
