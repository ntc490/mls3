#!/usr/bin/env python3
"""
Sync Last Prayer Dates Utility for MLS3

Scans all completed prayer assignments and updates each member's
last_prayer_date field in members.csv to match their most recent
completed prayer.

This is a one-time sync utility to ensure data consistency.
Going forward, the last_prayer_date is automatically maintained
when prayers are marked as completed.

Usage:
    ./utils/sync_prayer_dates.py [--dry-run]
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from models import MemberDatabase, PrayerAssignmentDatabase


def sync_prayer_dates(dry_run: bool = False):
    """
    Sync last_prayer_date in members.csv from completed prayer assignments.

    Args:
        dry_run: If True, show what would be updated without saving
    """
    print(f"\n{'='*60}")
    print("MLS3 - Sync Last Prayer Dates")
    print(f"{'='*60}\n")

    # Load databases
    members_db = MemberDatabase()
    assignments_db = PrayerAssignmentDatabase()

    print(f"Loaded {len(members_db.members)} members")
    print(f"Loaded {len(assignments_db.assignments)} prayer assignments\n")

    # Get all completed assignments
    completed_assignments = [
        a for a in assignments_db.assignments
        if a.state == 'Completed' and a.member_id
    ]

    print(f"Found {len(completed_assignments)} completed prayer assignments\n")

    # Build a map of member_id -> most recent completed prayer date
    member_last_prayer = {}
    for assignment in completed_assignments:
        member_id = assignment.member_id
        prayer_date = assignment.date_obj

        if member_id not in member_last_prayer:
            member_last_prayer[member_id] = prayer_date
        else:
            # Keep the most recent date
            if prayer_date > member_last_prayer[member_id]:
                member_last_prayer[member_id] = prayer_date

    print(f"Found prayer history for {len(member_last_prayer)} members\n")

    # Stats
    stats = {
        'updated': 0,
        'already_correct': 0,
        'cleared': 0,
        'no_change': 0
    }

    # Update each member
    print("Syncing member records...")
    print("-" * 60)

    for member in members_db.members:
        member_id = member.member_id
        current_date = member.last_prayer_date

        # Get the calculated last prayer date from assignments
        calculated_date = None
        if member_id in member_last_prayer:
            calculated_date = member_last_prayer[member_id].strftime(config.DATE_FORMAT)

        # Compare and update if needed
        if current_date == calculated_date:
            stats['already_correct'] += 1
        elif calculated_date is None and current_date is None:
            stats['no_change'] += 1
        elif calculated_date is None and current_date is not None:
            # Member has a date but no completed prayers - should clear it
            print(f"  CLEAR: {member.full_name}")
            print(f"         Current: {current_date} -> New: None")
            if not dry_run:
                members_db.update_member(member_id, last_prayer_date=None)
            stats['cleared'] += 1
        else:
            # Need to update
            action = "UPDATE" if current_date else "SET"
            print(f"  {action}: {member.full_name}")
            print(f"         Current: {current_date or 'None'} -> New: {calculated_date}")
            if not dry_run:
                members_db.update_member(member_id, last_prayer_date=calculated_date)
            stats['updated'] += 1

    # Print summary
    print("\n" + "="*60)
    print("SYNC SUMMARY")
    print("="*60)
    print(f"Members already correct: {stats['already_correct']}")
    print(f"Members with no prayers: {stats['no_change']}")
    print(f"Members updated:         {stats['updated']}")
    print(f"Members cleared:         {stats['cleared']}")
    print(f"Total members:           {len(members_db.members)}")

    if dry_run:
        print("\n(DRY RUN - No changes saved)")
    else:
        print("\n✓ Changes saved to members.csv")
        print("\nMembers.csv is now synchronized with completed prayer assignments!")


def main():
    parser = argparse.ArgumentParser(
        description='Sync last_prayer_date in members.csv from completed prayer assignments'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without saving changes'
    )

    args = parser.parse_args()
    sync_prayer_dates(args.dry_run)


if __name__ == '__main__':
    main()
