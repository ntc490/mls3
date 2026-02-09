# Import Script Quick Reference

Complete guide for using the `import_members.py` utility.

## Basic Usage

```bash
python utils/import_members.py [FILE] [OPTIONS]
```

## Import Modes

### 1. Import Member Data

**File Format:** Tab-separated with header row
```
Name	Gender	Age	Birth Date	Phone Number	E-mail
Smith, John	M	45	15 Mar 1980	801-555-0101	john@example.com
```

**Required Columns:**
- `Name` - Format: "Last, First"
- `Gender` - M or F
- `Birth Date` - Format: "5 Dec 1953" or similar
- `Phone Number` - Any format

**Commands:**
```bash
# Basic import (add new, update existing)
python utils/import_members.py church_export.csv

# Preview changes without saving
python utils/import_members.py church_export.csv --dry-run

# Mark present members active, absent as inactive
python utils/import_members.py church_export.csv --activate-present --deactivate-absent
```

**What It Does:**
- ✅ Adds new members
- ✅ Updates phone, birthday, gender for existing members
- ✅ Preserves prayer history, notes, and don't_ask flags
- ✅ Default: leaves active/inactive status unchanged

### 2. Import Prayer Dates

**File Format:** Tab-separated with header row
```
Name	Prayed
Smith, John	12-15-2023
Johnson, Mary	1/20/2024o
Williams, Robert	2024-02-10c
```

**Columns:**
- `Name` - "Last, First" OR "First Last"
- `Prayed` - Date in various formats (MM-DD-YYYY, M/D/YYYY, etc.)
  - Can include trailing markers: c (closing), o (opening), ? (undecided)

**Commands:**
```bash
# Import prayer dates
python utils/import_members.py --update-prayed prayer_history.csv

# Preview first
python utils/import_members.py --update-prayed prayer_history.csv --dry-run
```

**Note:** Prayer date imports also use fuzzy name matching (see Don't Ask section above).

**Supported Date Formats:**
- 12-15-2023 (MM-DD-YYYY)
- 12/5/2023 (M/D/YYYY)
- 2023-12-05 (YYYY-MM-DD)
- Dec 5, 2023 (Month DD, YYYY)
- 5 Dec 2023 (DD Month YYYY)
- Plus all of the above with trailing c, o, or ?

### 3. Manage Don't Ask Flags

**File Format:** Tab-separated with header row
```
Name
Brown, Patricia
Davis, Emily
```

**Columns:**
- `Name` - "Last, First" OR "First Last"

**Commands:**
```bash
# Mark members as "don't ask for prayers"
python utils/import_members.py --dont-ask dont_ask_list.csv

# Re-enable members for prayer assignments
python utils/import_members.py --do-ask can_ask_list.csv

# Preview first
python utils/import_members.py --dont-ask dont_ask_list.csv --dry-run
```

**Fuzzy Matching:**
Names are matched fuzzily - all words in your query must match the start of words in the member's name:
- "Autumn Wood" matches "Autumn Sally Wood" ✅
- "Wood, Autumn" matches "Autumn Sally Wood" ✅
- "Sally Wood" matches "Autumn Sally Wood" ✅
- "Autumn" matches "Autumn Sally Wood" ✅
- "John Smi" matches "John Smith" ✅

## Query Commands

### Show Don't Ask Members

List all members marked with dont_ask_prayer=True:
```bash
python utils/import_members.py --show-dont-ask

# Prefix matching works too
python utils/import_members.py --show-d
```

**Output:**
```
=== Members with Don't Ask Flag ===
Total: 3

  Brown, Patricia (F) - active
  Davis, Emily (F) - active
  Wilson, James (M) - inactive
```

### Show Inactive Members

List all members marked with active=False:
```bash
python utils/import_members.py --show-inactive

# Prefix matching works too
python utils/import_members.py --show-i
```

**Output:**
```
=== Inactive Members ===
Total: 2

  Anderson, Jessica (F) [DON'T ASK]
  Wilson, James (M)
```

## Common Options

### `--dry-run`
Preview changes without saving to database
```bash
python utils/import_members.py FILE --dry-run
```

### `--no-backup`
Skip creating backup before import (not recommended)
```bash
python utils/import_members.py FILE --no-backup
```

### `--delimiter CHAR`
Use different delimiter (default: tab)
```bash
python utils/import_members.py FILE --delimiter ","
```

### `--activate-present`
Mark members in import file as active=True
```bash
python utils/import_members.py FILE --activate-present
```

### `--deactivate-absent`
Mark members NOT in import file as active=False
```bash
python utils/import_members.py FILE --deactivate-absent
```

## Example Files

See `data/` directory for examples:
- `sample_church_export.tsv` - Member import format
- `sample_prayer_dates.tsv` - Prayer date import format
- `sample_dont_ask.tsv` - Don't ask flag format

## Output

The script provides detailed feedback:

```
Loading existing member database from: members.csv
Current members: 30
Backup created: backups/members_backup_20260206_151030.csv

Importing from: church_export.csv
Delimiter: '\t'
Field mapping: {...}

Loaded 25 members from church CSV

  Updated: John Smith → phone changed
  Updated: Mary Johnson → birthday changed

=== Import Results ===
Added:     2 new members
Updated:   2 existing members
Unchanged: 21 members
Activated: 0 members
Deactivated: 0 members

Changes saved to: members.csv
```

### Not Found Names

If names don't match, they're listed at the end:
```
Names not found in database:
  - Smith, Jane
  - Doe, John
```

**Common Reasons:**
- Spelling differences
- Nickname vs full name
- Name changes (marriage, etc.)
- Member moved away (inactive)

**Solutions:**
- Check spelling in both files
- Use fuzzy search in app to find correct name
- Manually update CSV if needed

## Troubleshooting

### Wrong File Format

**Error:** "CSV must have 'Name' column"

**Fix:**
- Check header row exists
- Verify column name is exactly "Name" (case-insensitive)
- Make sure file is tab-separated

### No Members Imported

**Check:**
1. File format (tab vs comma separated)
2. Header row present
3. Name format ("Last, First")
4. Run with `--dry-run` to see what would happen

### Import Creates Duplicates

**Cause:** Name matching failed

**Fix:**
- Names must match exactly (case-insensitive)
- Check for extra spaces
- Use "Last, First" format consistently

## Tips

1. **Prefix matching works** - You can use `--show-d` instead of `--show-dont-ask`, `--dry` instead of `--dry-run`, etc. (as long as it's unambiguous)
2. **Always use --dry-run first** to preview changes
3. **Backups are automatic** unless you use --no-backup
4. **Names are flexible** - "Last, First" or "First Last" both work
5. **Date formats are flexible** - many formats accepted
6. **Check the end of output** for unmatched names
7. **Use sample files** in data/ directory as templates

## Getting Help

```bash
# Show all options
python utils/import_members.py --help
```

For more information, see:
- README.md - Quick start guide
- DEPLOYMENT.md - Full deployment guide
- TESTING.md - Testing procedures
