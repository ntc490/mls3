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

    @property
    def full_name(self):
        """Returns full name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def last_prayer_date_obj(self) -> Optional[date]:
        """Returns last_prayer_date as a date object, or None"""
        if self.last_prayer_date:
            return datetime.strptime(self.last_prayer_date, config.DATE_FORMAT).date()
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
            print(f"Warning: Members CSV not found at {self.csv_path}")
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
                    notes=row['notes']
                )
                self.members.append(member)

    def save(self):
        """Save members to CSV file"""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'member_id', 'first_name', 'last_name', 'gender', 'phone',
                'birthday', 'recommend_expiration', 'last_prayer_date',
                'dont_ask_prayer', 'active', 'notes'
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
        self.load()

    def load(self):
        """Load templates from YAML file"""
        if not self.yaml_path.exists():
            print(f"Warning: Message templates YAML not found at {self.yaml_path}")
            return

        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            self.templates = yaml.safe_load(f)

    def get_template(self, activity: str, template_name: str) -> str:
        """Get a specific template"""
        return self.templates.get(activity, {}).get(template_name, "")

    def expand_template(self, activity: str, template_name: str, **kwargs) -> str:
        """Get template and expand variables"""
        template = self.get_template(activity, template_name)
        return template.format(**kwargs)
