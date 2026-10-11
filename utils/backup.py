#!/usr/bin/env python3
"""
Whole-dataset backup and restore for MLS3.

An import rewrites members and households together, and reassigning household
IDs can orphan references between them, so a snapshot covers every data file
rather than members.csv alone.

Snapshots live in $MLS3_DATA_DIR/backups/<YYYYMMDD_HHMMSS>/ (gitignored):

    members.csv
    households.csv
    prayer_assignments.csv
    appointments.csv
    manifest.json      what it was, when, why, and whether it verified

They sit inside the data directory on purpose: when that directory is synced to
cloud storage, the backups go with it and are off the phone without any extra
work. That also means sync mirrors the pruning of old snapshots, so RETENTION is
how much history the off-device copy keeps.

A snapshot is read back with the app's own loaders as soon as it is taken, and
the manifest is written last so that its absence marks a snapshot that never
finished - a snapshot interrupted mid-write, or one copied before it finished
syncing. Neither a damaged nor an unfinished snapshot will be restored; see
Snapshot.restorable.

Usage:
    from utils import backup
    snapshot = backup.create('PDF import')
    backup.restore(snapshot.timestamp)
"""
import csv
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# Keep this many snapshots; older ones are pruned as new ones are taken. An
# import takes two (before and after) and a restore takes one, so this has to
# be comfortably larger than the number of snapshots a confusing session can
# produce, or the window rolls past the last good copy.
#
# The data directory is typically synced to cloud storage, and sync mirrors
# deletions, so this is also how much history the off-device copy keeps. At
# roughly 56KB a snapshot for a 350-member ward, 30 costs under 2MB.
RETENTION = 30

TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


def backup_root() -> Path:
    return config.DATA_DIR / 'backups'


def data_files() -> Dict[str, Path]:
    """The files a snapshot covers, by name."""
    return {
        'members.csv': config.MEMBERS_CSV,
        'households.csv': config.HOUSEHOLDS_CSV,
        'prayer_assignments.csv': config.PRAYER_ASSIGNMENTS_CSV,
        'appointments.csv': config.APPOINTMENTS_CSV,
    }


@dataclass
class Snapshot:
    """One backup on disk."""
    timestamp: str
    path: Path
    reason: str = ''
    created: str = ''
    files: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    notes: Dict[str, str] = field(default_factory=dict)
    # True if every file parsed when the snapshot was taken, False if one did
    # not, None for snapshots from before this was recorded.
    verified: Optional[bool] = None
    verify_problems: List[str] = field(default_factory=list)
    # False when the snapshot was never finished: no manifest, or a file the
    # manifest lists is not on disk. See restorable.
    complete: bool = True
    incomplete_reason: str = ''

    @property
    def label(self) -> str:
        """Human-friendly timestamp, e.g. '12 Sep 2026 at 20:04'."""
        # Snapshots taken in the same second carry a "-2" style suffix, which is
        # not part of the timestamp itself.
        stamp = self.timestamp.split('-', 1)[0]
        try:
            dt = datetime.strptime(stamp, TIMESTAMP_FORMAT)
        except ValueError:
            return self.timestamp
        return dt.strftime('%d %b %Y at %H:%M')

    @property
    def restorable(self) -> bool:
        """
        Whether this snapshot is safe to put back.

        An unfinished snapshot would restore a mismatched set of files, and one
        that failed verification would put the app straight back into recovery
        mode. A snapshot from before verification existed is allowed through.
        """
        return self.complete and self.verified is not False

    @property
    def status(self) -> str:
        if not self.complete:
            return 'incomplete'
        if self.verified is False:
            return 'damaged'
        if self.verified is True:
            return 'verified'
        return 'unverified'

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'label': self.label,
            'reason': self.reason,
            'created': self.created,
            'files': self.files,
            'counts': self.counts,
            'notes': self.notes,
            'verified': self.verified,
            'verify_problems': self.verify_problems,
            'complete': self.complete,
            'incomplete_reason': self.incomplete_reason,
            'restorable': self.restorable,
            'status': self.status,
        }


def _verify(directory: Path, names: List[str]) -> Tuple[bool, List[str], Dict[str, int]]:
    """
    Read back the files just copied, to be sure the snapshot is usable.

    A copy of an already-damaged file is a damaged backup, and because old
    snapshots are pruned, a run of those can push the last good one out of the
    window - and then mirror that to cloud storage. Each file is loaded with
    the same code the app uses, so anything the app would reject is caught here.
    """
    # Imported lazily: models is a heavier import and this keeps `backup` usable
    # from contexts that only need to list snapshots.
    from models import (
        AppointmentDatabase, DataIntegrityError, HouseholdDatabase,
        MemberDatabase, PrayerAssignmentDatabase,
    )

    loaders = {
        'members.csv': (MemberDatabase, 'members'),
        'households.csv': (HouseholdDatabase, 'households'),
        'prayer_assignments.csv': (PrayerAssignmentDatabase, 'assignments'),
        'appointments.csv': (AppointmentDatabase, 'appointments'),
    }

    problems: List[str] = []
    counts: Dict[str, int] = {}

    for name in names:
        loader = loaders.get(name)
        if loader is None:
            continue
        cls, attribute = loader
        try:
            db = cls(csv_path=directory / name)
            counts[name] = len(getattr(db, attribute))
        except DataIntegrityError as e:
            problems.append(f"{name}: {e}")
        except (OSError, ValueError) as e:
            problems.append(f"{name}: could not be read back ({e})")

    return (not problems), problems, counts


def create(reason: str = '', notes: Dict[str, str] = None) -> Optional[Snapshot]:
    """
    Snapshot every data file that exists, then read it back to check it.

    Returns None when there is nothing to back up (a first run with no data
    files yet), which is not an error. A snapshot that fails verification is
    kept but marked, and will not be offered for restore.
    """
    present = {name: path for name, path in data_files().items() if path.exists()}
    if not present:
        return None

    now = datetime.now()
    timestamp = now.strftime(TIMESTAMP_FORMAT)
    target = backup_root() / timestamp

    # A second snapshot inside the same second would otherwise overwrite the
    # first; give it a suffix rather than losing it.
    suffix = 1
    while target.exists():
        suffix += 1
        timestamp = f"{now.strftime(TIMESTAMP_FORMAT)}-{suffix}"
        target = backup_root() / timestamp

    target.mkdir(parents=True)
    for name, path in present.items():
        shutil.copy2(path, target / name)

    verified, problems, parsed_counts = _verify(target, sorted(present))

    snapshot = Snapshot(
        timestamp=timestamp,
        path=target,
        reason=reason,
        created=now.isoformat(timespec='seconds'),
        files=sorted(present),
        counts=parsed_counts or {name: _row_count(path) for name, path in present.items()},
        notes=dict(notes or {}),
        verified=verified,
        verify_problems=problems,
    )

    # The manifest is written last, so its presence is what marks a snapshot as
    # finished. A snapshot interrupted here - or caught mid-upload by cloud
    # sync - has no manifest and will not be offered for restore.
    (target / 'manifest.json').write_text(
        json.dumps(snapshot.to_dict(), indent=2), encoding='utf-8'
    )

    prune()
    return snapshot


def list_snapshots() -> List[Snapshot]:
    """Every snapshot on disk, newest first."""
    root = backup_root()
    if not root.exists():
        return []

    snapshots = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        snapshots.append(_read_snapshot(entry))
    return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)


def get(timestamp: str) -> Optional[Snapshot]:
    path = backup_root() / timestamp
    if not _is_snapshot_dir(path):
        return None
    return _read_snapshot(path)


def restore(timestamp: str) -> Snapshot:
    """
    Put a snapshot's files back.

    Takes its own snapshot first, so restoring is itself undoable.
    """
    snapshot = get(timestamp)
    if snapshot is None:
        raise ValueError(f"No backup named {timestamp!r} was found.")

    if not snapshot.complete:
        raise ValueError(
            f"The backup from {snapshot.label} cannot be restored because "
            f"{snapshot.incomplete_reason}. Restoring it would leave your "
            f"files out of step with each other. Choose a different backup."
        )

    if snapshot.verified is False:
        detail = snapshot.verify_problems[0] if snapshot.verify_problems else ''
        raise ValueError(
            f"The backup from {snapshot.label} was damaged when it was taken, "
            f"so restoring it would not help. {detail} Choose a different backup."
        )

    create(reason=f'Before restoring {snapshot.label}')

    restored = []
    for name, destination in data_files().items():
        source = snapshot.path / name
        if not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored.append(name)

    if not restored:
        raise ValueError(f"Backup {snapshot.label} contains no data files.")
    return snapshot


def prune(keep: int = RETENTION) -> List[str]:
    """
    Delete all but the newest `keep` snapshots. Returns what was removed.

    The newest verified snapshot is never deleted, even if it has aged out of
    the window: it is the last copy known to be readable, and a run of newer
    snapshots taken over damaged data must not be able to evict it.
    """
    snapshots = list_snapshots()
    keepers = {s.timestamp for s in snapshots[:keep]}

    newest_good = next((s for s in snapshots if s.verified is True), None)
    if newest_good is not None:
        keepers.add(newest_good.timestamp)

    removed = []
    for snapshot in snapshots:
        if snapshot.timestamp in keepers:
            continue
        shutil.rmtree(snapshot.path, ignore_errors=True)
        removed.append(snapshot.timestamp)
    return removed


def _is_snapshot_dir(path: Path) -> bool:
    """Guard against a caller passing '..' or an arbitrary path as a timestamp."""
    if not path.is_dir():
        return False
    try:
        return path.resolve().parent == backup_root().resolve()
    except OSError:
        return False


def _read_snapshot(path: Path) -> Snapshot:
    snapshot = Snapshot(timestamp=path.name, path=path)
    on_disk = sorted(p.name for p in path.glob('*.csv'))

    manifest = path / 'manifest.json'
    if not manifest.exists():
        # The manifest is written last, so there is no way to know whether the
        # CSVs beside it are all there.
        snapshot.files = on_disk
        snapshot.counts = {p.name: _row_count(p) for p in path.glob('*.csv')}
        snapshot.complete = False
        snapshot.incomplete_reason = (
            "it has no manifest, so it was never finished - either interrupted "
            "while being written, or copied before it finished syncing"
        )
        return snapshot

    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        snapshot.files = on_disk
        snapshot.complete = False
        snapshot.incomplete_reason = "its manifest could not be read"
        return snapshot

    snapshot.reason = data.get('reason', '')
    snapshot.created = data.get('created', '')
    snapshot.counts = data.get('counts', {})
    snapshot.notes = data.get('notes', {})
    snapshot.verified = data.get('verified')
    snapshot.verify_problems = data.get('verify_problems', [])
    snapshot.files = data.get('files') or on_disk

    # Every file the manifest promised has to actually be there - a partly
    # synced snapshot would otherwise restore a mismatched set.
    missing = [name for name in snapshot.files if not (path / name).exists()]
    if missing:
        snapshot.complete = False
        snapshot.incomplete_reason = (
            f"{', '.join(missing)} is missing from it, so only part of the "
            f"snapshot is present"
        )

    if not snapshot.counts:
        snapshot.counts = {p.name: _row_count(p) for p in path.glob('*.csv')}
    return snapshot


def _row_count(path: Path) -> int:
    """
    Data rows in a CSV, excluding the header.

    Parsed rather than line-counted: household addresses are multi-line and sit
    inside quoted fields, so one row can span several lines.
    """
    try:
        with open(path, 'r', newline='', encoding='utf-8') as f:
            return max(sum(1 for _ in csv.reader(f)) - 1, 0)
    except (OSError, csv.Error):
        return 0


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == 'restore':
        result = restore(sys.argv[2])
        print(f"Restored {result.label}")
    elif len(sys.argv) > 1 and sys.argv[1] == 'create':
        result = create(reason='Manual')
        print(f"Created {result.timestamp}" if result else "Nothing to back up")
    else:
        for item in list_snapshots():
            counts = ', '.join(f"{k.split('.')[0]}={v}" for k, v in sorted(item.counts.items()))
            print(f"{item.timestamp}  {item.label}  {item.status:<10} "
                  f"{item.reason or '-'}  [{counts}]")
            if not item.complete:
                print(f"    not restorable: {item.incomplete_reason}")
            for problem in item.verify_problems:
                print(f"    {problem}")
