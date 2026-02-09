#!/usr/bin/env python3
"""
Household Import Utility for MLS3

Imports household data from church TSV export and links members to households.
Handles fuzzy matching of member names and automatic household ID assignment.

Usage:
    ./utils/import_households.py <household_report.tsv>
"""
import sys
import csv
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from models import MemberDatabase, HouseholdDatabase, Household


def fuzzy_match_score(s1: str, s2: str) -> float:
    """
    Calculate fuzzy match score between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score between 0 and 1
    """
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def find_matching_member(first_name: str, last_name: str, members_db: MemberDatabase) -> Optional[int]:
    """
    Find matching member by first and last name using fuzzy matching.

    Args:
        first_name: Member's first name
        last_name: Member's last name
        members_db: MemberDatabase instance

    Returns:
        Member ID if found, None otherwise
    """
    best_score = 0
    best_member = None

    for member in members_db.members:
        # Calculate fuzzy match scores for both first and last names
        first_score = fuzzy_match_score(first_name, member.first_name)
        last_score = fuzzy_match_score(last_name, member.last_name)

        # Average the scores
        avg_score = (first_score + last_score) / 2

        # If this is a better match and above threshold
        if avg_score > best_score and avg_score >= 0.8:
            best_score = avg_score
            best_member = member

    return best_member.member_id if best_member else None


def parse_household_tsv(tsv_path: Path) -> List[Dict]:
    """
    Parse household TSV file exported from church system.

    Expected format:
    - Tab-separated values
    - First line: Family name (e.g., "Smith, Jack & Jill")
    - Following lines: Individual first names
    - Then: Address lines
    - Then: Phone number
    - Then: Email
    - Blank line separates households

    Args:
        tsv_path: Path to TSV file

    Returns:
        List of household dictionaries
    """
    households = []
    current_household = None

    with open(tsv_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            # Blank line indicates end of household
            if not line.strip():
                if current_household:
                    households.append(current_household)
                    current_household = None
                continue

            # Parse tab-separated values
            parts = line.split('\t')

            if current_household is None:
                # First line of household - family name
                current_household = {
                    'name': parts[0] if parts else '',
                    'members': [],
                    'address': '',
                    'phone': '',
                    'email': ''
                }
            else:
                # Subsequent lines - could be member names or contact info
                # If line looks like a name (single word or two words)
                if len(parts[0].split()) <= 2 and not '@' in parts[0] and not any(c.isdigit() for c in parts[0][:5]):
                    current_household['members'].append(parts[0])
                elif '@' in parts[0]:
                    # Email address
                    current_household['email'] = parts[0]
                elif any(c.isdigit() for c in parts[0]):
                    # Phone or address - check if it looks like a phone number
                    if parts[0].replace('-', '').replace('(', '').replace(')', '').replace(' ', '').isdigit():
                        current_household['phone'] = parts[0]
                    else:
                        # Address line
                        if current_household['address']:
                            current_household['address'] += '\n'
                        current_household['address'] += parts[0]

        # Add last household if exists
        if current_household:
            households.append(current_household)

    return households


def import_households(tsv_path: Path, dry_run: bool = False):
    """
    Import households from TSV file and link members.

    Args:
        tsv_path: Path to TSV file
        dry_run: If True, only show what would be imported without saving
    """
    print(f"Reading household data from {tsv_path}...")

    # Load databases
    members_db = MemberDatabase()
    households_db = HouseholdDatabase()

    print(f"Loaded {len(members_db.members)} members")
    print(f"Loaded {len(households_db.households)} existing households")

    # Parse TSV file
    household_data = parse_household_tsv(tsv_path)
    print(f"\nParsed {len(household_data)} households from TSV\n")

    # Process each household
    stats = {
        'households_added': 0,
        'members_linked': 0,
        'members_not_found': 0
    }

    next_household_id = households_db.get_next_id()

    for hh_data in household_data:
        print(f"\nHousehold: {hh_data['name']}")
        print(f"  Members: {', '.join(hh_data['members'])}")
        print(f"  Address: {hh_data['address']}")
        print(f"  Phone: {hh_data['phone']}")
        print(f"  Email: {hh_data['email']}")

        if not dry_run:
            # Create household
            household = Household(
                household_id=next_household_id,
                name=hh_data['name'],
                address=hh_data['address'],
                phone=hh_data['phone'],
                email=hh_data['email']
            )
            households_db.add(household)
            stats['households_added'] += 1

        # Parse last name from household name
        # Format is typically "Last, First & First" or just "Last, First"
        last_name = hh_data['name'].split(',')[0].strip()

        # Link members
        for member_first_name in hh_data['members']:
            member_first_name = member_first_name.strip()
            member_id = find_matching_member(member_first_name, last_name, members_db)

            if member_id:
                print(f"  ✓ Linked: {member_first_name} {last_name} (ID: {member_id})")
                if not dry_run:
                    members_db.update_member(member_id, household_id=next_household_id)
                    stats['members_linked'] += 1
            else:
                print(f"  ✗ Not found: {member_first_name} {last_name}")
                stats['members_not_found'] += 1

        next_household_id += 1

    # Print summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"Households added: {stats['households_added']}")
    print(f"Members linked: {stats['members_linked']}")
    print(f"Members not found: {stats['members_not_found']}")

    if dry_run:
        print("\n(DRY RUN - No changes saved)")
    else:
        print("\n✓ Changes saved successfully!")


def main():
    parser = argparse.ArgumentParser(
        description='Import household data from church TSV export'
    )
    parser.add_argument(
        'tsv_file',
        type=Path,
        help='Path to household TSV file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be imported without saving changes'
    )

    args = parser.parse_args()

    if not args.tsv_file.exists():
        print(f"Error: File not found: {args.tsv_file}")
        sys.exit(1)

    import_households(args.tsv_file, args.dry_run)


if __name__ == '__main__':
    main()
