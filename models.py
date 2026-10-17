"""
Data models for MLS3
Handles CSV-based data persistence for members and prayer assignments
"""
import csv
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

import config


class DataIntegrityError(Exception):
    """
    A data file is damaged and was not loaded.

    Raised instead of quietly loading part of a file. Half a ward looks normal
    on screen, which is far worse than a clear failure: the app can offer to
    restore a backup, but it cannot notice that 180 people are missing.
    """


# ---------------------------------------------------------------------------
# Durable writes
#
# Every data file is written to a temporary file in the same directory, flushed
# all the way to disk, and then moved into place with os.replace, which is
# atomic on POSIX. A process killed at any point leaves either the complete old
# file or the complete new one - never a half-written one.
#
# This matters because MLS3 runs in Termux: Android kills background processes
# whenever it wants, and a plain open(path, 'w') is destructive from the moment
# it truncates until the last byte lands. The same mechanism also survives a
# full disk, since the failure happens while writing the temporary file and the
# original is left untouched.
# ---------------------------------------------------------------------------

def _fsync_dir(directory: Path) -> None:
    """Flush a directory entry so a rename survives power loss."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass            # some filesystems do not allow this; the rename still holds
    finally:
        os.close(fd)


def _staged_path(path: Path) -> Path:
    return path.with_name(path.name + '.tmp')


@contextmanager
def staged_write(path: Path, newline: str = '', encoding: str = 'utf-8'):
    """
    Write a file's new contents to disk without publishing them yet.

    Yields the open file. On a clean exit the data is fully flushed to the
    staging file and the staging path is left for publish() to move into place.
    On any exception the staging file is removed.

    Used when several files have to change together - see publish().
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = _staged_path(path)

    handle = open(staged, 'w', newline=newline, encoding=encoding)
    try:
        yield handle
        handle.flush()
        os.fsync(handle.fileno())
    except BaseException:
        handle.close()
        staged.unlink(missing_ok=True)
        raise
    else:
        handle.close()


def publish(staged: List[Tuple[Path, Path]]) -> None:
    """
    Move staged files into place, back to back.

    Two renames cannot be one atomic operation, but each is atomic on its own
    and the gap between them is microseconds with no I/O in it, which is as
    close to a multi-file commit as a CSV store gets.
    """
    for staged_path, final_path in staged:
        os.replace(staged_path, final_path)
    for _, final_path in staged:
        _fsync_dir(final_path.parent)


@contextmanager
def atomic_write(path: Path, newline: str = '', encoding: str = 'utf-8'):
    """Write one file durably: staged, flushed, then moved into place."""
    path = Path(path)
    with staged_write(path, newline=newline, encoding=encoding) as handle:
        yield handle
    publish([(_staged_path(path), path)])


def _require_complete_file(path: Path) -> None:
    """
    Refuse a file whose last row was cut off.

    Every row the csv writer produces ends with a line terminator, so a file
    that does not end with one stopped partway through being written or copied.
    Atomic writes make this impossible for MLS3's own saves; this catches a bad
    copy, failing storage, or an interrupted manual edit.

    Truncation exactly on a row boundary cannot be detected this way - that is
    what the count comparison in utils/check_data.py is for.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size == 0:
        raise DataIntegrityError(
            f"{path.name} is empty. Restore a backup."
        )
    with open(path, 'rb') as f:
        f.seek(-1, os.SEEK_END)
        if f.read(1) not in (b'\n', b'\r'):
            raise DataIntegrityError(
                f"{path.name} ends in the middle of a row, so it was cut off "
                f"while being written or copied. Restore a backup rather than "
                f"using it."
            )


def _require_columns(path: Path, reader: csv.DictReader, required: List[str]) -> None:
    """Refuse a file whose header is missing columns we depend on."""
    present = set(reader.fieldnames or [])
    missing = [name for name in required if name not in present]
    if missing:
        raise DataIntegrityError(
            f"{path.name} is missing the column(s) {', '.join(missing)}. "
            f"The file looks damaged or is from a different program. "
            f"Restore a backup rather than importing over it."
        )


def _int_field(path: Path, row: dict, column: str, line: int) -> int:
    """Read an integer column, naming the file and line when it is unreadable."""
    raw = (row.get(column) or '').strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise DataIntegrityError(
            f"{path.name} line {line}: {column} should be a number but is "
            f"{raw!r}. The file is probably truncated or damaged - restore a backup."
        )


def _check_unique(path: Path, ids: List[int], column: str) -> None:
    seen, duplicates = set(), []
    for value in ids:
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        shown = ', '.join(str(d) for d in sorted(set(duplicates))[:5])
        raise DataIntegrityError(
            f"{path.name} has more than one row with the same {column} "
            f"({shown}). Restore a backup."
        )


@dataclass
class Member:
    """Represents a church member"""
    member_id: int
    first_name: str
    last_name: str
    gender: str  # M or F
    phone: str
    birthday: str
    recommend_expiration: str
    last_prayer_date: Optional[str] = None
    dont_ask_prayer: bool = False
    active: bool = True
    notes: str = ""
    skip_until: Optional[str] = None  # Date to skip member until (YYYY-MM-DD)
    flag: str = ""  # Color flags: comma-separated list like 'red,yellow,blue' or empty
    aka: str = ""  # Also known as / preferred name (e.g., "Mike" instead of "Michael")
    household_id: Optional[int] = None  # Links member to household
    household_role: str = ""  # 'head' or 'dependent' within the household
    # Two separate facts, deliberately kept apart:
    #   in_ward - owned by the import. Are they on the ward's records at all?
    #             Someone who moves away is in_ward=False and disappears from
    #             the UI entirely; nothing in the app shows them.
    #   active  - owned by the user, set from the Members page. Are they
    #             church-active and worth scheduling? An import never writes it.
    # Conflating the two meant moving out of the ward and back in silently
    # undid the user's own judgement about someone.
    in_ward: bool = True

    @property
    def full_name(self):
        """Returns full name using AKA if set, otherwise first_name"""
        display_first = self.aka if self.aka else self.first_name
        return f"{display_first} {self.last_name}"

    @property
    def display_name(self):
        """Returns the name to display for messages (first word of AKA or first name)"""
        name = self.aka if self.aka else self.first_name
        # Return only the first word (handles cases like "John Paul" -> "John")
        return name.split()[0] if name else ""

    @property
    def display_name_with_last(self):
        """Returns first word of first name/AKA plus last name (for event lists)"""
        first = self.display_name
        return f"{first} {self.last_name}" if first else self.last_name

    @property
    def flags_list(self) -> List[str]:
        """Returns list of flags set for this member"""
        if not self.flag:
            return []
        return [f.strip() for f in self.flag.split(',') if f.strip()]

    def has_flag(self, flag_color: str) -> bool:
        """Check if member has a specific flag"""
        return flag_color in self.flags_list

    def toggle_flag(self, flag_color: str):
        """Toggle a specific flag on/off"""
        flags = set(self.flags_list)
        if flag_color in flags:
            flags.remove(flag_color)
        else:
            flags.add(flag_color)
        # Store in consistent order: blue, yellow, red
        ordered = []
        for color in ['blue', 'yellow', 'red']:
            if color in flags:
                ordered.append(color)
        self.flag = ','.join(ordered) if ordered else ''

    @property
    def last_prayer_date_obj(self) -> Optional[date]:
        """Returns last_prayer_date as a date object, or None"""
        if self.last_prayer_date:
            return datetime.strptime(self.last_prayer_date, config.DATE_FORMAT).date()
        return None

    @property
    def skip_until_obj(self) -> Optional[date]:
        """Returns skip_until as a date object, or None"""
        if self.skip_until:
            return datetime.strptime(self.skip_until, config.DATE_FORMAT).date()
        return None

    @property
    def age(self) -> Optional[int]:
        """Calculate age from birthday"""
        if not self.birthday:
            return None
        try:
            birth_date = datetime.strptime(self.birthday, '%Y-%m-%d').date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return age
        except ValueError:
            return None

    @property
    def is_minor(self) -> bool:
        """Check if member is under 18 based on birthday"""
        age = self.age
        return age is not None and age < 18

    @property
    def is_prayer_eligible(self) -> bool:
        """Check if member is eligible to pray in sacrament meeting (8 years or older)"""
        age = self.age
        if age is None:
            # If no birthday, assume eligible
            return True
        return age >= 8


@dataclass
class PrayerAssignment:
    """Represents a prayer assignment"""
    assignment_id: int
    member_id: int
    date: str
    prayer_type: str  # Opening, Closing, or Undecided
    state: str  # Draft, Invited, Accepted, Reminded, Completed
    created_date: str
    last_updated: str
    completed_date: Optional[str] = None

    @property
    def date_obj(self) -> date:
        """Returns date as a date object"""
        return datetime.strptime(self.date, config.DATE_FORMAT).date()


@dataclass
class AppointmentType:
    """Represents an appointment type configuration"""
    name: str
    default_duration: int
    default_conductor: str


@dataclass
class Appointment:
    """Represents an appointment"""
    appointment_id: int
    member_id: int
    appointment_type: str
    datetime_utc: str  # ISO 8601 UTC format: "2026-02-08T18:00:00Z"
    duration_minutes: int
    conductor: str  # Bishop or Counselor
    state: str  # Draft, Invited, Reminded, Completed, Cancelled
    created_date: str
    last_updated: str
    completed_date: Optional[str] = None
    google_event_id: Optional[str] = None  # Google Calendar event ID for sync
    notes: Optional[str] = None  # Optional notes (location, calling info, etc.)
    # For the heads of member_id's household rather than member_id alone.
    # The heads are looked up when needed, so they follow a re-import.
    household: bool = False

    @property
    def datetime_obj_utc(self) -> datetime:
        """Returns appointment datetime as timezone-aware UTC datetime"""
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        # Parse ISO 8601 UTC format
        dt = datetime.strptime(self.datetime_utc, '%Y-%m-%dT%H:%M:%SZ')
        return dt.replace(tzinfo=ZoneInfo('UTC'))

    def datetime_local(self, timezone: str) -> datetime:
        """
        Returns appointment datetime in specified timezone

        Args:
            timezone: IANA timezone string (e.g., 'America/Denver', 'America/New_York')
        """
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        utc_dt = self.datetime_obj_utc
        local_tz = ZoneInfo(timezone)
        return utc_dt.astimezone(local_tz)

    def time_local(self, timezone: str) -> str:
        """
        Returns time string in 12-hour format for specified timezone

        Args:
            timezone: IANA timezone string (e.g., 'America/Denver')

        Returns:
            Time string like "11:00 AM"
        """
        local_dt = self.datetime_local(timezone)
        return local_dt.strftime('%I:%M %p')

    @property
    def date_obj(self) -> date:
        """Returns date as a date object (in UTC)"""
        return self.datetime_obj_utc.date()

    @property
    def date(self) -> str:
        """Returns date string (for backward compatibility)"""
        return self.date_obj.strftime(config.DATE_FORMAT)

    @property
    def time(self) -> str:
        """Returns time string in 24-hour format (for backward compatibility) - UTC time"""
        return self.datetime_obj_utc.strftime('%H:%M')

    @property
    def datetime_obj(self) -> datetime:
        """Returns datetime object (for backward compatibility) - timezone-naive UTC"""
        return self.datetime_obj_utc.replace(tzinfo=None)

    def date_local(self, timezone: str) -> str:
        """Returns date string in local timezone (YYYY-MM-DD format)"""
        local_dt = self.datetime_local(timezone)
        return local_dt.strftime(config.DATE_FORMAT)


@dataclass
class Household:
    """Represents a household (family unit)"""
    household_id: int
    name: str  # e.g., "Smith, Jack & Jill"
    address: str  # Multi-line address
    # No phone or email here on purpose. Contact details live on the member -
    # messages go to a person, and the heads' own numbers are what SMS uses -
    # so a second copy on the household was only ever displayed, and was one
    # more thing an import could overwrite or blank.


class HouseholdDatabase:
    """Manages household data from CSV"""

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.HOUSEHOLDS_CSV
        self.households: List[Household] = []
        # Flask serves requests on threads, so two handlers can save at once.
        self._lock = threading.Lock()
        self.load()

    FIELDNAMES = ['household_id', 'name', 'address']

    def load(self):
        """Load households from CSV, refusing a damaged file."""
        self.households = []

        if not self.csv_path.exists():
            # File doesn't exist yet - this is OK, we'll create it on save
            return

        _require_complete_file(self.csv_path)

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            _require_columns(self.csv_path, reader, ['household_id', 'name'])
            for line, row in enumerate(reader, start=2):
                # phone and email columns may still be present in an older
                # file; they are simply not read, and drop out on the next save.
                self.households.append(Household(
                    household_id=_int_field(self.csv_path, row, 'household_id', line),
                    name=row.get('name') or '',
                    address=row.get('address') or ''
                ))

        _check_unique(self.csv_path,
                      [h.household_id for h in self.households], 'household_id')

    def _write_rows(self, handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
        writer.writeheader()
        for household in self.households:
            writer.writerow(asdict(household))

    def save(self):
        """Save households durably."""
        with self._lock:
            with atomic_write(self.csv_path) as f:
                self._write_rows(f)

    def stage(self) -> Tuple[Path, Path]:
        """
        Write the new contents without publishing them.

        Returns (staged path, final path) for publish(), so households and
        members can be committed together.
        """
        with self._lock:
            with staged_write(self.csv_path) as f:
                self._write_rows(f)
        return _staged_path(self.csv_path), self.csv_path

    def get_by_id(self, household_id: int) -> Optional[Household]:
        """Get household by ID"""
        for household in self.households:
            if household.household_id == household_id:
                return household
        return None

    def add(self, household: Household):
        """Add a new household"""
        self.households.append(household)
        self.save()

    def update(self, household_id: int, **kwargs):
        """Update household fields"""
        household = self.get_by_id(household_id)
        if household:
            for key, value in kwargs.items():
                if hasattr(household, key):
                    setattr(household, key, value)
            self.save()

    def get_next_id(self) -> int:
        """Get next available household ID"""
        if not self.households:
            return 1
        return max(h.household_id for h in self.households) + 1


class MemberDatabase:
    """Manages member data from CSV"""

    FIELDNAMES = [
        'member_id', 'first_name', 'last_name', 'gender', 'phone',
        'birthday', 'recommend_expiration', 'last_prayer_date',
        'dont_ask_prayer', 'active', 'notes', 'skip_until', 'flag', 'aka',
        'household_id', 'household_role', 'in_ward'
    ]

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.MEMBERS_CSV
        self.members: List[Member] = []
        self._lock = threading.Lock()
        self.load()

    def load(self):
        """Load members from CSV file"""
        self.members = []

        if not self.csv_path.exists():
            # File doesn't exist yet - this is OK, we'll create it on save
            return

        _require_complete_file(self.csv_path)

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            _require_columns(self.csv_path, reader,
                             ['member_id', 'first_name', 'last_name'])
            for line, row in enumerate(reader, start=2):
                # Parse household_id if present
                household_id = None
                if row.get('household_id') and row['household_id']:
                    try:
                        household_id = int(row['household_id'])
                    except ValueError:
                        household_id = None

                # Columns are read with .get so a file written by an older
                # version, or one missing an optional column, still loads. The
                # columns we cannot do without are checked above.
                member = Member(
                    member_id=_int_field(self.csv_path, row, 'member_id', line),
                    first_name=row.get('first_name') or '',
                    last_name=row.get('last_name') or '',
                    gender=row.get('gender') or '',
                    phone=row.get('phone') or '',
                    birthday=row.get('birthday') or '',
                    recommend_expiration=row.get('recommend_expiration') or '',
                    last_prayer_date=row.get('last_prayer_date') or None,
                    dont_ask_prayer=(row.get('dont_ask_prayer') or '').lower() == 'true',
                    active=(row.get('active') or 'true').lower() == 'true',
                    notes=row.get('notes') or '',
                    skip_until=row.get('skip_until') or None,
                    flag=row.get('flag') or '',
                    aka=row.get('aka') or '',
                    household_id=household_id,
                    household_role=row.get('household_role') or '',
                    # Defaults to True so a database written before this
                    # column existed stays fully visible; the next import
                    # sets it authoritatively.
                    in_ward=(row.get('in_ward') or 'true').lower() == 'true'
                )
                self.members.append(member)

        _check_unique(self.csv_path, [m.member_id for m in self.members], 'member_id')

    def _write_rows(self, handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
        writer.writeheader()
        for member in self.members:
            writer.writerow(asdict(member))

    def save(self):
        """Save members durably."""
        with self._lock:
            with atomic_write(self.csv_path) as f:
                self._write_rows(f)

    def stage(self) -> Tuple[Path, Path]:
        """Write the new contents without publishing them. See publish()."""
        with self._lock:
            with staged_write(self.csv_path) as f:
                self._write_rows(f)
        return _staged_path(self.csv_path), self.csv_path

    def get_by_id(self, member_id: int) -> Optional[Member]:
        """Get member by ID"""
        for member in self.members:
            if member.member_id == member_id:
                return member
        return None

    def get_active_members(self, gender: Optional[str] = None, prayer_eligible_only: bool = False) -> List[Member]:
        """
        Get all active members, optionally filtered by gender and prayer eligibility.

        Args:
            gender: Optional gender filter ('M' or 'F')
            prayer_eligible_only: If True, only return members 8 years or older

        Returns:
            List of active members matching the filters
        """
        # Both facts matter here: someone who has left the ward cannot be
        # asked, and someone church-inactive should not be asked.
        result = [m for m in self.members if m.in_ward and m.active]
        if gender:
            result = [m for m in result if m.gender == gender]
        if prayer_eligible_only:
            result = [m for m in result if m.is_prayer_eligible]
        return result

    def search(self, query: str) -> List[Member]:
        """Fuzzy search for members by name"""
        query = query.lower()
        results = []

        for member in self.members:
            if member.in_ward and member.active:
                full_name = member.full_name.lower()
                if query in full_name:
                    results.append(member)

        return results

    def update_last_prayer_date(self, member_id: int, prayer_date: date):
        """Update a member's last prayer date"""
        member = self.get_by_id(member_id)
        if member:
            member.last_prayer_date = prayer_date.strftime(config.DATE_FORMAT)
            self.save()

    def update_member(self, member_id: int, **kwargs):
        """Update member fields"""
        member = self.get_by_id(member_id)
        if member:
            for key, value in kwargs.items():
                if hasattr(member, key):
                    setattr(member, key, value)
            self.save()

    def get_last_prayer_date(self, member_id: int, assignments_db) -> Optional[str]:
        """
        Get member's last prayer date from the members database.

        This returns the stored last_prayer_date field, which is maintained
        by the system when prayers are marked as completed.

        Args:
            member_id: Member ID to look up
            assignments_db: Unused (kept for compatibility)

        Returns:
            Date string in YYYY-MM-DD format, or None if never prayed
        """
        member = self.get_by_id(member_id)
        if not member:
            return None

        return member.last_prayer_date

    def get_parents(self, member_id: int, households_db=None) -> List['Member']:
        """
        Get parent(s) for a member: the heads of their household.

        The church household report marks heads of household explicitly, and the
        PDF import stores that in Member.household_role. That is used whenever
        it is available.

        Falls back to parsing household.name for members imported before
        household_role existed. The fallback is weaker on two counts: it matches
        people by first-name string, so it misses a head whose surname differs
        from the household name, and it uses age 18 as a stand-in for
        parenthood, which does not hold - adult children commonly live at home.

        Args:
            member_id: ID of the member
            households_db: HouseholdDatabase, required only for the fallback

        Returns:
            List of parent Member objects (empty if household data unavailable)
        """
        member = self.get_by_id(member_id)
        if not member or not member.household_id:
            return []

        return [h for h in self.get_heads(member.household_id, households_db)
                if h.member_id != member_id]

    def get_heads(self, household_id: int, households_db=None) -> List['Member']:
        """
        Get the heads of a household - the parents, or the couple.

        Uses Member.household_role when the household has it, otherwise falls
        back to the household name; see get_parents() for the trade-offs.

        Args:
            household_id: ID of the household
            households_db: HouseholdDatabase, required only for the fallback

        Returns:
            List of head Member objects (empty if household data unavailable)
        """
        if not household_id:
            return []

        # Filtered on in_ward, not active: whether a parent attends church has
        # nothing to do with whether they are the person to contact about their
        # child. Only having left the ward removes them.
        household_members = [
            m for m in self.members
            if m.household_id == household_id and m.in_ward
        ]

        heads = [m for m in household_members if m.household_role == 'head']
        if heads:
            return heads

        # This household predates household_role - fall back to the household
        # name. Only do so when nobody in the household has a role, otherwise
        # an absent role is a genuine "not a head".
        if any(m.household_role for m in household_members):
            return []

        if not households_db:
            return []

        household = households_db.get_by_id(household_id)
        if not household or not household.name:
            return []

        parent_first_names = self._parse_parent_names(household.name)
        if not parent_first_names:
            return []

        return [
            m for m in household_members
            if not m.is_minor and m.first_name in parent_first_names
        ]

    def _parse_parent_names(self, household_name: str) -> set:
        """
        Parse parent first names from household name string.

        Args:
            household_name: e.g., "Smith, Jack & Jill" or "Smith, Jack"

        Returns:
            Set of parent first names, e.g., {"Jack", "Jill"}
        """
        if not household_name or ',' not in household_name:
            return set()

        # Split on comma: ["Smith", " Jack & Jill"]
        parts = household_name.split(',', 1)
        if len(parts) < 2:
            return set()

        # Get the names part: " Jack & Jill"
        names_part = parts[1].strip()

        # Split on & or 'and' to get individual names
        if '&' in names_part:
            names = [n.strip() for n in names_part.split('&')]
        elif ' and ' in names_part.lower():
            names = [n.strip() for n in names_part.split(' and ')]
        else:
            names = [names_part]

        return set(names)

    def get_household_members(self, household_id: int) -> List['Member']:
        """
        Get all members in a household.

        Args:
            household_id: ID of the household

        Returns:
            List of Member objects in the household
        """
        return [m for m in self.members
                if m.household_id == household_id and m.in_ward]

    def get_children(self, member_id: int) -> List['Member']:
        """
        Get children for a member (minors in same household).

        Args:
            member_id: ID of the member

        Returns:
            List of child Member objects (may be empty if no children found)
        """
        member = self.get_by_id(member_id)
        if not member or not member.household_id:
            return []

        # Filtered on in_ward, not active, for the same reason as get_parents:
        # a child's church attendance does not change whose child they are.
        children = []
        for m in self.members:
            if (m.household_id == member.household_id and
                m.member_id != member_id and
                m.is_minor and
                m.in_ward):
                children.append(m)

        return children


class PrayerAssignmentDatabase:
    """Manages prayer assignment data from CSV"""

    FIELDNAMES = [
        'assignment_id', 'member_id', 'date', 'prayer_type', 'state',
        'created_date', 'last_updated', 'completed_date'
    ]

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.PRAYER_ASSIGNMENTS_CSV
        self.assignments: List[PrayerAssignment] = []
        self._lock = threading.Lock()
        self.load()

    def load(self):
        """Load assignments from CSV, refusing a damaged file."""
        self.assignments = []

        if not self.csv_path.exists():
            print(f"Warning: Prayer assignments CSV not found at {self.csv_path}")
            return

        _require_complete_file(self.csv_path)

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            _require_columns(self.csv_path, reader, ['assignment_id', 'member_id'])
            for line, row in enumerate(reader, start=2):
                self.assignments.append(PrayerAssignment(
                    assignment_id=_int_field(self.csv_path, row, 'assignment_id', line),
                    member_id=_int_field(self.csv_path, row, 'member_id', line),
                    date=row.get('date') or '',
                    prayer_type=row.get('prayer_type') or '',
                    state=row.get('state') or '',
                    created_date=row.get('created_date') or '',
                    last_updated=row.get('last_updated') or '',
                    completed_date=row.get('completed_date') or None
                ))

        _check_unique(self.csv_path,
                      [a.assignment_id for a in self.assignments], 'assignment_id')

    def _write_rows(self, handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
        writer.writeheader()
        for assignment in self.assignments:
            writer.writerow(asdict(assignment))

    def save(self):
        """Save assignments durably."""
        with self._lock:
            with atomic_write(self.csv_path) as f:
                self._write_rows(f)

    def stage(self) -> Tuple[Path, Path]:
        """Write the new contents without publishing them. See publish()."""
        with self._lock:
            with staged_write(self.csv_path) as f:
                self._write_rows(f)
        return _staged_path(self.csv_path), self.csv_path

    def get_by_id(self, assignment_id: int) -> Optional[PrayerAssignment]:
        """Get assignment by ID"""
        for assignment in self.assignments:
            if assignment.assignment_id == assignment_id:
                return assignment
        return None

    def get_next_id(self) -> int:
        """Get next available assignment ID"""
        if not self.assignments:
            return 1
        return max(a.assignment_id for a in self.assignments) + 1

    def get_active_assignments(self) -> List[PrayerAssignment]:
        """Get all non-completed assignments"""
        return [a for a in self.assignments if a.state != 'Completed']

    def get_assignments_for_date(self, target_date: date) -> List[PrayerAssignment]:
        """Get all assignments for a specific date"""
        date_str = target_date.strftime(config.DATE_FORMAT)
        return [a for a in self.assignments if a.date == date_str]

    def get_assigned_member_ids(self) -> List[int]:
        """Get list of member IDs with active assignments"""
        return [a.member_id for a in self.get_active_assignments()]

    def create_assignment(
        self,
        member_id: Optional[int],
        date: date,
        prayer_type: str = "Undecided"
    ) -> PrayerAssignment:
        """Create a new prayer assignment"""
        now = datetime.now().strftime(config.DATE_FORMAT)
        assignment = PrayerAssignment(
            assignment_id=self.get_next_id(),
            member_id=member_id or 0,  # 0 = no member selected yet
            date=date.strftime(config.DATE_FORMAT),
            prayer_type=prayer_type,
            state="Draft",
            created_date=now,
            last_updated=now
        )
        self.assignments.append(assignment)
        self.save()
        return assignment

    def update_state(self, assignment_id: int, new_state: str):
        """Update assignment state"""
        assignment = self.get_by_id(assignment_id)
        if assignment:
            assignment.state = new_state
            assignment.last_updated = datetime.now().strftime(config.DATE_FORMAT)

            if new_state == "Completed":
                assignment.completed_date = datetime.now().strftime(config.DATE_FORMAT)

            self.save()

    def update_assignment(
        self,
        assignment_id: int,
        member_id: Optional[int] = None,
        prayer_type: Optional[str] = None,
        date: Optional[date] = None
    ):
        """Update assignment details"""
        assignment = self.get_by_id(assignment_id)
        if assignment:
            if member_id is not None:
                assignment.member_id = member_id
            if prayer_type is not None:
                assignment.prayer_type = prayer_type
            if date is not None:
                assignment.date = date.strftime(config.DATE_FORMAT)

            assignment.last_updated = datetime.now().strftime(config.DATE_FORMAT)
            self.save()


class MessageTemplates:
    """Manages message templates from YAML"""

    def __init__(self, yaml_path: Path = None):
        self.yaml_path = yaml_path or config.MESSAGE_TEMPLATES_YAML
        self.templates = {}
        self.pleasantries = {}
        self.load()

    def load(self):
        """Load templates from YAML file"""
        if not self.yaml_path.exists():
            print(f"Warning: Message templates YAML not found at {self.yaml_path}")
            return

        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

            # Extract pleasantries section
            self.pleasantries = data.get('pleasantries', {})

            # Load templates (exclude pleasantries)
            self.templates = {k: v for k, v in data.items() if k != 'pleasantries'}

    def get_template(self, activity: str, template_name: str) -> str:
        """Get a specific template"""
        return self.templates.get(activity, {}).get(template_name, "")

    def expand_template(self, activity: str, template_name: str, **kwargs) -> str:
        """Get template and expand variables (LEGACY - simple expansion only)"""
        template = self.get_template(activity, template_name)
        return template.format(**kwargs)

    def expand_smart(self, activity: str, template_name: str, member, appointment=None, **kwargs) -> str:
        """
        Get template and expand with smart variables.

        Args:
            activity: Template category (prayer, appointments, adhoc)
            template_name: Template name within category
            member: Member object
            appointment: Optional appointment/assignment object
            **kwargs: Additional simple variables

        Returns:
            Fully expanded message string
        """
        from utils.template_expander import SmartTemplateExpander

        template = self.get_template(activity, template_name)
        expander = SmartTemplateExpander(self)
        return expander.expand(template, member, appointment, **kwargs)


class AppointmentTypesDatabase:
    """Manages appointment types from YAML"""

    def __init__(self, yaml_path: Path = None):
        self.yaml_path = yaml_path or config.APPOINTMENT_TYPES_YAML
        self.types: List[AppointmentType] = []
        self.load()

    def load(self):
        """Load appointment types from YAML file"""
        if not self.yaml_path.exists():
            print(f"Warning: Appointment types YAML not found at {self.yaml_path}")
            return

        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            for item in data.get('appointment_types', []):
                self.types.append(AppointmentType(
                    name=item['name'],
                    default_duration=item['default_duration'],
                    default_conductor=item['default_conductor']
                ))

    def get_all(self) -> List[AppointmentType]:
        """Get all appointment types"""
        return self.types

    def get_by_name(self, name: str) -> Optional[AppointmentType]:
        """Get appointment type by name"""
        for t in self.types:
            if t.name == name:
                return t
        return None


class AppointmentDatabase:
    """Manages appointment data from CSV"""

    FIELDNAMES = [
        'appointment_id', 'member_id', 'appointment_type', 'datetime_utc',
        'duration_minutes', 'conductor', 'state', 'created_date',
        'last_updated', 'completed_date', 'google_event_id', 'notes',
        'household'
    ]

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.APPOINTMENTS_CSV
        self.appointments: List[Appointment] = []
        self._lock = threading.Lock()
        self.load()

    def load(self):
        """Load appointments from CSV, refusing a damaged file."""
        self.appointments = []

        if not self.csv_path.exists():
            print(f"Warning: Appointments CSV not found at {self.csv_path}")
            return

        _require_complete_file(self.csv_path)

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            _require_columns(self.csv_path, reader,
                             ['appointment_id', 'member_id', 'datetime_utc'])
            for line, row in enumerate(reader, start=2):
                self.appointments.append(Appointment(
                    appointment_id=_int_field(self.csv_path, row, 'appointment_id', line),
                    member_id=_int_field(self.csv_path, row, 'member_id', line),
                    appointment_type=row.get('appointment_type') or '',
                    datetime_utc=row.get('datetime_utc') or '',
                    duration_minutes=_int_field(self.csv_path, row, 'duration_minutes', line),
                    conductor=row.get('conductor') or '',
                    state=row.get('state') or '',
                    created_date=row.get('created_date') or '',
                    last_updated=row.get('last_updated') or '',
                    completed_date=row.get('completed_date') or None,
                    google_event_id=row.get('google_event_id') or None,
                    notes=row.get('notes') or None,
                    household=(row.get('household') or '').lower() == 'true'
                ))

        _check_unique(self.csv_path,
                      [a.appointment_id for a in self.appointments], 'appointment_id')

    def _write_rows(self, handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
        writer.writeheader()
        for appointment in self.appointments:
            writer.writerow(asdict(appointment))

    def save(self):
        """Save appointments durably."""
        with self._lock:
            with atomic_write(self.csv_path) as f:
                self._write_rows(f)

    def stage(self) -> Tuple[Path, Path]:
        """Write the new contents without publishing them. See publish()."""
        with self._lock:
            with staged_write(self.csv_path) as f:
                self._write_rows(f)
        return _staged_path(self.csv_path), self.csv_path

    def get_by_id(self, appointment_id: int) -> Optional[Appointment]:
        """Get appointment by ID"""
        for appointment in self.appointments:
            if appointment.appointment_id == appointment_id:
                return appointment
        return None

    def get_next_id(self) -> int:
        """Get next available appointment ID"""
        if not self.appointments:
            return 1
        return max(a.appointment_id for a in self.appointments) + 1

    def get_active_appointments(self) -> List[Appointment]:
        """Get all non-completed/non-cancelled appointments"""
        return [a for a in self.appointments if a.state not in ['Completed', 'Cancelled']]

    def get_appointments_for_member(self, member_id: int, members_db=None,
                                    households_db=None) -> List[Appointment]:
        """
        Get all appointments for a specific member.

        With members_db, this includes household appointments the member is a
        head of, so a couple's appointment shows up for both of them.
        """
        result = []
        for a in self.appointments:
            if a.member_id == member_id:
                result.append(a)
            elif a.household and members_db:
                picked = members_db.get_by_id(a.member_id)
                if picked and any(h.member_id == member_id for h in
                                  members_db.get_heads(picked.household_id, households_db)):
                    result.append(a)
        return result

    def create_appointment(
        self,
        member_id: int,
        appointment_type: str,
        date: date,
        time: str,
        duration_minutes: int,
        conductor: str,
        timezone: str = None,
        notes: str = None,
        household: bool = False
    ) -> Appointment:
        """
        Create a new appointment

        Args:
            member_id: Member ID
            appointment_type: Type of appointment
            date: Date object
            time: Time string in 24-hour format (e.g., "11:00")
            duration_minutes: Duration in minutes
            conductor: Conductor name
            timezone: IANA timezone string (e.g., 'America/Denver'). If None, uses HOME_TIMEZONE.
            notes: Optional notes (location, calling info, etc.)
            household: For the heads of the member's household
        """
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        # Use provided timezone or fall back to HOME_TIMEZONE
        if timezone is None:
            timezone = config.HOME_TIMEZONE

        # Create datetime in local timezone
        datetime_str = f"{date.strftime(config.DATE_FORMAT)} {time}"
        local_dt = datetime.strptime(datetime_str, f"{config.DATE_FORMAT} %H:%M")
        local_tz = ZoneInfo(timezone)
        local_dt = local_dt.replace(tzinfo=local_tz)

        # Convert to UTC
        utc_tz = ZoneInfo('UTC')
        utc_dt = local_dt.astimezone(utc_tz)

        # Format as ISO 8601 with Z suffix
        datetime_utc_str = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        now = datetime.now().strftime(config.DATE_FORMAT)
        appointment = Appointment(
            appointment_id=self.get_next_id(),
            member_id=member_id,
            appointment_type=appointment_type,
            datetime_utc=datetime_utc_str,
            duration_minutes=duration_minutes,
            conductor=conductor,
            state="Draft",
            created_date=now,
            last_updated=now,
            notes=notes,
            household=household
        )
        self.appointments.append(appointment)
        self.save()
        return appointment

    def update_state(self, appointment_id: int, new_state: str):
        """Update appointment state"""
        appointment = self.get_by_id(appointment_id)
        if appointment:
            appointment.state = new_state
            appointment.last_updated = datetime.now().strftime(config.DATE_FORMAT)

            if new_state == "Completed":
                appointment.completed_date = datetime.now().strftime(config.DATE_FORMAT)

            self.save()

    def update_appointment(
        self,
        appointment_id: int,
        appointment_type: Optional[str] = None,
        date: Optional[date] = None,
        time: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        conductor: Optional[str] = None,
        timezone: Optional[str] = None,
        notes: Optional[str] = None,
        household: Optional[bool] = None
    ):
        """Update appointment details

        Args:
            appointment_id: ID of appointment to update
            appointment_type: Optional new appointment type
            date: Optional new date
            time: Optional new time (24-hour format)
            duration_minutes: Optional new duration
            conductor: Optional new conductor
            timezone: Timezone for date/time interpretation. If None, uses HOME_TIMEZONE.
            notes: Optional notes (pass empty string to clear, None to leave unchanged)
            household: Optional - for the heads of the member's household
        """
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        appointment = self.get_by_id(appointment_id)
        if appointment:
            # If date or time is being updated, we need to rebuild datetime_utc
            if date is not None or time is not None:
                # Use provided timezone or fall back to HOME_TIMEZONE
                if timezone is None:
                    timezone = config.HOME_TIMEZONE

                local_tz = ZoneInfo(timezone)

                # Get current values if not updating
                if date is None:
                    date = appointment.date_obj
                if time is None:
                    # Extract LOCAL time from current datetime (not UTC time!)
                    current_local = appointment.datetime_local(timezone)
                    time = current_local.strftime('%H:%M')

                # Create datetime in local timezone
                datetime_str = f"{date.strftime(config.DATE_FORMAT)} {time}"
                local_dt = datetime.strptime(datetime_str, f"{config.DATE_FORMAT} %H:%M")
                local_dt = local_dt.replace(tzinfo=local_tz)

                # Convert to UTC
                utc_tz = ZoneInfo('UTC')
                utc_dt = local_dt.astimezone(utc_tz)

                # Update datetime_utc
                appointment.datetime_utc = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            if appointment_type is not None:
                appointment.appointment_type = appointment_type
            if duration_minutes is not None:
                appointment.duration_minutes = duration_minutes
            if conductor is not None:
                appointment.conductor = conductor
            if notes is not None:
                appointment.notes = notes if notes else None  # Convert empty string to None
            if household is not None:
                appointment.household = household

            appointment.last_updated = datetime.now().strftime(config.DATE_FORMAT)
            self.save()
