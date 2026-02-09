# Household Import Feature - Design Notes

## Overview
Need to import household data to link members to households and identify parent-child relationships for minors.

## Sample Data Format

From church export (tab-separated):
```
Name    Household Members       Address Phone Number    E-mail
Anderson, Bryan & Barbara
Bryan
Barbara
3439 W Winding Creek Ln
Riverton UT     801-573-2025    bryan.anderson.08@comcast.net

Anderson, Jack & Rachel
Jack
Rachel
Easton
3387 W Gentle Creek Cir
Riverton UT 84065       801-918-5677    rockethead98052@gmail.com
```

## Data Structure Analysis

**Multi-line records** where:
- Line 1: `Name` column contains head(s) of household (e.g., "Anderson, Bryan & Barbara")
- Lines 2+: List of household members (first names only)
- Address spans multiple lines
- Phone and email on first line only

## Proposed Database Schema Changes

### Add to Member model:
```python
household_id: Optional[int] = None  # Links to household
is_minor: bool = False  # Calculated from age < 18
```

### New Household model:
```python
@dataclass
class Household:
    household_id: int
    name: str  # e.g., "Anderson, Bryan & Barbara"
    address: str
    phone: str
    email: str
    adults: List[int]  # member_ids of adults in household
```

## Import Logic

1. **Parse household TSV**:
   - Identify record boundaries (when Name column is non-empty)
   - Extract household name, address, phone, email
   - Parse individual names in "Household Members" column

2. **Match members to household**:
   - Use fuzzy matching to find member records
   - Link members to household_id
   - Identify adults (age >= 18) vs minors (age < 18)

3. **Parent assignment**:
   - For minors in a household, adults in same household are potential parents
   - Could add `parent_member_ids` to Member model (list of member IDs)

## UI Changes Needed

### Member Info Modal:
- Show household name
- If minor: show parent names with clickable links
- If parent: show children in household

### Prayer Assignment:
- When selecting a minor, show parent contact info
- Option to contact parents instead of minor

## Import Script

New command:
```bash
python utils/import_members.py --import-households households.tsv
```

Should:
- Create households.csv if it doesn't exist
- Match household members to existing member records
- Update members.csv with household_id and parent links
- Handle unmatched names gracefully

## Edge Cases

1. **Single parents**: "Anderson, Jack" (only one adult)
2. **Adult children**: Age >= 18 living at home
3. **Multiple generations**: Grandparents, parents, children
4. **Name variations**: "Bryan" vs "Brian", "Jack" vs "John"
5. **Missing members**: Names in household not in member database
6. **Ambiguous surnames**: Multiple families with same last name

## Future Enhancements

- Household view page showing all members
- Family photo/image support
- Household notes/flags
- Emergency contact information
- Preferred contact method per household

## Implementation Priority

**Phase 1 (Now)**:
- Add age display to modal ✅
- Add "(minor)" indicator for age < 18 ✅

**Phase 2 (Next)**:
- Add household_id to Member model
- Create Household model and CSV
- Write household import script
- Update member info modal to show household

**Phase 3 (Future)**:
- Parent linking for minors
- Household management UI
- Contact routing for minors

---

## Sample Implementation

```python
# In utils/import_households.py

def parse_household_tsv(file_path: Path) -> List[dict]:
    """Parse multi-line household records from TSV."""
    households = []
    current = None

    with open(file_path, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row['Name'].strip():
                # New household
                if current:
                    households.append(current)
                current = {
                    'name': row['Name'].strip(),
                    'members': [],
                    'address': '',
                    'phone': row['Phone Number'].strip(),
                    'email': row['E-mail'].strip()
                }

            # Add member names
            members_text = row['Household Members'].strip()
            if members_text:
                current['members'].append(members_text)

            # Accumulate address lines
            addr = row['Address'].strip()
            if addr:
                current['address'] += addr + '\n'

        if current:
            households.append(current)

    return households
```

## Questions to Resolve

1. Should we store parent relationships or just household relationships?
2. How to handle adult siblings vs parent-child?
3. Should minors be excluded from prayer assignments automatically?
4. Contact flow: always contact parents first, or give option?
