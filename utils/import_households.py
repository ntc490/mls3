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
    - Header row: <tab>Name<tab>Household Members<tab>Address<tab>Phone Number<tab>E-mail
    - Each household:
      - Row 1: <tab>Family Name<tab><empty>
      - Row 2-N: Member first names (one per line, no tabs)
      - Last row: Address lines...<tab>Phone<tab>Email

    Args:
        tsv_path: Path to TSV file

    Returns:
        List of household dictionaries
    """
    households = []
    current_household = None
    address_lines = []

    with open(tsv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Skip header row
    i = 1
    while i < len(lines):
        line = lines[i].rstrip('\n')
        i += 1

        # Check if this is a household name line (starts with tab, has household name)
        if line.startswith('\t') and line.strip():
            # Save previous household if exists
            if current_household:
                # Clean up address
                current_household['address'] = '\n'.join(address_lines).strip()
                households.append(current_household)
                address_lines = []

            # Parse household name line: <tab>Name<tab>...
            parts = line.split('\t')
            household_name = parts[1] if len(parts) > 1 else parts[0].strip()

            current_household = {
                'name': household_name,
                'members': [],
                'address': '',
                'phone': '',
                'email': ''
            }

        elif current_household and not line.startswith('\t') and line.strip():
            # This is a member name or address line (no leading tab)
            content = line.strip()

            # Check if this line has tabs (final line with contact info)
            if '\t' in line:
                # This is the final line: address<tab>phone<tab>email
                parts = line.split('\t')

                # First part is rest of address
                if parts[0].strip():
                    address_lines.append(parts[0].strip())

                # Phone is second column
                if len(parts) > 1 and parts[1].strip():
                    current_household['phone'] = parts[1].strip()

                # Email is third column
                if len(parts) > 2 and parts[2].strip():
                    current_household['email'] = parts[2].strip()
            else:
                # Check if this looks like a name or address
                # Names can be:
                #   - "FirstName" or "FirstName (age)"
                #   - "LastName, FirstName" or "LastName, FirstName (age)" (different last name)
                # Addresses typically have street indicators: numbers, "Street", "Ln", "Cir", "W", "E", etc.

                # Check if this is a full name with different last name: "Spooner, Tyler Franklin (13)"
                if ',' in content:
                    # Could be "LastName, FirstName" or an address
                    # If it doesn't look like an address, treat as a name
                    # Addresses with commas usually have state: "Riverton UT 84065, USA" or multi-part addresses
                    # Names with commas: "LastName, FirstName"

                    # Heuristic: If comma is followed by a capitalized word (not state abbrev), it's likely a name
                    comma_parts = content.split(',', 1)
                    if len(comma_parts) == 2:
                        after_comma = comma_parts[1].strip().split()[0] if comma_parts[1].strip() else ''
                        # If after comma looks like a first name (capitalized, not a state code, not a number)
                        if after_comma and after_comma[0].isupper() and len(after_comma) > 2 and not after_comma.isdigit():
                            # This is a name: "Spooner, Tyler Franklin"
                            current_household['members'].append(content)
                        else:
                            # This is an address
                            address_lines.append(content)
                    else:
                        address_lines.append(content)
                else:
                    # No comma - check if name or address
                    # Extract name without age (if present)
                    name_part = content.split('(')[0].strip()

                    # If it's a short name-like string (1-3 words, no numbers at start, no street indicators)
                    words = name_part.split()
                    has_street_indicator = any(word in ['W', 'E', 'N', 'S', 'Street', 'St', 'Ave', 'Ln', 'Dr', 'Cir', 'Way', 'Ct'] for word in words)

                    if len(words) <= 3 and not any(c.isdigit() for c in name_part[:3]) and not has_street_indicator:
                        # This is a member name
                        current_household['members'].append(content)
                    else:
                        # This is an address line
                        address_lines.append(content)

    # Add last household if exists
    if current_household:
        current_household['address'] = '\n'.join(address_lines).strip()
        households.append(current_household)

    return households


def import_households(tsv_path: Path, dry_run: bool = False):
    """
    Import households from TSV file and link members.

    NOTE: This clears ALL existing household assignments and recreates them from the TSV.
    This ensures the database matches the current church household export.

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

    # Clear all existing household assignments
    print("\nClearing existing household assignments...")
    if not dry_run:
        for member in members_db.members:
            if member.household_id:
                members_db.update_member(member.member_id, household_id=None)
        # Clear all existing households
        households_db.households = []
        households_db.save()
    print("✓ Cleared all household data")

    # Parse TSV file
    household_data = parse_household_tsv(tsv_path)
    print(f"\nParsed {len(household_data)} households from TSV\n")

    # Process each household
    stats = {
        'households_added': 0,
        'members_linked': 0,
        'members_not_found': 0,
        'members_unlinked': sum(1 for m in members_db.members if m.household_id is not None) if not dry_run else 0
    }

    # Start household IDs from 1 since we cleared everything
    next_household_id = 1

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
        household_last_name = hh_data['name'].split(',')[0].strip()

        # Link members
        for member_name in hh_data['members']:
            member_name = member_name.strip()

            # Remove age suffix if present: "Tyler Franklin (13)" -> "Tyler Franklin"
            if '(' in member_name:
                member_name = member_name.split('(')[0].strip()

            # Check if this member has a different last name
            # Format: "LastName, FirstName" or just "FirstName"
            if ',' in member_name:
                # Full name with different last name: "Spooner, Tyler Franklin"
                parts = member_name.split(',', 1)
                member_last_name = parts[0].strip()
                member_first_name = parts[1].strip()
            else:
                # Just first name - use household last name
                member_first_name = member_name
                member_last_name = household_last_name

            member_id = find_matching_member(member_first_name, member_last_name, members_db)

            if member_id:
                print(f"  ✓ Linked: {member_first_name} {member_last_name} (ID: {member_id})")
                if not dry_run:
                    members_db.update_member(member_id, household_id=next_household_id)
                    stats['members_linked'] += 1
            else:
                print(f"  ✗ Not found: {member_first_name} {member_last_name}")
                stats['members_not_found'] += 1

        next_household_id += 1

    # Print summary
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    if not dry_run:
        print(f"Previous household assignments cleared: {stats['members_unlinked']}")
    print(f"Households added: {stats['households_added']}")
    print(f"Members linked: {stats['members_linked']}")
    print(f"Members not found: {stats['members_not_found']}")

    if dry_run:
        print("\n(DRY RUN - No changes saved)")
    else:
        print("\n✓ Changes saved successfully!")
        print("\nNOTE: All previous household data was cleared and replaced with this import.")


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
