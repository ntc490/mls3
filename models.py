"""
Data models for MLS3
Handles CSV-based data persistence for members and prayer assignments
"""
import csv
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional
import yaml

import config


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


class MemberDatabase:
    """Manages member data from CSV"""

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.MEMBERS_CSV
        self.members: List[Member] = []
        self.load()

    def load(self):
        """Load members from CSV file"""
        self.members = []

        if not self.csv_path.exists():
            # File doesn't exist yet - this is OK, we'll create it on save
            return

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                member = Member(
                    member_id=int(row['member_id']),
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    gender=row['gender'],
                    phone=row['phone'],
                    birthday=row['birthday'],
                    recommend_expiration=row['recommend_expiration'],
                    last_prayer_date=row['last_prayer_date'] if row['last_prayer_date'] else None,
                    dont_ask_prayer=row['dont_ask_prayer'].lower() == 'true',
                    active=row['active'].lower() == 'true',
                    notes=row['notes'],
                    skip_until=row.get('skip_until') if row.get('skip_until') else None,
                    flag=row.get('flag', ''),
                    aka=row.get('aka', '')
                )
                self.members.append(member)

    def save(self):
        """Save members to CSV file"""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'member_id', 'first_name', 'last_name', 'gender', 'phone',
                'birthday', 'recommend_expiration', 'last_prayer_date',
                'dont_ask_prayer', 'active', 'notes', 'skip_until', 'flag', 'aka'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for member in self.members:
                row = asdict(member)
                writer.writerow(row)

    def get_by_id(self, member_id: int) -> Optional[Member]:
        """Get member by ID"""
        for member in self.members:
            if member.member_id == member_id:
                return member
        return None

    def get_active_members(self, gender: Optional[str] = None) -> List[Member]:
        """Get all active members, optionally filtered by gender"""
        result = [m for m in self.members if m.active]
        if gender:
            result = [m for m in result if m.gender == gender]
        return result

    def search(self, query: str) -> List[Member]:
        """Fuzzy search for members by name"""
        query = query.lower()
        results = []

        for member in self.members:
            if member.active:
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
        """Get member's last prayer date from members.csv"""
        member = self.get_by_id(member_id)
        if not member:
            return None

        return member.last_prayer_date


class PrayerAssignmentDatabase:
    """Manages prayer assignment data from CSV"""

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.PRAYER_ASSIGNMENTS_CSV
        self.assignments: List[PrayerAssignment] = []
        self.load()

    def load(self):
        """Load assignments from CSV file"""
        self.assignments = []

        if not self.csv_path.exists():
            print(f"Warning: Prayer assignments CSV not found at {self.csv_path}")
            return

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                assignment = PrayerAssignment(
                    assignment_id=int(row['assignment_id']),
                    member_id=int(row['member_id']),
                    date=row['date'],
                    prayer_type=row['prayer_type'],
                    state=row['state'],
                    created_date=row['created_date'],
                    last_updated=row['last_updated'],
                    completed_date=row['completed_date'] if row['completed_date'] else None
                )
                self.assignments.append(assignment)

    def save(self):
        """Save assignments to CSV file"""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'assignment_id', 'member_id', 'date', 'prayer_type', 'state',
                'created_date', 'last_updated', 'completed_date'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for assignment in self.assignments:
                row = asdict(assignment)
                writer.writerow(row)

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

    def __init__(self, csv_path: Path = None):
        self.csv_path = csv_path or config.APPOINTMENTS_CSV
        self.appointments: List[Appointment] = []
        self.load()

    def load(self):
        """Load appointments from CSV file"""
        self.appointments = []

        if not self.csv_path.exists():
            print(f"Warning: Appointments CSV not found at {self.csv_path}")
            return

        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                appointment = Appointment(
                    appointment_id=int(row['appointment_id']),
                    member_id=int(row['member_id']),
                    appointment_type=row['appointment_type'],
                    datetime_utc=row['datetime_utc'],
                    duration_minutes=int(row['duration_minutes']),
                    conductor=row['conductor'],
                    state=row['state'],
                    created_date=row['created_date'],
                    last_updated=row['last_updated'],
                    completed_date=row['completed_date'] if row['completed_date'] else None
                )
                self.appointments.append(appointment)

    def save(self):
        """Save appointments to CSV file"""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'appointment_id', 'member_id', 'appointment_type', 'datetime_utc',
                'duration_minutes', 'conductor', 'state', 'created_date',
                'last_updated', 'completed_date'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for appointment in self.appointments:
                row = asdict(appointment)
                writer.writerow(row)

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

    def get_appointments_for_member(self, member_id: int) -> List[Appointment]:
        """Get all appointments for a specific member"""
        return [a for a in self.appointments if a.member_id == member_id]

    def create_appointment(
        self,
        member_id: int,
        appointment_type: str,
        date: date,
        time: str,
        duration_minutes: int,
        conductor: str,
        timezone: str = None
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
            last_updated=now
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
        timezone: Optional[str] = None
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
        """
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        appointment = self.get_by_id(appointment_id)
        if appointment:
            # If date or time is being updated, we need to rebuild datetime_utc
            if date is not None or time is not None:
                # Get current values if not updating
                if date is None:
                    date = appointment.date_obj
                if time is None:
                    # Extract time from current datetime_utc
                    time = appointment.time

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

                # Update datetime_utc
                appointment.datetime_utc = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            if appointment_type is not None:
                appointment.appointment_type = appointment_type
            if duration_minutes is not None:
                appointment.duration_minutes = duration_minutes
            if conductor is not None:
                appointment.conductor = conductor

            appointment.last_updated = datetime.now().strftime(config.DATE_FORMAT)
            self.save()
