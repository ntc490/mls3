#!/usr/bin/env python3
"""
Debug script to find and fix assignment issues
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from models import MemberDatabase, PrayerAssignmentDatabase
from datetime import date, timedelta

def get_next_sunday(from_date: date = None) -> date:
    """Get the next Sunday from a given date (or today)"""
    if from_date is None:
        from_date = date.today()

    days_ahead = 6 - from_date.weekday()  # Sunday is 6
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def main():
    # Load databases
    members_db = MemberDatabase()
    assignments_db = PrayerAssignmentDatabase()

    print(f"Loaded {len(members_db.members)} members")
    print(f"Loaded {len(assignments_db.assignments)} assignments")
    print()

    # Get next Sunday
    next_sunday = get_next_sunday()
    next_sunday_str = next_sunday.strftime(config.DATE_FORMAT)

    print(f"Next Sunday: {next_sunday_str}")
    print()

    # Find all assignments for next Sunday
    sunday_assignments = assignments_db.get_assignments_for_date(next_sunday)

    if not sunday_assignments:
        print("No assignments found for next Sunday")
        return

    print(f"Found {len(sunday_assignments)} assignment(s) for next Sunday:")
    print()

    for assignment in sunday_assignments:
        member = members_db.get_by_id(assignment.member_id) if assignment.member_id else None

        print(f"Assignment ID: {assignment.assignment_id}")
        print(f"  Member ID: {assignment.member_id}")
        if member:
            print(f"  Member Name: {member.full_name}")
        else:
            print(f"  Member Name: [Not assigned or ID={assignment.member_id}]")
        print(f"  Prayer Type: {assignment.prayer_type}")
        print(f"  State: {assignment.state}")
        print(f"  Date: {assignment.date}")
        print(f"  Created: {assignment.created_date}")
        print(f"  Last Updated: {assignment.last_updated}")
        print()

    # Check for issues
    print("Checking for issues:")
    print()

    # Issue 1: Assignments with member_id=0 or None
    empty_assignments = [a for a in sunday_assignments if not a.member_id or a.member_id == 0]
    if empty_assignments:
        print(f"⚠ Found {len(empty_assignments)} assignment(s) with no member assigned")
        for a in empty_assignments:
            print(f"  - Assignment {a.assignment_id}: {a.prayer_type}, State: {a.state}")

    # Issue 2: Non-completed assignments
    active = [a for a in sunday_assignments if a.state != 'Completed']
    if active:
        print(f"Found {len(active)} active (non-completed) assignment(s)")
        for a in active:
            member = members_db.get_by_id(a.member_id) if a.member_id else None
            member_name = member.full_name if member else f"[ID={a.member_id}]"
            print(f"  - {member_name}: {a.prayer_type}, State: {a.state}")

    # Issue 3: Duplicate member assignments
    member_ids = [a.member_id for a in sunday_assignments if a.member_id and a.member_id > 0]
    if len(member_ids) != len(set(member_ids)):
        print(f"⚠ DUPLICATE: Same member has multiple assignments!")
        from collections import Counter
        counts = Counter(member_ids)
        for member_id, count in counts.items():
            if count > 1:
                member = members_db.get_by_id(member_id)
                print(f"  - {member.full_name if member else f'ID={member_id}'}: {count} assignments")


if __name__ == '__main__':
    main()
