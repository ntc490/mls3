#!/usr/bin/env python3
"""
Import members and households from the two church PDF reports.

Takes the member list (per-person details) and the household report (household
structure and head/dependent roles), checks them against each other, works out
exactly what would change, and applies it.

The preview and the commit share one ImportPlan, so what you confirm is what
gets written.

Preserved across every import: prayer history, dont_ask_prayer, notes, flags,
aka, skip_until, recommend_expiration - and the active flag, which belongs to the
user and is never written here at all.

The import owns `in_ward` instead: present in the reports means in_ward=True,
absent means in_ward=False, and someone out of the ward disappears from the UI
without their row or their history being touched. Keeping the two apart is what
lets a person move out, move back, and still be whatever the user last judged
them to be - church-active or not.

Usage:
    plan = build_plan(Path('members.pdf'), Path('households.pdf'),
                      members_db, households_db)
    if not plan.errors:
        result = commit(plan, members_db, households_db)
"""
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from models import Household, Member, MemberDatabase, HouseholdDatabase, publish
from utils import backup, check_data
from utils.pdf_household_list import (
    HEAD, HouseholdListReport, HouseholdRecord, parse_household_list,
)
from utils.pdf_member_list import MemberListReport, MemberRecord, parse_member_list
from utils.pdf_tables import PdfToolMissing, normalize_name, sniff_report_type

# Member fields the import owns. Everything else on a Member is MLS3's own data
# and is never touched.
IMPORTED_FIELDS = ('first_name', 'last_name', 'gender', 'phone', 'birthday')

ADD = 'add'
UPDATE = 'update'
RENAME = 'rename'
LEFT_WARD = 'left_ward'
UNCHANGED = 'unchanged'


@dataclass
class MemberChange:
    """One member's worth of change, as it will be applied."""
    action: str
    name: str
    member_id: Optional[int] = None
    fields: Dict[str, Tuple[str, str]] = field(default_factory=dict)   # field -> (old, new)
    record: Optional[MemberRecord] = None
    household_name: str = ''
    # Where this person lands. Kept as real attributes, not read back out of
    # `fields`: `fields` is for showing the diff and omits anything unchanged.
    household_id: Optional[int] = None
    role: str = ''

    def to_dict(self) -> dict:
        return {
            'action': self.action,
            'name': self.name,
            'member_id': self.member_id,
            'household': self.household_name,
            'role': self.role,
            'fields': {k: {'old': v[0], 'new': v[1]} for k, v in self.fields.items()},
        }


@dataclass
class HouseholdChange:
    action: str
    name: str
    household_id: Optional[int] = None
    fields: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    record: Optional[HouseholdRecord] = None

    def to_dict(self) -> dict:
        return {
            'action': self.action,
            'name': self.name,
            'household_id': self.household_id,
            'fields': {k: {'old': v[0], 'new': v[1]} for k, v in self.fields.items()},
        }


@dataclass
class ImportPlan:
    """Everything that would change, worked out before anything is written."""
    member_changes: List[MemberChange] = field(default_factory=list)
    household_changes: List[HouseholdChange] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    member_report: Optional[MemberListReport] = None
    household_report: Optional[HouseholdListReport] = None

    def by_action(self, action: str) -> List[MemberChange]:
        return [c for c in self.member_changes if c.action == action]

    @property
    def counts(self) -> Dict[str, int]:
        counts = {a: len(self.by_action(a))
                  for a in (ADD, UPDATE, RENAME, LEFT_WARD, UNCHANGED)}
        counts['households'] = len(self.household_changes)
        counts['people'] = len(self.member_report.members) if self.member_report else 0
        counts['total_households'] = (
            len(self.household_report.households) if self.household_report else 0
        )
        return counts

    @property
    def changes_anything(self) -> bool:
        return any(c.action != UNCHANGED for c in self.member_changes) or \
            bool(self.household_changes)

    def to_dict(self) -> dict:
        return {
            'ok': not self.errors,
            'errors': self.errors,
            'warnings': self.warnings,
            'counts': self.counts,
            'members': [c.to_dict() for c in self.member_changes if c.action != UNCHANGED],
            'households': [c.to_dict() for c in self.household_changes],
            'print_dates': {
                'member_list': self.member_report.print_date if self.member_report else '',
                'household_list': self.household_report.print_date if self.household_report else '',
            },
            'columns': self.member_report.columns if self.member_report else [],
        }


def identify_reports(paths: List[Path]) -> Dict[str, Optional[Path]]:
    """
    Sort uploaded files into the member list and the household report.

    The user should not have to remember which slot is which, so each file is
    identified by its own columns.
    """
    found: Dict[str, List[Path]] = {'member': [], 'household': [], 'unknown': []}
    for path in paths:
        found[sniff_report_type(path)].append(path)

    errors = []
    if len(found['member']) > 1:
        errors.append("Two member lists were uploaded. One of them should be the "
                      "household report.")
    if len(found['household']) > 1:
        errors.append("Two household reports were uploaded. One of them should be "
                      "the member list.")
    for path in found['unknown']:
        errors.append(f"{path.name} does not look like a church report.")

    return {
        'member': found['member'][0] if len(found['member']) == 1 else None,
        'household': found['household'][0] if len(found['household']) == 1 else None,
        'errors': errors,
    }


def build_plan(member_pdf: Path, household_pdf: Path,
               members_db: MemberDatabase, households_db: HouseholdDatabase) -> ImportPlan:
    """Parse both reports, cross-check them, and work out every change."""
    plan = ImportPlan()

    try:
        plan.member_report = parse_member_list(Path(member_pdf))
        plan.household_report = parse_household_list(Path(household_pdf))
    except PdfToolMissing as e:
        plan.errors.append(str(e))
        return plan
    except (ValueError, OSError) as e:
        plan.errors.append(str(e))
        return plan

    plan.warnings.extend(plan.member_report.warnings)
    plan.warnings.extend(plan.household_report.warnings)

    _cross_check(plan)
    if plan.errors:
        return plan

    household_plan = _plan_households(plan, households_db, members_db)
    _plan_members(plan, members_db, household_plan)
    return plan


def _cross_check(plan: ImportPlan) -> None:
    """Confirm the two reports describe the same ward on the same day."""
    members = plan.member_report.members
    household_people = plan.household_report.all_members

    member_keys = {m.key for m in members}
    household_keys = {m.key for m in household_people}

    if len(members) != len(household_people):
        plan.errors.append(
            f"The two reports disagree: the member list has {len(members)} people "
            f"and the household report has {len(household_people)}. They were "
            f"probably printed at different times - please print both again."
        )

    missing_household = sorted(member_keys - household_keys)
    missing_member = sorted(household_keys - member_keys)

    if missing_household:
        plan.errors.append(
            f"{len(missing_household)} people are on the member list but in no "
            f"household: {_sample(missing_household)}."
        )
    if missing_member:
        plan.errors.append(
            f"{len(missing_member)} people are in a household but not on the "
            f"member list: {_sample(missing_member)}."
        )

    member_by_key = {m.key: m for m in members}
    for person in household_people:
        record = member_by_key.get(person.key)
        if record is None:
            continue
        if person.gender and record.gender and person.gender != record.gender:
            plan.warnings.append(
                f"{record.name}: the reports disagree on gender "
                f"({record.gender} vs {person.gender})."
            )
        if person.printed_age is not None:
            # As of the print date, not today - see MemberListReport.printed_on.
            computed = record.computed_age(plan.member_report.printed_on)
            if computed is not None and computed != person.printed_age:
                plan.warnings.append(
                    f"{record.name}: the reports disagree on age "
                    f"({computed} vs {person.printed_age})."
                )

    dates = (plan.member_report.print_date, plan.household_report.print_date)
    if all(dates) and dates[0] != dates[1]:
        plan.warnings.append(
            f"The reports were printed on different days ({dates[0]} and "
            f"{dates[1]}). Check they are both current."
        )


def _sample(keys: List[str], limit: int = 3) -> str:
    # Separated with semicolons: the names are "Last, First", so commas between
    # them read as more names.
    shown = '; '.join(keys[:limit])
    return shown if len(keys) <= limit else f"{shown}; and {len(keys) - limit} more"


def _plan_households(plan: ImportPlan, households_db: HouseholdDatabase,
                     members_db: MemberDatabase) -> Dict[str, dict]:
    """
    Match incoming households to existing ones and record the changes.

    Household IDs must stay stable, because members point at them. Names do not:
    "Butterfield, Chad" becomes "Butterfield, Chad & Debbie" when a spouse is
    added. Matching therefore tries, in order:

    1. the set of heads - the most stable identity;
    2. the household name;
    3. the household most of these people already belong to.

    Step 3 catches the case the first two miss: when a head changes, through a
    death or a marriage, both the head set and the name change at once. Without
    it the household is rebuilt from scratch under a new id, and anything stored
    on it with no source in the report - its email address - is silently lost.

    Returns a lookup of incoming household name -> assigned id and members.
    """
    existing_heads: Dict[frozenset, int] = {}
    for household in households_db.households:
        keys = frozenset(
            normalize_name(f"{m.last_name}, {m.first_name}")
            for m in members_db.members
            if m.household_id == household.household_id and m.household_role == HEAD
        )
        if keys:
            existing_heads[keys] = household.household_id

    existing_by_name = {
        normalize_name(h.name): h.household_id for h in households_db.households
    }

    # Where each person currently lives, for step 3.
    current_household: Dict[str, int] = {
        normalize_name(f"{m.last_name}, {m.first_name}"): m.household_id
        for m in members_db.members if m.household_id
    }

    next_id = households_db.get_next_id()
    assigned: Dict[str, dict] = {}
    claimed = set()

    for record in plan.household_report.households:
        household_id = existing_heads.get(record.head_keys)
        if household_id is None or household_id in claimed:
            candidate = existing_by_name.get(normalize_name(record.name))
            household_id = candidate if candidate not in claimed else None

        if household_id is None:
            household_id = _household_of_most_members(record, current_household, claimed)

        address = record.address
        if household_id is None:
            household_id = next_id
            next_id += 1
            plan.household_changes.append(HouseholdChange(
                action=ADD, name=record.name, household_id=household_id, record=record,
            ))
        else:
            existing = households_db.get_by_id(household_id)
            fields = {}
            if existing:
                if existing.name != record.name:
                    fields['name'] = (existing.name, record.name)
                # An absent address or phone on the report means "not printed",
                # not "deleted" - nine households in a typical report have no
                # phone and some have no address. Blanking a number entered by
                # hand because the church does not have it would be wrong, and
                # is how member phones are already treated.
                if address and existing.address != address:
                    fields['address'] = (existing.address, address)
                if record.phone and existing.phone != record.phone:
                    fields['phone'] = (existing.phone, record.phone)
            if fields:
                plan.household_changes.append(HouseholdChange(
                    action=UPDATE, name=record.name, household_id=household_id,
                    fields=fields, record=record,
                ))

        claimed.add(household_id)
        assigned[record.name] = {'household_id': household_id, 'record': record}

    return assigned


def _household_of_most_members(record: HouseholdRecord,
                               current_household: Dict[str, int],
                               claimed: set) -> Optional[int]:
    """
    The existing household that most of this one's people already belong to.

    Requires a strict majority, so two households merging does not let one
    quietly absorb the other's identity, and ignores any household already
    matched to a different incoming one.
    """
    tally: Dict[int, int] = {}
    for person in record.members:
        existing_id = current_household.get(person.key)
        if existing_id is not None and existing_id not in claimed:
            tally[existing_id] = tally.get(existing_id, 0) + 1

    if not tally:
        return None

    best_id, best_count = max(tally.items(), key=lambda kv: kv[1])
    return best_id if best_count * 2 > len(record.members) else None


def _plan_members(plan: ImportPlan, members_db: MemberDatabase,
                  household_plan: Dict[str, dict]) -> None:
    """Work out the per-member changes."""
    # Where each person lives, and what they are within that household.
    placement: Dict[str, Tuple[int, str, str]] = {}
    for name, info in household_plan.items():
        for person in info['record'].members:
            placement[person.key] = (info['household_id'], person.role, name)

    # Two members whose names normalize alike would collapse into one entry
    # here, leaving the other invisible to every import - never matched, never
    # deactivated, silently skipped. It cannot be resolved automatically, so say
    # so rather than pick one.
    existing_by_key: Dict[str, Member] = {}
    collisions: List[str] = []
    for member in members_db.members:
        key = normalize_name(f"{member.last_name}, {member.first_name}")
        if key in existing_by_key:
            collisions.append(f"{member.last_name}, {member.first_name}")
        existing_by_key[key] = member

    if collisions:
        plan.warnings.append(
            f"{len(collisions)} name(s) belong to more than one member here: "
            f"{_sample(sorted(set(collisions)))}. Only one of each can be matched "
            f"to the reports, so the others were left untouched. Give them "
            f"distinct names, or merge them, on the Members page."
        )

    incoming_keys = {m.key for m in plan.member_report.members}

    matched_ids = set()
    adds: List[MemberRecord] = []

    for record in plan.member_report.members:
        existing = existing_by_key.get(record.key)
        household_id, role, household_name = placement.get(record.key, (None, '', ''))

        if existing is None:
            adds.append(record)
            continue

        matched_ids.add(existing.member_id)
        change = _diff_member(existing, record, household_id, role)
        change.household_name = household_name
        plan.member_changes.append(change)

    # Anyone in the database but not in the reports has left the ward. Their
    # row, prayer history, notes and flags all stay; only in_ward changes, so
    # they vanish from the UI and come back intact if they return.
    departures: List[Member] = [
        m for m in members_db.members
        if m.member_id not in matched_ids
        and normalize_name(f"{m.last_name}, {m.first_name}") not in incoming_keys
        and m.in_ward
    ]

    renames = _match_renames(adds, departures)

    for record, existing in renames:
        adds.remove(record)
        departures.remove(existing)
        matched_ids.add(existing.member_id)
        household_id, role, household_name = placement.get(record.key, (None, '', ''))
        change = _diff_member(existing, record, household_id, role)
        change.action = RENAME
        change.household_name = household_name
        plan.member_changes.append(change)

    for record in adds:
        household_id, role, household_name = placement.get(record.key, (None, '', ''))
        plan.member_changes.append(MemberChange(
            action=ADD, name=record.name, record=record,
            household_name=household_name, household_id=household_id, role=role,
            fields={
                'gender': ('', record.gender),
                'birthday': ('', record.birth_date),
                'phone': ('', record.phone),
            },
        ))

    for existing in departures:
        plan.member_changes.append(MemberChange(
            action=LEFT_WARD,
            name=f"{existing.last_name}, {existing.first_name}",
            member_id=existing.member_id,
            fields={'in_ward': ('True', 'False')},
        ))


def _diff_member(existing: Member, record: MemberRecord,
                 household_id: Optional[int], role: str) -> MemberChange:
    """Compare a database row against its report row."""
    fields: Dict[str, Tuple[str, str]] = {}

    if existing.first_name != record.first_name:
        fields['first_name'] = (existing.first_name, record.first_name)
    if existing.last_name != record.last_name:
        fields['last_name'] = (existing.last_name, record.last_name)
    if record.gender and existing.gender != record.gender:
        fields['gender'] = (existing.gender, record.gender)
    if record.birth_date and existing.birthday != record.birth_date:
        fields['birthday'] = (existing.birthday, record.birth_date)
    # An absent phone on the report means "not printed", not "removed", so an
    # existing number is kept.
    if record.phone and existing.phone != record.phone:
        fields['phone'] = (existing.phone, record.phone)
    if household_id is not None and existing.household_id != household_id:
        fields['household_id'] = (str(existing.household_id or ''), str(household_id))
    if role and existing.household_role != role:
        fields['household_role'] = (existing.household_role, role)

    # Back on the ward's records after being off them. `active` is still not
    # touched: whatever the user last judged about this person stands, so
    # someone who moved away church-inactive comes back church-inactive.
    if not existing.in_ward:
        fields['in_ward'] = ('False', 'True')

    action = UPDATE if fields else UNCHANGED

    return MemberChange(
        action=action, name=record.name, member_id=existing.member_id,
        fields=fields, record=record, household_id=household_id, role=role,
    )


def _match_renames(adds: List[MemberRecord],
                   departures: List[Member]) -> List[Tuple[MemberRecord, Member]]:
    """
    Spot people whose name changed rather than people coming and going.

    A corrected spelling ("Deangelo" -> "DeAngelis") otherwise reads as one new
    member plus one departure, which would strand that person's prayer history
    on a deactivated record.

    Three things must hold: same gender and birth date, an unambiguous one-to-one
    match on that signature, and part of the name still intact. The last one
    matters - gender and birth date alone are not an identity. Without it, one
    person leaving and an unrelated person of the same gender and birthday
    arriving are fused, and the newcomer silently inherits the member id, prayer
    history, notes and flags of someone who left.
    """
    if not adds or not departures:
        return []

    def signature(gender: str, birthday: str) -> Optional[Tuple[str, str]]:
        return (gender, birthday) if gender and birthday else None

    incoming: Dict[Tuple[str, str], List[MemberRecord]] = {}
    for record in adds:
        key = signature(record.gender, record.birth_date)
        if key:
            incoming.setdefault(key, []).append(record)

    outgoing: Dict[Tuple[str, str], List[Member]] = {}
    for member in departures:
        key = signature(member.gender, member.birthday)
        if key:
            outgoing.setdefault(key, []).append(member)

    pairs = []
    for key, records in incoming.items():
        candidates = outgoing.get(key, [])
        if len(records) == 1 and len(candidates) == 1:
            if _shares_a_name(records[0], candidates[0]):
                pairs.append((records[0], candidates[0]))
    return pairs


def _shares_a_name(record: MemberRecord, member: Member) -> bool:
    """
    Whether these two could plausibly be the same person under a new name.

    A rename is a corrected spelling or a marriage, so one half of the name
    survives: "Deangelo, Moriah" -> "DeAngelis, Moriah" keeps the first name,
    "Smith, Jane" -> "Jones, Jane" keeps the first name, and a misspelt first
    name keeps the surname. Two different people sharing a birthday keep
    neither.
    """
    return (normalize_name(record.first_name) == normalize_name(member.first_name)
            or normalize_name(record.last_name) == normalize_name(member.last_name))


def commit(plan: ImportPlan, members_db: MemberDatabase,
           households_db: HouseholdDatabase) -> dict:
    """
    Apply a plan, after taking a full backup.

    An import changes members and households together, and members point at
    household ids, so the two files must not be allowed to disagree. Both are
    written to staging files and flushed to disk before either is moved into
    place, which reduces the inconsistent window to two renames with no I/O
    between them.

    A marker file is written before publishing and removed after. If the
    process dies in between, the marker survives and names the backup to
    restore - see check_interrupted_import().

    Raises ValueError if the plan has errors, so a failed cross-check can never
    be committed.
    """
    if plan.errors:
        raise ValueError("This import cannot be applied: " + "; ".join(plan.errors))

    before = backup.create(
        reason='Before PDF import',
        notes={
            'member_list_printed': plan.member_report.print_date,
            'household_list_printed': plan.household_report.print_date,
        },
    )

    # An import that cannot be undone must not run. `before` is None only on a
    # first run with no data files yet, where there is nothing to undo.
    if before is not None and not before.restorable:
        detail = (before.incomplete_reason
                  or '; '.join(before.verify_problems)
                  or 'it could not be read back')
        raise ValueError(
            f"The backup taken before this import is not usable - {detail}. "
            f"Nothing was imported, because the import could not be undone. "
            f"Check your data first (Run a check on the Import page)."
        )

    _apply_households(plan, households_db)
    _apply_members(plan, members_db)

    # Stage both files first: if writing either fails, nothing has been
    # published and the live data is still the pre-import data.
    staged = [households_db.stage(), members_db.stage()]

    marker = _marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(before.timestamp if before else '', encoding='utf-8')
    try:
        publish(staged)
    finally:
        marker.unlink(missing_ok=True)

    # A known-good restore point for the state the import just produced. Backing
    # up only beforehand would mean that damage after an import could only be
    # undone by throwing the import away.
    after = backup.create(reason='After PDF import')

    integrity = check_data.check(members_db, households_db)

    return {
        'counts': plan.counts,
        'backup': before.to_dict() if before else None,
        'backup_after': after.to_dict() if after else None,
        'warnings': plan.warnings,
        'integrity': integrity.to_dict(),
    }


def _marker_path() -> Path:
    return config.DATA_DIR / '.import-in-progress'


def check_interrupted_import() -> Optional[str]:
    """
    Report an import that was interrupted while writing.

    The marker only exists during the two renames at the end of a commit, so if
    it is still there at startup the data files may disagree with each other.
    Returns a message naming the backup to restore, or None.
    """
    marker = _marker_path()
    if not marker.exists():
        return None

    try:
        timestamp = marker.read_text(encoding='utf-8').strip()
    except OSError:
        timestamp = ''

    snapshot = backup.get(timestamp) if timestamp else None
    if snapshot:
        return (f"An import was interrupted while saving, so members and "
                f"households may not match. Restore the backup from "
                f"{snapshot.label} to undo it.")
    return ("An import was interrupted while saving, so members and households "
            "may not match. Restore a backup, then run the import again.")


def clear_interrupted_import() -> None:
    """Forget an interrupted import, once it has been dealt with."""
    _marker_path().unlink(missing_ok=True)


def _apply_households(plan: ImportPlan, households_db: HouseholdDatabase) -> None:
    for change in plan.household_changes:
        if change.action == ADD:
            households_db.households.append(Household(
                household_id=change.household_id,
                name=change.record.name,
                address=change.record.address,
                phone=change.record.phone,
                email='',
            ))
        else:
            household = households_db.get_by_id(change.household_id)
            if household is None:
                continue
            household.name = change.record.name
            # Only overwrite what the report actually carries - see the matching
            # comment in _plan_households. email has no source in the report at
            # all, so it is never touched.
            if change.record.address:
                household.address = change.record.address
            if change.record.phone:
                household.phone = change.record.phone


def _apply_members(plan: ImportPlan, members_db: MemberDatabase) -> None:
    next_id = max((m.member_id for m in members_db.members), default=0) + 1

    for change in plan.member_changes:
        if change.action == ADD:
            record = change.record
            members_db.members.append(Member(
                member_id=next_id,
                first_name=record.first_name,
                last_name=record.last_name,
                gender=record.gender,
                phone=record.phone,
                birthday=record.birth_date,
                recommend_expiration='',
                # A brand new member is on the records and presumed worth
                # scheduling until the user says otherwise.
                in_ward=True,
                active=True,
                household_id=change.household_id,
                household_role=change.role,
            ))
            next_id += 1
            continue

        member = members_db.get_by_id(change.member_id)
        if member is None:
            continue

        if change.action == LEFT_WARD:
            # Off the records, so out of the UI - but `active` is the user's
            # own judgement and is left exactly as they set it, so moving back
            # in later restores them unchanged.
            member.in_ward = False
            continue

        record = change.record
        if record is not None:
            member.first_name = record.first_name
            member.last_name = record.last_name
            if record.gender:
                member.gender = record.gender
            if record.birth_date:
                member.birthday = record.birth_date
            if record.phone:
                member.phone = record.phone

        if change.household_id is not None:
            member.household_id = change.household_id
        if change.role:
            member.household_role = change.role
        # Present in the reports, so on the records - whatever they were before.
        member.in_ward = True


def run_cli(member_pdf: Path, household_pdf: Path, apply_changes: bool) -> int:
    members_db = MemberDatabase()
    households_db = HouseholdDatabase()
    plan = build_plan(member_pdf, household_pdf, members_db, households_db)

    for error in plan.errors:
        print(f"ERROR: {error}")
    for warning in plan.warnings:
        print(f"warning: {warning}")
    if plan.errors:
        return 1

    counts = plan.counts
    print(f"{counts['people']} people, {counts['total_households']} households")
    print(f"  add {counts[ADD]}, update {counts[UPDATE]}, rename {counts[RENAME]}, "
          f"left ward {counts[LEFT_WARD]}, unchanged {counts[UNCHANGED]}")

    if not apply_changes:
        print("(dry run - nothing written; pass --apply to import)")
        return 0

    result = commit(plan, members_db, households_db)
    snapshot = result['backup']
    print(f"Imported. Backup: {snapshot['timestamp'] if snapshot else 'none needed'}")
    return 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Import members from church PDF reports')
    parser.add_argument('pdfs', nargs=2, help='the member list and household report, in any order')
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    args = parser.parse_args()

    identified = identify_reports([Path(p) for p in args.pdfs])
    if identified['errors']:
        for message in identified['errors']:
            print(f"ERROR: {message}")
        sys.exit(1)
    if not identified['member'] or not identified['household']:
        print("ERROR: both the member list and the household report are needed.")
        sys.exit(1)

    sys.exit(run_cli(identified['member'], identified['household'], args.apply))
