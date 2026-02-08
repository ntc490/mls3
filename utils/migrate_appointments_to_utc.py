#!/usr/bin/env python3
"""
Migration script to convert appointment times from local (Mountain Time) to UTC.

This script:
1. Backs up the existing appointments.csv file
2. Reads all appointments
3. Converts date+time from America/Denver timezone to UTC
4. Writes back in ISO 8601 UTC format (datetime_utc field)

Usage:
    python utils/migrate_appointments_to_utc.py
"""
import csv
import shutil
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo


def migrate_appointments():
    """Migrate appointments from local time to UTC"""

    appointments_file = config.APPOINTMENTS_CSV

    if not appointments_file.exists():
        print(f"No appointments file found at {appointments_file}")
        print("Nothing to migrate.")
        return

    # Create backup
    backup_file = appointments_file.with_suffix('.csv.backup')
    print(f"Creating backup: {backup_file}")
    shutil.copy2(appointments_file, backup_file)

    # Read existing appointments
    appointments = []
    with open(appointments_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        # Check if already migrated
        if 'datetime_utc' in fieldnames:
            print("Appointments already migrated (datetime_utc field exists)")
            print("If you want to re-migrate, restore from backup first")
            return

        for row in reader:
            appointments.append(row)

    print(f"Found {len(appointments)} appointments to migrate")

    # Get timezone objects
    home_tz = zoneinfo.ZoneInfo(config.HOME_TIMEZONE)
    utc_tz = zoneinfo.ZoneInfo('UTC')

    # Convert appointments
    migrated_appointments = []
    for appt in appointments:
        # Parse date and time in home timezone
        date_str = appt['date']
        time_str = appt['time']

        if not time_str or time_str.strip() == '':
            print(f"Warning: Appointment {appt['appointment_id']} has no time, skipping")
            continue

        # Create datetime in home timezone
        datetime_str = f"{date_str} {time_str}"
        local_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        local_dt = local_dt.replace(tzinfo=home_tz)

        # Convert to UTC
        utc_dt = local_dt.astimezone(utc_tz)

        # Format as ISO 8601 with Z suffix
        datetime_utc_str = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        print(f"  Appointment {appt['appointment_id']}: {date_str} {time_str} ({config.HOME_TIMEZONE}) → {datetime_utc_str} (UTC)")

        # Create new row
        new_row = {
            'appointment_id': appt['appointment_id'],
            'member_id': appt['member_id'],
            'appointment_type': appt['appointment_type'],
            'datetime_utc': datetime_utc_str,
            'duration_minutes': appt['duration_minutes'],
            'conductor': appt['conductor'],
            'state': appt['state'],
            'created_date': appt['created_date'],
            'last_updated': appt['last_updated'],
            'completed_date': appt.get('completed_date', '')
        }
        migrated_appointments.append(new_row)

    # Write new format
    new_fieldnames = [
        'appointment_id', 'member_id', 'appointment_type', 'datetime_utc',
        'duration_minutes', 'conductor', 'state', 'created_date',
        'last_updated', 'completed_date'
    ]

    print(f"\nWriting {len(migrated_appointments)} migrated appointments to {appointments_file}")
    with open(appointments_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(migrated_appointments)

    print("\nMigration complete!")
    print(f"Backup saved at: {backup_file}")
    print("\nNext steps:")
    print("1. Restart the application")
    print("2. Verify appointments display correctly")
    print(f"3. If there are issues, restore from backup: cp {backup_file} {appointments_file}")


if __name__ == '__main__':
    print("=" * 60)
    print("Appointment Time Migration: Local → UTC")
    print("=" * 60)
    print()

    try:
        migrate_appointments()
    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        print("The original file should still be intact.")
        import traceback
        traceback.print_exc()
        sys.exit(1)
