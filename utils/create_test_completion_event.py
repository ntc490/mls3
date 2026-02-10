#!/usr/bin/env python3
"""
Create a test calendar event with completion tracking links
This is for POC testing of the completion tracking feature
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.google_calendar import GoogleCalendarManager
import config

def create_test_event(web_app_url):
    """Create a test calendar event with completion links"""

    if not config.GOOGLE_CALENDAR_ENABLED:
        print("ERROR: Google Calendar is not enabled")
        print("Set MLS3_GOOGLE_CALENDAR=true and configure calendar IDs")
        return False

    # Initialize calendar manager
    calendar = GoogleCalendarManager()

    # Test appointment details
    member_name = "Test Member"
    member_phone = "801-555-1234"
    appointment_type = "Temple Recommend"
    conductor = "Bishop"

    # We'll get the actual event ID after creating the event
    # For now, we'll use a placeholder in description and update it after creation

    # Tomorrow at 3 PM
    start_time = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0) + timedelta(days=1)
    end_time = start_time + timedelta(minutes=30)

    # Use Bishop calendar for test
    calendar_id = config.BISHOP_CALENDAR_ID

    # Build event description template (we'll add event ID after creation)
    description_template = """Temple Recommend Interview - TEST EVENT

Member: {member_name}
Phone: {member_phone}
Type: {appointment_type}

This is a TEST event for completion tracking POC.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AFTER APPOINTMENT - Record Completion:

Long-press one of the links below and select "Open link":

✓ Completed
{web_app_url}?calendar_id={calendar_id}&event_id={{event_id}}&status=Completed

⊗ No-show
{web_app_url}?calendar_id={calendar_id}&event_id={{event_id}}&status=No-show

⚠ Rescheduled
{web_app_url}?calendar_id={calendar_id}&event_id={{event_id}}&status=Rescheduled

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Instructions:
1. After appointment, LONG-PRESS one of the links above
2. Select "Open link" from menu
3. Browser will open showing confirmation
4. Check Google Sheet "MLS3 Appointment Tracking" for completion record

Note: This is a TEST event. You can delete it after testing.
"""

    # Create event with placeholder description (we'll update it with event ID)
    event = {
        'summary': f'[TEST] {appointment_type} - {member_name}',
        'description': 'Creating event...',  # Temporary
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Denver',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Denver',
        },
        'colorId': '10',  # Green for testing
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 30},
            ],
        },
    }

    try:
        # Create the event first to get the event ID
        created_event = calendar.service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()

        event_link = created_event.get('htmlLink')
        event_id = created_event.get('id')

        # Now update the event with the proper description containing the event ID
        description = description_template.format(
            member_name=member_name,
            member_phone=member_phone,
            appointment_type=appointment_type,
            web_app_url=web_app_url,
            calendar_id=calendar_id,
            event_id=event_id
        )

        # Update the event with the complete description
        created_event['description'] = description
        calendar.service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=created_event
        ).execute()

        print("✓ Test event created successfully!")
        print(f"\nEvent ID: {event_id}")
        print(f"Calendar ID: {calendar_id}")
        print(f"Event Link: {event_link}")
        print(f"\nAppointment Details:")
        print(f"  Member: {member_name}")
        print(f"  Type: {appointment_type}")
        print(f"  Time: {start_time.strftime('%B %d, %Y at %I:%M %p')}")
        print(f"  Duration: 30 minutes")
        print(f"\nCompletion Links Format:")
        print(f"  {web_app_url}?calendar_id={calendar_id}&event_id={event_id}&status=STATUS")
        print(f"\nOpen this event on your phone and LONG-PRESS the completion links to test!")

        return True

    except Exception as e:
        print(f"ERROR: Failed to create test event: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_test_completion_event.py <WEB_APP_URL>")
        print("\nExample:")
        print("  python create_test_completion_event.py https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec")
        print("\nTo get your Web App URL:")
        print("  1. Open Google Sheet 'MLS3 Appointment Tracking'")
        print("  2. Extensions → Apps Script")
        print("  3. Deploy → New deployment → Web app")
        print("  4. Copy the Web App URL")
        sys.exit(1)

    web_app_url = sys.argv[1]

    # Validate URL format
    if not web_app_url.startswith('https://script.google.com/'):
        print("ERROR: Web App URL should start with 'https://script.google.com/'")
        print(f"Got: {web_app_url}")
        sys.exit(1)

    print("Creating test event with completion tracking links...")
    print(f"Web App URL: {web_app_url}\n")

    success = create_test_event(web_app_url)

    if success:
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. Open your Google Calendar")
        print("2. Find the [TEST] event for tomorrow at 3 PM")
        print("3. Click one of the completion links")
        print("4. Verify the Google Sheet records the completion")
        print("5. Test different status options (Completed, No-show, Rescheduled)")
        print("\nWhen done testing, delete the test event from calendar.")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
