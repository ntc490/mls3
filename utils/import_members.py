#!/usr/bin/env python3
"""
Member Import Utility for MLS3

Imports and merges member data from church website CSV exports.
Preserves existing MLS3-specific data (last_prayer_date, dont_ask_prayer, notes).
"""
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from models import MemberDatabase, Member


def load_church_csv(filepath: Path, field_mapping: dict) -> list:
    """
    Load members from church website CSV export.

    Args:
        filepath: Path to church CSV file
        field_mapping: Dictionary mapping church fields to MLS3 fields

    Returns:
        List of dictionaries with MLS3 field names
    """
    members = []

    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            member_data = {}

            for mls3_field, church_field in field_mapping.items():
                if church_field in row:
                    member_data[mls3_field] = row[church_field].strip()
                else:
                    member_data[mls3_field] = ''

            members.append(member_data)

    return members


def merge_members(existing_db: MemberDatabase, new_members: list, match_field: str = 'name') -> dict:
    """
    Merge new member data with existing database.

    Args:
        existing_db: Current member database
        new_members: List of new member dictionaries
        match_field: Field to use for matching ('name' or 'member_id')

    Returns:
        Dictionary with statistics: {added: int, updated: int, unchanged: int}
    """
    stats = {'added': 0, 'updated': 0, 'unchanged': 0, 'errors': 0}

    # Create lookup dictionary for existing members
    if match_field == 'name':
        existing_lookup = {
            f"{m.first_name.lower()} {m.last_name.lower()}": m
            for m in existing_db.members
        }
    else:
        existing_lookup = {m.member_id: m for m in existing_db.members}

    # Get next available member_id
    next_id = max([m.member_id for m in existing_db.members], default=0) + 1

    for new_data in new_members:
        try:
            # Create lookup key
            if match_field == 'name':
                lookup_key = f"{new_data.get('first_name', '').lower()} {new_data.get('last_name', '').lower()}"
            else:
                lookup_key = int(new_data.get('member_id', 0))

            if lookup_key in existing_lookup:
                # Update existing member
                existing = existing_lookup[lookup_key]

                # Update fields that might have changed
                updated = False

                if new_data.get('phone') and existing.phone != new_data['phone']:
                    existing.phone = new_data['phone']
                    updated = True

                if new_data.get('birthday') and existing.birthday != new_data['birthday']:
                    existing.birthday = new_data['birthday']
                    updated = True

                if new_data.get('recommend_expiration') and existing.recommend_expiration != new_data['recommend_expiration']:
                    existing.recommend_expiration = new_data['recommend_expiration']
                    updated = True

                if new_data.get('gender') and existing.gender != new_data['gender']:
                    existing.gender = new_data['gender']
                    updated = True

                # Mark as active if in church export
                if not existing.active:
                    existing.active = True
                    updated = True

                if updated:
                    stats['updated'] += 1
                else:
                    stats['unchanged'] += 1

            else:
                # Add new member
                new_member = Member(
                    member_id=next_id,
                    first_name=new_data.get('first_name', ''),
                    last_name=new_data.get('last_name', ''),
                    gender=new_data.get('gender', ''),
                    phone=new_data.get('phone', ''),
                    birthday=new_data.get('birthday', ''),
                    recommend_expiration=new_data.get('recommend_expiration', ''),
                    last_prayer_date=None,
                    dont_ask_prayer=False,
                    active=True,
                    notes=''
                )
                existing_db.members.append(new_member)
                existing_lookup[lookup_key] = new_member
                next_id += 1
                stats['added'] += 1

        except Exception as e:
            print(f"Error processing member: {new_data.get('first_name')} {new_data.get('last_name')}: {e}")
            stats['errors'] += 1

    # Save updated database
    existing_db.save()

    return stats


def create_backup(db: MemberDatabase):
    """Create a backup of the current member database"""
    backup_dir = config.DATA_DIR / 'backups'
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_dir / f'members_backup_{timestamp}.csv'

    import shutil
    shutil.copy(config.MEMBERS_CSV, backup_file)

    print(f"Backup created: {backup_file}")
    return backup_file


def main():
    parser = argparse.ArgumentParser(
        description='Import members from church website CSV export'
    )
    parser.add_argument(
        'csv_file',
        type=Path,
        help='Path to church CSV export file'
    )
    parser.add_argument(
        '--match-by',
        choices=['name', 'id'],
        default='name',
        help='Field to use for matching (default: name)'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup before import'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without saving'
    )

    args = parser.parse_args()

    # Validate CSV file exists
    if not args.csv_file.exists():
        print(f"Error: CSV file not found: {args.csv_file}")
        sys.exit(1)

    # Load existing database
    print(f"Loading existing member database from: {config.MEMBERS_CSV}")
    db = MemberDatabase()
    print(f"Current members: {len(db.members)}")

    # Create backup unless disabled
    if not args.no_backup and not args.dry_run:
        create_backup(db)

    # Define field mapping
    # Adjust this mapping based on your church's CSV export format
    field_mapping = {
        'first_name': 'First Name',        # Change to match church CSV
        'last_name': 'Last Name',          # Change to match church CSV
        'gender': 'Gender',                # Change to match church CSV
        'phone': 'Phone',                  # Change to match church CSV
        'birthday': 'Birth Date',          # Change to match church CSV
        'recommend_expiration': 'Temple Recommend Expiration',  # Change to match
    }

    print(f"\nImporting from: {args.csv_file}")
    print(f"Field mapping: {field_mapping}")
    print()

    # Load church CSV
    try:
        new_members = load_church_csv(args.csv_file, field_mapping)
        print(f"Loaded {len(new_members)} members from church CSV")
    except Exception as e:
        print(f"Error loading church CSV: {e}")
        sys.exit(1)

    # Merge data
    if args.dry_run:
        print("\n=== DRY RUN - No changes will be saved ===")

    stats = merge_members(db, new_members, match_field=args.match_by)

    # Print results
    print("\n=== Import Results ===")
    print(f"Added:     {stats['added']} new members")
    print(f"Updated:   {stats['updated']} existing members")
    print(f"Unchanged: {stats['unchanged']} members")
    if stats['errors'] > 0:
        print(f"Errors:    {stats['errors']} members")

    if args.dry_run:
        print("\nDry run complete - no changes saved")
    else:
        print(f"\nChanges saved to: {config.MEMBERS_CSV}")


if __name__ == '__main__':
    main()
