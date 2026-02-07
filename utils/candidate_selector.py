"""
Candidate Selection Algorithm for MLS3

Implements fair rotation logic for selecting next prayer candidates.
"""
from datetime import date
from typing import List, Optional
from models import Member, MemberDatabase, PrayerAssignmentDatabase


def get_next_candidates(
    members_db: MemberDatabase,
    assignments_db: PrayerAssignmentDatabase,
    gender: str,
    count: int = 3
) -> List[Member]:
    """
    Get the next eligible candidates for prayer assignment.

    Returns members sorted by last_prayer_date (oldest first).
    Excludes anyone currently in active queue, marked dont_ask, or skipped until future date.

    Args:
        members_db: Member database
        assignments_db: Prayer assignment database
        gender: 'M' or 'F'
        count: Number of candidates to return (default: 3)

    Returns:
        List of Member objects (up to count)
    """
    today = date.today()

    # Get all active members of specified gender
    eligible = [
        m for m in members_db.members
        if m.active and m.gender == gender and not m.dont_ask_prayer
    ]

    # Exclude members with skip_until date in the future
    eligible = [
        m for m in eligible
        if not m.skip_until_obj or m.skip_until_obj <= today
    ]

    # Get member IDs with active assignments
    assigned_member_ids = assignments_db.get_assigned_member_ids()

    # Exclude anyone currently assigned
    eligible = [m for m in eligible if m.member_id not in assigned_member_ids]

    # Sort by last_prayer_date (oldest first, nulls first)
    # Nulls = never prayed, they should go first
    eligible.sort(key=lambda m: m.last_prayer_date_obj or date.min)

    return eligible[:count]


def get_candidates_with_context(
    members_db: MemberDatabase,
    assignments_db: PrayerAssignmentDatabase,
    gender: str,
    count: int = 3
) -> List[dict]:
    """
    Get next candidates with additional context for display.

    Returns list of dictionaries with member info and display context.

    Args:
        members_db: Member database
        assignments_db: Prayer assignment database
        gender: 'M' or 'F'
        count: Number of candidates to return

    Returns:
        List of dicts with keys: member, last_prayer_date_display, priority
    """
    candidates = get_next_candidates(members_db, assignments_db, gender, count)

    results = []
    for i, member in enumerate(candidates):
        if member.last_prayer_date:
            display_date = member.last_prayer_date
        else:
            display_date = "Never"

        results.append({
            'member': member,
            'last_prayer_date_display': display_date,
            'priority': i + 1  # 1 = highest priority
        })

    return results


def find_member_by_fuzzy_search(
    members_db: MemberDatabase,
    query: str,
    gender: Optional[str] = None,
    limit: int = 10
) -> List[Member]:
    """
    Fuzzy search for members by name.

    Supports multi-word queries where each word can match the start of
    any part of the name. For example:
    - "bi wo" matches "Bill Wong" or "Wonder Biatch"
    - "j sm" matches "John Smith" or "Jane Smoot"

    Args:
        members_db: Member database
        query: Search query (space-separated words)
        gender: Optional gender filter ('M' or 'F')
        limit: Maximum results to return

    Returns:
        List of matching members
    """
    query_lower = query.lower().strip()

    if not query_lower:
        # No query, return active members of specified gender
        members = members_db.get_active_members(gender=gender)
        return members[:limit]

    # Split query into words
    query_words = query_lower.split()

    # Search in full name
    results = []
    for member in members_db.members:
        if not member.active:
            continue

        if gender and member.gender != gender:
            continue

        full_name = member.full_name.lower()
        first_name = member.first_name.lower()
        last_name = member.last_name.lower()
        name_parts = [first_name, last_name]

        # Single word query - use original logic
        if len(query_words) == 1:
            word = query_words[0]
            # Check for substring match in full name
            if word in full_name:
                results.append((member, 0))  # Priority 0 = highest
            # Check first name starts with query
            elif first_name.startswith(word):
                results.append((member, 1))
            # Check last name starts with query
            elif last_name.startswith(word):
                results.append((member, 2))
        else:
            # Multi-word query - each word must match start of some name part
            # For "bi wo" to match "Bill Wong":
            # - "bi" matches start of "bill"
            # - "wo" matches start of "wong"
            matched_words = 0
            for query_word in query_words:
                for name_part in name_parts:
                    if name_part.startswith(query_word):
                        matched_words += 1
                        break  # Found match for this query word, move to next

            # If all query words matched, add to results
            if matched_words == len(query_words):
                # Priority based on how early the matches are
                # Prefer matches in order (first word matches first name)
                priority = 3
                if first_name.startswith(query_words[0]):
                    priority = 2  # Better if first query word matches first name
                results.append((member, priority))

    # Sort by priority, then by name
    results.sort(key=lambda x: (x[1], x[0].last_name, x[0].first_name))

    return [m for m, _ in results[:limit]]
