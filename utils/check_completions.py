#!/usr/bin/env python3
"""
Check Google Sheet for appointment completions (POC only)
This demonstrates what auto-sync would do in Phase 3
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle

def get_sheets_service():
    """Get authenticated Google Sheets service"""
    creds = None

    # Load credentials from token file (same OAuth as calendar)
    token_path = os.path.expanduser('~/mls3-data/token.pickle')
    if not os.path.exists(token_path):
        token_path = 'token.pickle'

    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        print("ERROR: No valid credentials found")
        print("Run authorize_google_calendar.py first")
        return None

    return build('sheets', 'v4', credentials=creds)

def check_completions(sheet_id):
    """Check Google Sheet for new completions"""

    service = get_sheets_service()
    if not service:
        return []

    try:
        # Read all rows from Completions sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range='Completions!A2:D'  # Skip header row - only 4 columns now
        ).execute()

        values = result.get('values', [])

        if not values:
            print("No completions found in sheet")
            return []

        print(f"\nFound {len(values)} completion(s):\n")
        print("=" * 80)

        completions = []
        for i, row in enumerate(values, start=2):
            # Pad row to ensure all columns exist
            while len(row) < 4:
                row.append('')

            timestamp, calendar_id, event_id, status = row

            completion = {
                'row': i,
                'timestamp': timestamp,
                'calendar_id': calendar_id,
                'event_id': event_id,
                'status': status
            }

            completions.append(completion)

            print(f"Row {i}:")
            print(f"  Timestamp: {timestamp}")
            print(f"  Calendar ID: {calendar_id}")
            print(f"  Event ID: {event_id}")
            print(f"  Status: {status}")
            print()

        print("=" * 80)
        return completions

    except Exception as e:
        print(f"ERROR: Failed to read sheet: {e}")
        return []

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_completions.py <SHEET_ID>")
        print("\nExample:")
        print("  python check_completions.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
        print("\nTo get your Sheet ID:")
        print("  Open Google Sheet in browser")
        print("  Copy ID from URL: https://docs.google.com/spreadsheets/d/SHEET_ID/edit")
        print("\nNote: This uses the same OAuth credentials as Google Calendar")
        print("Run authorize_google_calendar.py first if needed")
        sys.exit(1)

    sheet_id = sys.argv[1]

    print("Checking Google Sheet for completions...")
    print(f"Sheet ID: {sheet_id}\n")

    completions = check_completions(sheet_id)

    if completions:
        print(f"\n✓ Found {len(completions)} completion(s)")
        print("\nIn Phase 3, MLS3 would automatically:")
        print("  1. Read these completions every 5 minutes")
        print("  2. Use Calendar ID + Event ID to find appointment in MLS3")
        print("  3. Update appointment state to 'Completed'")
        print("  4. Mark rows as processed (or delete them)")
        print("\nFor POC: Manually update these appointments in MLS3")
        print("\nTo generate detailed report:")
        print("  Clerk can add a report script to the sheet that:")
        print("  - Reads Calendar ID + Event ID from each row")
        print("  - Fetches the calendar event details")
        print("  - Extracts member name, appointment type, conductor")
        print("  - Creates detailed completion report")
    else:
        print("\nNo completions found")
        print("\nTo test:")
        print("  1. Open test calendar event")
        print("  2. Click completion link")
        print("  3. Run this script again")

if __name__ == '__main__':
    main()
