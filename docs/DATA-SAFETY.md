# Data Safety

How MLS3 protects the CSV files, and what to do when something looks wrong.

MLS3 runs in Termux on a phone. Android kills background processes whenever it
needs the memory, batteries die, and storage fails. The data store is four CSV
files, so everything below is about making those files hard to lose.

## The problem this solves

`open(path, 'w')` truncates the file immediately and the contents only reappear
as they are written. Kill the process in that window and the file is cut in
half. Worse, a half-written CSV usually still parses: before this work, a
truncated `members.csv` loaded **182 of 364 members with no error at all** and
the app served half the ward as though nothing had happened.

## What is in place

### 1. Atomic writes

Every save goes to `<file>.tmp` in the same directory, is flushed to disk with
`fsync`, and is then moved into place with `os.replace`, which is atomic on
POSIX. A process killed at any point leaves either the complete old file or the
complete new one.

The same mechanism handles a full disk: the failure happens while writing the
temporary file, and the original is never touched.

See `atomic_write`, `staged_write` and `publish` in `models.py`. All four
databases use it. There is a test that every database still does
(`test_every_database_writes_durably`), so a fifth one cannot quietly skip it.

### 2. Damaged files are refused, not half-loaded

On load, each database checks that:

- the file ends with a line terminator, meaning it was not cut off mid-row
- it is not empty
- the columns it depends on are present
- id columns hold numbers, naming the file and line when they do not
- no id appears twice

Any failure raises `DataIntegrityError` rather than loading what it can.

### 3. Recovery mode

If the data cannot be trusted at startup, `app.py` comes up with `DATA_PROBLEM`
set and a `before_request` hook sends every page to `/recovery` and every API
call to a 503 explaining why. The recovery page names the problem and lists the
backups; restoring one reloads everything and, if the restored files are sound,
returns the app to normal. Nothing is served from a file we do not trust.

### 4. Integrity checking

Atomic writes stop a file being half-written. They do not stop data that parses
cleanly but does not hang together, which `utils/check_data.py` looks for:

| | |
|---|---|
| error | duplicate member, household, assignment or appointment ids |
| error | a member in a household that no longer exists |
| error | a prayer assignment or appointment for a member who is gone |
| error | an unrecognised `household_role` |
| error | a member with no name at all |
| warning | an active member with no gender |
| warning | a date not in `YYYY-MM-DD` form |
| warning | a household with members but no head, so parents cannot be resolved |
| warning | a household with nobody in it |
| warning | **records lost since the last backup** |
| warning | a leftover `.tmp` file from an interrupted save |

That second-to-last one matters: a file truncated *exactly* on a row boundary
ends cleanly and every row parses, so the load-time guard cannot see it. The
only thing that notices is the record count being lower than the last backup's.

Run it from the Import page ("Run a check"), from `/api/data/check`, or on the
command line:

```bash
python utils/check_data.py     # exit 0 clean, 1 problems found, 2 unreadable
```

It also runs automatically after every import, and the result is shown on the
import result screen.

### 5. Imports are all-or-nothing

An import rewrites members and households together, and members point at
household ids, so the two must not be left disagreeing. `commit()`:

1. takes a **Before PDF import** backup
2. applies the changes in memory
3. stages *both* files and flushes them to disk - if either write fails,
   nothing has been published and the live data is still the old data
4. writes an `.import-in-progress` marker
5. publishes both files back to back
6. removes the marker
7. takes an **After PDF import** backup
8. runs the integrity check on what it wrote

Two renames cannot be one atomic operation, but the gap between them is
microseconds with no I/O in it. If the process dies there, the marker survives;
at the next startup `check_interrupted_import()` finds it and recovery mode
offers the backup from step 1.

Step 7 matters for more than the count check: backing up only beforehand would
mean damage occurring *after* an import could only be undone by throwing the
import away.

### 6. A write lock

Flask serves requests on threads and the databases are module-level, so two
handlers can save at the same time. Each database holds a `threading.Lock`
around its writes.

## Backups

`$MLS3_DATA_DIR/backups/<timestamp>/` holds all four CSVs plus a `manifest.json`
recording when, why, how many rows of each, and whether the snapshot verified.
Roughly 56 KB per snapshot for a 350-member ward.

```bash
python utils/backup.py                      # list, with status
python utils/backup.py create               # take one now
python utils/backup.py restore <timestamp>  # put one back
```

A restore takes its own backup first, so restoring is itself undoable.

### Off-device copies

Backups live **inside** the data directory, so if `MLS3_DATA_DIR` is synced to
cloud storage the snapshots go with it and are already off the phone. Nothing
extra is needed.

Two consequences of that worth knowing:

- **Sync mirrors deletions.** Retention is 30 snapshots
  (`utils/backup.py: RETENTION`), so the cloud copy is a rolling 30-snapshot
  window rather than an archive. An import takes two and a restore takes one.
- **Bidirectional sync can be surprising.** The app loads at startup and writes
  from memory, so a change arriving *from* the cloud while it is running will be
  overwritten by the next save. Stop the app before editing a CSV on the other
  side.

### Snapshots are checked, and bad ones are refused

Every snapshot is read back with the same loaders the app uses, and the result
recorded in its manifest. `backup.py` shows a status per snapshot:

| status | meaning |
|---|---|
| `verified` | every file parsed when the snapshot was taken |
| `damaged` | a file did not parse - restoring it would not help |
| `incomplete` | no manifest, or a file the manifest lists is missing |
| `unverified` | taken before this check existed; allowed, but unproven |

`restore()` refuses `damaged` and `incomplete` snapshots, the Import and recovery
pages hide the Restore button for them and say why, and the API refuses them even
if asked directly.

`incomplete` is the case cloud sync makes real: the manifest is written **last**,
so a snapshot caught mid-upload - or pulled back onto a new phone before it
finished - has no manifest. Restoring such a snapshot used to succeed and leave
members pointing at household ids from a different era.

Two further guards:

- **`prune()` never deletes the newest verified snapshot**, even once it has aged
  out of the window, so a run of snapshots taken over damaged data cannot evict
  the last copy known to be readable.
- **An import refuses to run if the backup it just took is not restorable**,
  because the import would not be undoable.

## If something looks wrong

1. **The app sends you to a recovery page.** It names the problem. Pick a
   backup and restore it.
2. **The app works but numbers look wrong.** Import page -> "Run a check". If it
   reports records lost since the last backup, restore that backup.
3. **Neither, but you want reassurance.** `python utils/check_data.py`.
4. **You edited a CSV by hand and broke it.** Restore a backup. Hand-editing is
   fine, but leave the trailing newline alone - a file without one is treated as
   truncated.

## Tests

`tests/test_durability.py` covers all of the above by simulating the failures:
`fsync` raising mid-save, truncated and empty and duplicate-id files, three
writer threads racing three reader threads, an interrupted import marker, and a
staging failure during a commit.

```bash
./venv/bin/python -m unittest discover tests
```
