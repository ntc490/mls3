# Google Calendar Integration Setup Guide

This guide will walk you through setting up Google Calendar integration for MLS3.

## Overview

MLS3 can now automatically sync appointments to Google Calendar with:
- Separate calendars for Bishop and Counselor appointments
- Automatic sync when creating/updating/deleting appointments
- Manual sync button for troubleshooting
- State indicators in event descriptions (e.g., "[Draft]", "[Invited]")
- Completed appointments kept as history (not deleted from calendar)

## Prerequisites

- Google Account
- Internet connection
- Browser access (for initial OAuth setup)

## Step 1: Install Dependencies

```bash
cd ~/storage/shared/mls3
source venv/bin/activate
pip install -r requirements.txt
```

This installs the Google Calendar API libraries.

## Step 2: Create Google Cloud Project

1. Go to https://console.cloud.google.com
2. Click "Select a project" → "New Project"
3. Name it "MLS3 Calendar Integration"
4. Click "Create"

## Step 3: Enable Google Calendar API

1. In the Google Cloud Console, select your new project
2. Go to "APIs & Services" → "Library"
3. Search for "Google Calendar API"
4. Click on it and press "Enable"

## Step 4: Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure OAuth consent screen:
   - User Type: External
   - App name: MLS3
   - User support email: Your email
   - Developer contact: Your email
   - Click "Save and Continue" through the remaining screens
4. Back at "Create OAuth client ID":
   - Application type: **Desktop app**
   - Name: MLS3 Desktop
5. Click "Create"
6. In the popup, click "Download JSON"
7. Save the file as `credentials.json`

## Step 5: Copy Credentials to Data Directory

```bash
cp ~/Downloads/credentials.json ~/mls3-data/credentials.json
chmod 600 ~/mls3-data/credentials.json
```

## Step 6: Enable Google Calendar in MLS3

```bash
export MLS3_GOOGLE_CALENDAR=true
```

To make this permanent, add to your `~/.bashrc` or startup script:

```bash
echo 'export MLS3_GOOGLE_CALENDAR=true' >> ~/.bashrc
```

## Step 7: First-Time Authorization

1. Start your Flask app:
   ```bash
   cd ~/storage/shared/mls3
   python app.py
   ```

2. Create or edit an appointment in the web interface

3. The first time you try to sync, it will:
   - Open your browser to Google's consent screen
   - Ask you to log in and grant permissions
   - Redirect to `http://localhost:8080` (handled automatically)
   - Save the token to `~/mls3-data/token.pickle`

4. Future syncs will use the saved token automatically

## Step 8: Set Up Calendar IDs

You have two options: use existing shared calendars, or create new ones.

### Option A: Use Existing Shared Calendars (Recommended if calendars already shared with you)

1. Go to https://calendar.google.com
2. In the left sidebar, find the Bishop and Counselor calendars that were shared with you
3. For each calendar:
   - Click the three dots next to the calendar name
   - Select "Settings and sharing"
   - Scroll down to "Integrate calendar"
   - Copy the "Calendar ID" (looks like `abc123...@group.calendar.google.com`)

4. Set environment variables:
   ```bash
   export BISHOP_CALENDAR_ID="abc123...@group.calendar.google.com"
   export COUNSELOR_CALENDAR_ID="xyz789...@group.calendar.google.com"
   ```

5. Add to `~/.bashrc` to make permanent:
   ```bash
   echo 'export BISHOP_CALENDAR_ID="your_bishop_calendar_id"' >> ~/.bashrc
   echo 'export COUNSELOR_CALENDAR_ID="your_counselor_calendar_id"' >> ~/.bashrc
   ```

**Important**: Make sure the calendars were shared with you with "Make changes to events" permission, not just "See all event details".

### Option B: Create New Calendars (If you need to create your own)

1. In Python, after completing OAuth setup, run:
   ```python
   from utils.google_calendar import get_calendar_service, create_or_get_calendar
   service = get_calendar_service()
   bishop_id = create_or_get_calendar(service, "Bishop Schedule")
   counselor_id = create_or_get_calendar(service, "Counselor Schedule")
   print(f"BISHOP_CALENDAR_ID={bishop_id}")
   print(f"COUNSELOR_CALENDAR_ID={counselor_id}")
   ```

2. Copy the output and add to your environment as shown above

3. Then you can share these calendars with others from Google Calendar settings

## Step 9: Verify Setup

1. Create a test appointment in MLS3
2. Check if it appears in Google Calendar
3. Try the manual "🔄 Sync to Calendar" button
4. Verify both Bishop and Counselor appointments go to correct calendars

## Troubleshooting

### "Calendar integration not enabled"
- Check: `echo $MLS3_GOOGLE_CALENDAR` should print "true"
- Make sure you restarted the Flask app after setting the variable

### "credentials.json not found"
- Verify file exists: `ls -la ~/mls3-data/credentials.json`
- Check permissions: `chmod 600 ~/mls3-data/credentials.json`

### "Calendar ID not configured"
- Set BISHOP_CALENDAR_ID and COUNSELOR_CALENDAR_ID environment variables
- Restart Flask app

### "Failed to sync - offline"
- Check internet connection
- The sync will retry automatically next time you're online

### OAuth consent screen shows "unverified app"
- This is normal for personal apps
- Click "Advanced" → "Go to MLS3 (unsafe)"
- You're authorizing your own app, so it's safe

## Security Notes

- `credentials.json` contains your OAuth client secret - keep it secure
- `token.pickle` contains your access token - keep it secure
- Both files are in `~/mls3-data/` (outside git repository)
- Add them to `.gitignore` if you ever commit the data directory

## Features

### Automatic Sync
- Happens automatically when you:
  - Create new appointment
  - Update appointment details (time, date, duration, type)
  - Change appointment state (Draft → Invited → Accepted → Reminded → Completed)
  - Change conductor (deletes from old calendar, creates in new calendar)
  - Delete non-completed appointments
- Gracefully handles offline/error scenarios (logs to console)

### Manual Sync Button
- Available in appointment editor for all states
- Useful for:
  - Recovery after offline period
  - Fixing sync inconsistencies
  - Re-syncing after errors
- Shows success/failure message

### State Indicators
- Draft appointments: "[Draft] " prefix in calendar title
- Invited appointments: "[Invited] " prefix
- Reminded appointments: "[Reminded] " prefix
- Accepted/Completed: No prefix (clean title)

### Deletion Behavior
- **Non-completed appointments** (Draft, Invited, Accepted, Reminded):
  - Deleted from both MLS3 and Google Calendar
- **Completed appointments**:
  - Deleted from MLS3, but **preserved** in Google Calendar for history
- **Safety**: Only deletes events created by MLS3 (verified via extended properties)

### Safety Features
- MLS3 only modifies/deletes events it created
- All created events marked with `mls3_type: appointment` in extended properties
- Manual calendar events are never touched by MLS3
- Deletion verification checks for MLS3 ownership before removing events

## Disabling Integration

To temporarily disable without removing setup:

```bash
export MLS3_GOOGLE_CALENDAR=false
```

To permanently remove:

```bash
rm ~/mls3-data/credentials.json
rm ~/mls3-data/token.pickle
unset MLS3_GOOGLE_CALENDAR
```

## Advanced: Sharing Calendars

To share the calendars with bishopric members:

1. Go to Google Calendar
2. Find "Bishop Schedule" or "Counselor Schedule"
3. Click three dots → "Settings and sharing"
4. Under "Share with specific people", click "Add people"
5. Enter email addresses
6. Set permission level (e.g., "See all event details")
7. Click "Send"

Note: Extended properties (MLS3 metadata) remain private even when shared.
