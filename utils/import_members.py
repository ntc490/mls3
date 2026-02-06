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


def parse_name(name_str: str) -> tuple:
    """
    Parse 'Last, First' format into first and last names.

    Args:
        name_str: Name in format "Last, First" or "Last,First"

    Returns:
        Tuple of (first_name, last_name)
    """
    if ',' in name_str:
        parts = name_str.split(',', 1)
        last_name = parts[0].strip()
        first_name = parts[1].strip() if len(parts) > 1 else ''
        return (first_name, last_name)
    else:
        # Fallback if no comma
        parts = name_str.strip().split()
        if len(parts) >= 2:
            return (parts[0], ' '.join(parts[1:]))
        else:
            return (name_str.strip(), '')


def parse_birth_date(date_str: str) -> str:
    """
    Parse birth date from format like "5 Dec 1953" to YYYY-MM-DD.

    Args:
        date_str: Date in format "5 Dec 1953" or similar

    Returns:
        Date string in YYYY-MM-DD format, or empty string if invalid
    """
    if not date_str:
        return ''

    try:
        # Try parsing "5 Dec 1953" format
        dt = datetime.strptime(date_str.strip(), '%d %b %Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        try:
            # Try "Dec 5, 1953" format
            dt = datetime.strptime(date_str.strip(), '%b %d, %Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            # Return as-is if we can't parse it
            return date_str.strip()


def parse_prayer_date(date_str: str) -> str:
    """
    Parse prayer date from various common formats to YYYY-MM-DD.

    Tries multiple common formats in order:
    - MM-DD-YYYY (most common)
    - M/D/YYYY
    - YYYY-MM-DD
    - Month DD, YYYY (Dec 5, 2023)
    - DD Month YYYY (5 Dec 2023)

    Also handles trailing markers:
    - 'c' for closing prayer (e.g., "12-05-2023c")
    - 'o' for opening prayer (e.g., "12-05-2023o")
    - '?' for undecided (e.g., "12-05-2023?")

    Args:
        date_str: Date string in various formats

    Returns:
        Date string in YYYY-MM-DD format, or empty string if invalid
    """
    if not date_str:
        return ''

    date_str = date_str.strip()

    # Strip trailing markers (c, o, ?)
    if date_str and date_str[-1] in ('c', 'o', '?', 'C', 'O'):
        date_str = date_str[:-1].strip()

    # List of formats to try, in order of likelihood
    formats = [
        '%m-%d-%Y',      # 12-05-2023
        '%m/%d/%Y',      # 12/5/2023
        '%m-%d-%y',      # 12-05-23
        '%m/%d/%y',      # 12/5/23
        '%Y-%m-%d',      # 2023-12-05 (already our format)
        '%b %d, %Y',     # Dec 5, 2023
        '%B %d, %Y',     # December 5, 2023
        '%d %b %Y',      # 5 Dec 2023
        '%d %B %Y',      # 5 December 2023
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    # If nothing worked, return as-is
    return date_str


def load_church_csv(filepath: Path, field_mapping: dict, delimiter: str = ',') -> list:
    """
    Load members from church website CSV export.

    Args:
        filepath: Path to church CSV file
        field_mapping: Dictionary mapping church fields to MLS3 fields
        delimiter: CSV delimiter (default: ',', use '\t' for tab-separated)

    Returns:
        List of dictionaries with MLS3 field names
    """
    members = []

    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            member_data = {}

            for mls3_field, church_field in field_mapping.items():
                if church_field in row:
                    value = row[church_field].strip()

                    # Special handling for name field
                    if mls3_field == 'name' and value:
                        first, last = parse_name(value)
                        member_data['first_name'] = first
                        member_data['last_name'] = last
                    # Special handling for birth date
                    elif mls3_field == 'birthday' and value:
                        member_data['birthday'] = parse_birth_date(value)
                    else:
                        member_data[mls3_field] = value
                else:
                    if mls3_field not in ['name']:  # Skip 'name' since we split it
                        member_data[mls3_field] = ''

            members.append(member_data)

    return members


def merge_members(existing_db: MemberDatabase, new_members: list, match_field: str = 'name',
                  activate_present: bool = False, deactivate_absent: bool = False, dry_run: bool = False) -> dict:
    """
    Merge new member data with existing database.

    Args:
        existing_db: Current member database
        new_members: List of new member dictionaries
        match_field: Field to use for matching ('name' or 'member_id')
        activate_present: If True, mark members in import as active=True
        deactivate_absent: If True, mark members NOT in import as active=False

    Returns:
        Dictionary with statistics: {added: int, updated: int, unchanged: int, activated: int, deactivated: int}
    """
    stats = {'added': 0, 'updated': 0, 'unchanged': 0, 'errors': 0, 'activated': 0, 'deactivated': 0}

    # Create lookup dictionary for existing members
    if match_field == 'name':
        existing_lookup = {
            f"{m.first_name.lower()} {m.last_name.lower()}": m
            for m in existing_db.members
        }
    else:
        existing_lookup = {m.member_id: m for m in existing_db.members}

    # Track which members are in the import
    members_in_import = set()

    # Get next available member_id
    next_id = max([m.member_id for m in existing_db.members], default=0) + 1

    for new_data in new_members:
        try:
            # Create lookup key
            if match_field == 'name':
                lookup_key = f"{new_data.get('first_name', '').lower()} {new_data.get('last_name', '').lower()}"
            else:
                lookup_key = int(new_data.get('member_id', 0))

            members_in_import.add(lookup_key)

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

                # Handle active flag based on mode
                if activate_present and not existing.active:
                    existing.active = True
                    stats['activated'] += 1
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

    # Deactivate members not in import
    if deactivate_absent:
        for key, member in existing_lookup.items():
            if key not in members_in_import and member.active:
                member.active = False
                stats['deactivated'] += 1
                print(f"  Deactivated: {member.full_name}")

    # Save updated database
    if not dry_run:
        existing_db.save()

    return stats


def find_member_by_name(db: MemberDatabase, name_str: str, fuzzy: bool = False) -> Member:
    """
    Find a member by name, trying both "Last, First" and "First Last" formats.

    Args:
        db: Member database
        name_str: Name string in either format
        fuzzy: If True, use fuzzy matching (matches if all query words appear in name)

    Returns:
        Member object if found, None otherwise
    """
    # Create lookup dictionary
    member_lookup = {}
    for m in db.members:
        # Store by "first last" (normalized)
        key = f"{m.first_name.lower()} {m.last_name.lower()}"
        member_lookup[key] = m

    # Try exact matching first
    # Try "Last, First" format first
    if ',' in name_str:
        first, last = parse_name(name_str)
        lookup_key = f"{first.lower()} {last.lower()}"
        if lookup_key in member_lookup:
            return member_lookup[lookup_key]

    # Try "First Last" format
    parts = name_str.strip().split()
    if len(parts) >= 2:
        first = parts[0]
        last = ' '.join(parts[1:])
        lookup_key = f"{first.lower()} {last.lower()}"
        if lookup_key in member_lookup:
            return member_lookup[lookup_key]

    # Try single name lookup
    lookup_key = name_str.lower().strip()
    if lookup_key in member_lookup:
        return member_lookup[lookup_key]

    # If fuzzy matching enabled, try word-based matching
    if fuzzy:
        # Parse query to extract all words (handles "Last, First" and "First Last")
        if ',' in name_str:
            # "Last, First" -> extract both parts
            parts = [p.strip() for p in name_str.split(',')]
            query_words = []
            for part in parts:
                query_words.extend(part.lower().split())
        else:
            query_words = name_str.lower().split()

        if not query_words:
            return None

        # Score each member based on how many query words match
        best_match = None
        best_score = 0

        for member in db.members:
            full_name_lower = f"{member.first_name.lower()} {member.last_name.lower()}"
            name_words = full_name_lower.split()

            # Count how many query words match name words (starting with)
            matches = 0
            for query_word in query_words:
                for name_word in name_words:
                    if name_word.startswith(query_word):
                        matches += 1
                        break

            # If all query words matched, this is a candidate
            if matches == len(query_words):
                # Prefer exact matches (higher score for longer matches)
                score = matches * 100 + sum(len(w) for w in query_words)
                if score > best_score:
                    best_score = score
                    best_match = member

        return best_match

    return None


def update_dont_ask_flags(db: MemberDatabase, names_csv: Path, set_value: bool, delimiter: str = '\t', dry_run: bool = False) -> dict:
    """
    Update dont_ask_prayer flag from a CSV file with Name column.

    Expected format (first row is header):
    Name
    Last, First
    OR
    First Last

    Args:
        db: Member database
        names_csv: Path to CSV with Name column
        set_value: True to set dont_ask_prayer=True, False to set dont_ask_prayer=False
        delimiter: CSV delimiter (default: tab)

    Returns:
        Dictionary with statistics: {updated: int, not_found: int, errors: int, not_found_names: list}
    """
    stats = {'updated': 0, 'not_found': 0, 'errors': 0, 'not_found_names': []}

    with open(names_csv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        # Check if required column exists
        if 'Name' not in reader.fieldnames and 'name' not in reader.fieldnames:
            print(f"Error: CSV must have 'Name' column")
            print(f"Found columns: {reader.fieldnames}")
            return stats

        # Determine actual column name (case-insensitive)
        name_col = 'Name' if 'Name' in reader.fieldnames else 'name'

        for row in reader:
            name_str = row[name_col].strip()

            if not name_str:
                continue

            try:
                # Find member using smart name matching with fuzzy enabled
                member = find_member_by_name(db, name_str, fuzzy=True)

                if member:
                    if member.dont_ask_prayer != set_value:
                        member.dont_ask_prayer = set_value
                        stats['updated'] += 1
                        status = "DON'T ASK" if set_value else "DO ASK"
                        print(f"  Updated: {member.full_name} → {status}")
                else:
                    stats['not_found'] += 1
                    stats['not_found_names'].append(name_str)

            except Exception as e:
                stats['errors'] += 1
                print(f"  Error processing: {name_str}: {e}")

    # Report names that weren't found
    if stats['not_found_names']:
        print("\n  Names not found in database:")
        for name in stats['not_found_names']:
            print(f"    - {name}")

    if not dry_run:
        db.save()
    return stats


def update_prayer_dates(db: MemberDatabase, prayer_csv: Path, delimiter: str = '\t', dry_run: bool = False) -> dict:
    """
    Update last_prayer_date from a tab-separated CSV file.

    Expected format (first row is header):
    Name    Prayed
    Last, First    MM-DD-YYYY
    OR
    First Last    MM-DD-YYYY

    Args:
        db: Member database
        prayer_csv: Path to CSV with columns: Name, Prayed
        delimiter: CSV delimiter (default: tab)

    Returns:
        Dictionary with statistics: {updated: int, not_found: int, errors: int, not_found_names: list}
    """
    stats = {'updated': 0, 'not_found': 0, 'errors': 0, 'not_found_names': []}

    with open(prayer_csv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        # Check if required columns exist
        if 'Name' not in reader.fieldnames and 'name' not in reader.fieldnames:
            print(f"Error: CSV must have 'Name' column")
            print(f"Found columns: {reader.fieldnames}")
            return stats

        if 'Prayed' not in reader.fieldnames and 'prayed' not in reader.fieldnames:
            print(f"Error: CSV must have 'Prayed' column")
            print(f"Found columns: {reader.fieldnames}")
            return stats

        # Determine actual column names (case-insensitive)
        name_col = 'Name' if 'Name' in reader.fieldnames else 'name'
        prayed_col = 'Prayed' if 'Prayed' in reader.fieldnames else 'prayed'

        for row in reader:
            name_str = row[name_col].strip()
            date_str = row[prayed_col].strip()

            if not name_str or not date_str:
                continue

            try:
                # Find member using smart name matching with fuzzy enabled
                member = find_member_by_name(db, name_str, fuzzy=True)

                if member:
                    # Parse date with flexible format support
                    parsed_date = parse_prayer_date(date_str)

                    if member.last_prayer_date != parsed_date:
                        member.last_prayer_date = parsed_date
                        stats['updated'] += 1
                        print(f"  Updated: {member.full_name} → {parsed_date}")
                else:
                    stats['not_found'] += 1
                    stats['not_found_names'].append(name_str)

            except Exception as e:
                stats['errors'] += 1
                print(f"  Error processing: {name_str}: {e}")

    # Report names that weren't found
    if stats['not_found_names']:
        print("\n  Names not found in database:")
        for name in stats['not_found_names']:
            print(f"    - {name}")

    if not dry_run:
        db.save()
    return stats


def create_backup(db: MemberDatabase):
    """Create a backup of the current member database"""
    # Skip backup if file doesn't exist yet
    if not config.MEMBERS_CSV.exists():
        print(f"Skipping backup (no existing file to backup)")
        return None

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
        nargs='?',
        help='Path to church CSV export file (not required for --update-prayed)'
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
    parser.add_argument(
        '--delimiter',
        default='\t',
        help='CSV delimiter (default: tab)'
    )
    parser.add_argument(
        '--activate-present',
        action='store_true',
        help='Mark members present in import as active=True'
    )
    parser.add_argument(
        '--deactivate-absent',
        action='store_true',
        help='Mark members NOT in import as active=False'
    )
    parser.add_argument(
        '--update-prayed',
        type=Path,
        metavar='PRAYER_CSV',
        help='Update last_prayer_date from CSV file (Name, Prayed columns)'
    )
    parser.add_argument(
        '--dont-ask',
        type=Path,
        metavar='NAMES_CSV',
        help='Set dont_ask_prayer=True for members in CSV file (Name column)'
    )
    parser.add_argument(
        '--do-ask',
        type=Path,
        metavar='NAMES_CSV',
        help='Set dont_ask_prayer=False for members in CSV file (Name column)'
    )
    parser.add_argument(
        '--show-dont-ask',
        action='store_true',
        help='List all members with dont_ask_prayer=True'
    )
    parser.add_argument(
        '--show-inactive',
        action='store_true',
        help='List all members with active=False'
    )

    args = parser.parse_args()

    # Load existing database
    print(f"Loading existing member database from: {config.MEMBERS_CSV}")
    db = MemberDatabase()

    if len(db.members) == 0:
        if not config.MEMBERS_CSV.exists():
            print(f"Creating new member database (file doesn't exist yet)")
        else:
            print(f"Current members: 0 (empty database)")
    else:
        print(f"Current members: {len(db.members)}")

    # Handle --show-dont-ask mode
    if args.show_dont_ask:
        dont_ask_members = [m for m in db.members if m.dont_ask_prayer]
        print(f"\n=== Members with Don't Ask Flag ===")
        print(f"Total: {len(dont_ask_members)}\n")

        if dont_ask_members:
            # Sort by last name
            dont_ask_members.sort(key=lambda m: (m.last_name.lower(), m.first_name.lower()))
            for m in dont_ask_members:
                status = "inactive" if not m.active else "active"
                print(f"  {m.full_name} ({m.gender}) - {status}")
        else:
            print("  (none)")

        return

    # Handle --show-inactive mode
    if args.show_inactive:
        inactive_members = [m for m in db.members if not m.active]
        print(f"\n=== Inactive Members ===")
        print(f"Total: {len(inactive_members)}\n")

        if inactive_members:
            # Sort by last name
            inactive_members.sort(key=lambda m: (m.last_name.lower(), m.first_name.lower()))
            for m in inactive_members:
                dont_ask_status = " [DON'T ASK]" if m.dont_ask_prayer else ""
                print(f"  {m.full_name} ({m.gender}){dont_ask_status}")
        else:
            print("  (none)")

        return

    # Handle --dont-ask mode
    if args.dont_ask:
        if not args.dont_ask.exists():
            print(f"Error: Names CSV file not found: {args.dont_ask}")
            sys.exit(1)

        # Create backup unless disabled
        if not args.no_backup and not args.dry_run:
            create_backup(db)

        print(f"\nSetting dont_ask_prayer=True from: {args.dont_ask}")
        print(f"Expected format: Name column (tab-separated)")
        print(f"Name format: Last, First OR First Last")
        print()

        if args.dry_run:
            print("=== DRY RUN - No changes will be saved ===\n")

        stats = update_dont_ask_flags(db, args.dont_ask, set_value=True, delimiter=args.delimiter, dry_run=args.dry_run)

        print("\n=== Don't Ask Update Results ===")
        print(f"Updated:   {stats['updated']} members")
        print(f"Not Found: {stats['not_found']} members")
        if stats['errors'] > 0:
            print(f"Errors:    {stats['errors']} entries")

        # Show not found names again at the end for visibility
        if stats.get('not_found_names'):
            print("\nNames not found in database:")
            for name in stats['not_found_names']:
                print(f"  - {name}")

        if args.dry_run:
            print("\nDry run complete - no changes saved")
        else:
            print(f"\nChanges saved to: {config.MEMBERS_CSV}")

        return

    # Handle --do-ask mode
    if args.do_ask:
        if not args.do_ask.exists():
            print(f"Error: Names CSV file not found: {args.do_ask}")
            sys.exit(1)

        # Create backup unless disabled
        if not args.no_backup and not args.dry_run:
            create_backup(db)

        print(f"\nSetting dont_ask_prayer=False from: {args.do_ask}")
        print(f"Expected format: Name column (tab-separated)")
        print(f"Name format: Last, First OR First Last")
        print()

        if args.dry_run:
            print("=== DRY RUN - No changes will be saved ===\n")

        stats = update_dont_ask_flags(db, args.do_ask, set_value=False, delimiter=args.delimiter, dry_run=args.dry_run)

        print("\n=== Do Ask Update Results ===")
        print(f"Updated:   {stats['updated']} members")
        print(f"Not Found: {stats['not_found']} members")
        if stats['errors'] > 0:
            print(f"Errors:    {stats['errors']} entries")

        # Show not found names again at the end for visibility
        if stats.get('not_found_names'):
            print("\nNames not found in database:")
            for name in stats['not_found_names']:
                print(f"  - {name}")

        if args.dry_run:
            print("\nDry run complete - no changes saved")
        else:
            print(f"\nChanges saved to: {config.MEMBERS_CSV}")

        return

    # Handle --update-prayed mode (separate from main import)
    if args.update_prayed:
        if not args.update_prayed.exists():
            print(f"Error: Prayer CSV file not found: {args.update_prayed}")
            sys.exit(1)

        # Create backup unless disabled
        if not args.no_backup and not args.dry_run:
            create_backup(db)

        print(f"\nUpdating prayer dates from: {args.update_prayed}")
        print(f"Expected format: Name (tab) Prayed")
        print(f"Name format: Last, First")
        print(f"Date formats: MM-DD-YYYY, M/D/YYYY, etc.")
        print()

        if args.dry_run:
            print("=== DRY RUN - No changes will be saved ===\n")

        stats = update_prayer_dates(db, args.update_prayed, delimiter=args.delimiter, dry_run=args.dry_run)

        print("\n=== Prayer Date Update Results ===")
        print(f"Updated:   {stats['updated']} members")
        print(f"Not Found: {stats['not_found']} members")
        if stats['errors'] > 0:
            print(f"Errors:    {stats['errors']} entries")

        # Show not found names again at the end for visibility
        if stats.get('not_found_names'):
            print("\nNames not found in database:")
            for name in stats['not_found_names']:
                print(f"  - {name}")

        if args.dry_run:
            print("\nDry run complete - no changes saved")
        else:
            print(f"\nChanges saved to: {config.MEMBERS_CSV}")

        return

    # Main import mode - validate CSV file
    if not args.csv_file:
        print("Error: csv_file is required (or use --update-prayed)")
        parser.print_help()
        sys.exit(1)

    if not args.csv_file.exists():
        print(f"Error: CSV file not found: {args.csv_file}")
        sys.exit(1)

    # Create backup unless disabled
    if not args.no_backup and not args.dry_run:
        create_backup(db)

    # Define field mapping
    # Format: Name    Gender  Age     Birth Date      Phone Number    E-mail
    # Name is "Last, First" format
    field_mapping = {
        'name': 'Name',                    # Will be split into first_name and last_name
        'gender': 'Gender',                # M or F
        'birthday': 'Birth Date',          # Format: "5 Dec 1953"
        'phone': 'Phone Number',           # Format: 801-419-2655
        # Skip Age and E-mail - we don't need them
    }

    print(f"\nImporting from: {args.csv_file}")
    print(f"Delimiter: {'tab' if args.delimiter == '\\t' else repr(args.delimiter)}")
    print(f"Field mapping: {field_mapping}")
    if args.activate_present:
        print("Mode: Will mark present members as active=True")
    if args.deactivate_absent:
        print("Mode: Will mark absent members as active=False")
    print()

    # Load church CSV
    try:
        new_members = load_church_csv(args.csv_file, field_mapping, delimiter=args.delimiter)
        print(f"Loaded {len(new_members)} members from church CSV")
    except Exception as e:
        print(f"Error loading church CSV: {e}")
        sys.exit(1)

    # Merge data
    if args.dry_run:
        print("\n=== DRY RUN - No changes will be saved ===")

    stats = merge_members(db, new_members, match_field=args.match_by,
                         activate_present=args.activate_present,
                         deactivate_absent=args.deactivate_absent,
                         dry_run=args.dry_run)

    # Print results
    print("\n=== Import Results ===")
    print(f"Added:     {stats['added']} new members")
    print(f"Updated:   {stats['updated']} existing members")
    print(f"Unchanged: {stats['unchanged']} members")
    if stats['activated'] > 0:
        print(f"Activated: {stats['activated']} members")
    if stats['deactivated'] > 0:
        print(f"Deactivated: {stats['deactivated']} members")
    if stats['errors'] > 0:
        print(f"Errors:    {stats['errors']} members")

    if args.dry_run:
        print("\nDry run complete - no changes saved")
    else:
        print(f"\nChanges saved to: {config.MEMBERS_CSV}")


if __name__ == '__main__':
    main()
