#!/usr/bin/env python3
"""
Cleanup script to fix assignment issues
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
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Cleanup assignment issues')
    parser.add_argument('--delete-id', type=int, help='Delete assignment by ID')
    parser.add_argument('--delete-undecided', action='store_true', help='Delete all Undecided assignments for next Sunday')
    parser.add_argument('--delete-duplicates', action='store_true', help='Delete duplicate assignments for same member')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without saving')

    args = parser.parse_args()

    # Load databases
    members_db = MemberDatabase()
    assignments_db = PrayerAssignmentDatabase()

    next_sunday = get_next_sunday()
    next_sunday_str = next_sunday.strftime(config.DATE_FORMAT)

    print(f"Loaded {len(assignments_db.assignments)} assignments")
    print(f"Next Sunday: {next_sunday_str}")
    print()

    if args.delete_id:
        # Delete specific assignment
        assignment = assignments_db.get_by_id(args.delete_id)
        if not assignment:
            print(f"Assignment {args.delete_id} not found")
            return

        member = members_db.get_by_id(assignment.member_id) if assignment.member_id else None
        member_name = member.full_name if member else f"[ID={assignment.member_id}]"

        print(f"Deleting assignment {args.delete_id}:")
        print(f"  Member: {member_name}")
        print(f"  Type: {assignment.prayer_type}")
        print(f"  State: {assignment.state}")
        print(f"  Date: {assignment.date}")

        if not args.dry_run:
            assignments_db.assignments = [a for a in assignments_db.assignments if a.assignment_id != args.delete_id]
            assignments_db.save()
            print("\n✓ Deleted")
        else:
            print("\n[DRY RUN - Not saved]")

    elif args.delete_undecided:
        # Delete Undecided assignments for next Sunday
        to_delete = [
            a for a in assignments_db.assignments
            if a.date == next_sunday_str and a.prayer_type == 'Undecided' and a.state != 'Completed'
        ]

        if not to_delete:
            print("No Undecided assignments found for next Sunday")
            return

        print(f"Found {len(to_delete)} Undecided assignment(s) for next Sunday:")
        for a in to_delete:
            member = members_db.get_by_id(a.member_id) if a.member_id else None
            member_name = member.full_name if member else f"[ID={a.member_id}]"
            print(f"  - Assignment {a.assignment_id}: {member_name}, State: {a.state}")

        if not args.dry_run:
            delete_ids = {a.assignment_id for a in to_delete}
            assignments_db.assignments = [a for a in assignments_db.assignments if a.assignment_id not in delete_ids]
            assignments_db.save()
            print(f"\n✓ Deleted {len(to_delete)} assignment(s)")
        else:
            print("\n[DRY RUN - Not saved]")

    elif args.delete_duplicates:
        # Delete duplicate assignments for same member on next Sunday
        sunday_assignments = [a for a in assignments_db.assignments if a.date == next_sunday_str and a.state != 'Completed']

        # Group by member_id
        from collections import defaultdict
        by_member = defaultdict(list)
        for a in sunday_assignments:
            if a.member_id and a.member_id > 0:
                by_member[a.member_id].append(a)

        duplicates = {mid: assigns for mid, assigns in by_member.items() if len(assigns) > 1}

        if not duplicates:
            print("No duplicates found for next Sunday")
            return

        print(f"Found duplicates for {len(duplicates)} member(s):")
        to_delete = []

        for member_id, assigns in duplicates.items():
            member = members_db.get_by_id(member_id)
            print(f"\n{member.full_name if member else f'ID={member_id}'} has {len(assigns)} assignments:")

            # Sort: keep the first one, delete the rest
            assigns.sort(key=lambda a: a.assignment_id)
            keep = assigns[0]
            delete = assigns[1:]

            print(f"  KEEP: Assignment {keep.assignment_id} ({keep.prayer_type}, {keep.state})")
            for a in delete:
                print(f"  DELETE: Assignment {a.assignment_id} ({a.prayer_type}, {a.state})")
                to_delete.append(a.assignment_id)

        if not args.dry_run:
            delete_ids = set(to_delete)
            assignments_db.assignments = [a for a in assignments_db.assignments if a.assignment_id not in delete_ids]
            assignments_db.save()
            print(f"\n✓ Deleted {len(to_delete)} duplicate assignment(s)")
        else:
            print("\n[DRY RUN - Not saved]")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
