"""
Google Calendar API Integration
Handles OAuth authentication and calendar event synchronization
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle
import os
from datetime import datetime, timedelta
from typing import Optional
import config

# Google Calendar API scope
SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """
    Get authenticated Google Calendar API service.

    Returns:
        Authorized Calendar service object

    Raises:
        Exception if authentication fails
    """
    creds = None
    token_path = config.TOKEN_FILE
    credentials_path = config.CREDENTIALS_FILE

    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"Google Calendar credentials not found at {credentials_path}. "
            "Please download credentials.json from Google Cloud Console."
        )

    # Load existing token if available
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            creds.refresh(Request())
        else:
            # Run OAuth flow for first-time authorization
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                SCOPES
            )
            # Try to use local server, but handle browser issues on Termux
            try:
                # Attempt to open browser automatically
                # Use port 0 to let the system choose an available port
                creds = flow.run_local_server(port=0, open_browser=True)
            except Exception as e:
                # If browser fails, provide manual instructions
                print("\n" + "="*60)
                print("MANUAL AUTHORIZATION REQUIRED")
                print("="*60)
                print(f"Error opening browser: {e}")
                print("\nPlease follow these steps:")
                print("1. Open this URL in your browser:")
                auth_url, _ = flow.authorization_url()
                print(f"\n{auth_url}\n")
                print("2. Authorize the app")
                print("3. Copy the authorization code from the redirect URL")
                print("="*60)

                # Fall back to console-based flow
                creds = flow.run_console()

        # Save credentials for next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    # Build and return Calendar service
    return build('calendar', 'v3', credentials=creds)


def create_or_get_calendar(service, calendar_name: str, description: str = '') -> str:
    """
    Get calendar ID by name, or create calendar if it doesn't exist.

    Args:
        service: Authenticated Calendar service
        calendar_name: Name of the calendar
        description: Optional description

    Returns:
        Calendar ID string
    """
    # List all calendars
    try:
        calendar_list = service.calendarList().list().execute()

        # Search for calendar by name
        for calendar in calendar_list.get('items', []):
            if calendar['summary'] == calendar_name:
                return calendar['id']

        # Calendar doesn't exist, create it
        calendar = {
            'summary': calendar_name,
            'description': description or f'MLS3 {calendar_name}',
            'timeZone': config.HOME_TIMEZONE
        }

        created = service.calendars().insert(body=calendar).execute()
        return created['id']

    except HttpError as e:
        print(f"Error accessing calendars: {e}")
        raise


class CalendarSync:
    """Handles synchronization between MLS3 appointments and Google Calendar"""

    def __init__(self, service):
        """
        Initialize calendar sync handler.

        Args:
            service: Authenticated Google Calendar service
        """
        self.service = service

    def _get_calendar_id(self, conductor: str) -> str:
        """
        Get appropriate calendar ID based on conductor.

        Args:
            conductor: 'Bishop' or 'Counselor'

        Returns:
            Calendar ID string

        Raises:
            ValueError if calendar ID not configured
        """
        if conductor == 'Bishop':
            calendar_id = config.BISHOP_CALENDAR_ID
            if not calendar_id:
                raise ValueError("BISHOP_CALENDAR_ID not configured")
        elif conductor == 'Counselor':
            calendar_id = config.COUNSELOR_CALENDAR_ID
            if not calendar_id:
                raise ValueError("COUNSELOR_CALENDAR_ID not configured")
        else:
            raise ValueError(f"Unknown conductor: {conductor}")

        return calendar_id

    def sync_appointment(self, appointment, member, old_conductor=None):
        """
        Sync appointment to Google Calendar.
        Creates new event or updates existing one.
        If conductor changed, deletes old event and creates new one.

        Args:
            appointment: Appointment object from models
            member: Member object from models
            old_conductor: Previous conductor value if changed (for moving between calendars)

        Returns:
            Event ID from Google Calendar
        """
        calendar_id = self._get_calendar_id(appointment.conductor)

        # If conductor changed, we need to move the event to a different calendar
        if old_conductor and old_conductor != appointment.conductor and appointment.google_event_id:
            # Delete event from old calendar
            try:
                old_calendar_id = self._get_calendar_id(old_conductor)
                self.service.events().delete(
                    calendarId=old_calendar_id,
                    eventId=appointment.google_event_id
                ).execute()
                print(f"Deleted event from {old_conductor} calendar")
            except HttpError as e:
                if e.resp.status != 404:
                    print(f"Warning: Could not delete old event: {e}")
                # Continue anyway to create new event

            # Clear the event ID so we create a new one
            appointment.google_event_id = None

        if appointment.google_event_id:
            # Update existing event in same calendar
            return self.update_appointment_event(appointment, member, calendar_id)
        else:
            # Create new event
            return self.create_appointment_event(appointment, member, calendar_id)

    def create_appointment_event(self, appointment, member, calendar_id: str) -> str:
        """
        Create new calendar event for appointment.

        Args:
            appointment: Appointment object
            member: Member object
            calendar_id: Google Calendar ID

        Returns:
            Created event ID
        """
        # Get appointment datetime in local timezone
        local_dt = appointment.datetime_local(config.HOME_TIMEZONE)
        end_dt = local_dt + timedelta(minutes=appointment.duration_minutes)

        # Create event summary with state indicator
        if appointment.state in ['Draft', 'Invited']:
            state_prefix = "? "
        elif appointment.state == 'Complete':
            state_prefix = "✓ "
        else:  # Accepted
            state_prefix = ""
        summary = f"{state_prefix}{appointment.appointment_type} - {member.display_name_with_last}"

        # Build event object
        event = {
            'summary': summary,
            'description': (
                f"Appointment: {appointment.appointment_type}\n"
                f"Member: {member.full_name}\n"
                f"State: {appointment.state}\n"
                f"Duration: {appointment.duration_minutes} minutes\n"
                f"\nManaged by MLS3"
            ),
            'start': {
                'dateTime': local_dt.isoformat(),
                'timeZone': config.HOME_TIMEZONE,
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': config.HOME_TIMEZONE,
            },
            'extendedProperties': {
                'private': {
                    'mls3_appointment_id': str(appointment.appointment_id),
                    'mls3_member_id': str(appointment.member_id),
                    'mls3_type': 'appointment',
                    'mls3_state': appointment.state,
                    'mls3_conductor': appointment.conductor
                }
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 60},  # 1 hour before
                ],
            },
        }

        # Create event in calendar
        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()

            return created_event['id']

        except HttpError as e:
            print(f"Error creating calendar event: {e}")
            raise

    def update_appointment_event(self, appointment, member, calendar_id: str) -> str:
        """
        Update existing calendar event for appointment.

        Args:
            appointment: Appointment object
            member: Member object
            calendar_id: Google Calendar ID

        Returns:
            Updated event ID
        """
        # Get appointment datetime in local timezone
        local_dt = appointment.datetime_local(config.HOME_TIMEZONE)
        end_dt = local_dt + timedelta(minutes=appointment.duration_minutes)

        # Create event summary with state indicator
        if appointment.state in ['Draft', 'Invited']:
            state_prefix = "? "
        elif appointment.state == 'Complete':
            state_prefix = "✓ "
        else:  # Accepted
            state_prefix = ""
        summary = f"{state_prefix}{appointment.appointment_type} - {member.display_name_with_last}"

        # Build updated event object
        event = {
            'summary': summary,
            'description': (
                f"Appointment: {appointment.appointment_type}\n"
                f"Member: {member.full_name}\n"
                f"State: {appointment.state}\n"
                f"Duration: {appointment.duration_minutes} minutes\n"
                f"\nManaged by MLS3"
            ),
            'start': {
                'dateTime': local_dt.isoformat(),
                'timeZone': config.HOME_TIMEZONE,
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': config.HOME_TIMEZONE,
            },
            'extendedProperties': {
                'private': {
                    'mls3_appointment_id': str(appointment.appointment_id),
                    'mls3_member_id': str(appointment.member_id),
                    'mls3_type': 'appointment',
                    'mls3_state': appointment.state,
                    'mls3_conductor': appointment.conductor
                }
            },
        }

        # Update event in calendar
        try:
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=appointment.google_event_id,
                body=event
            ).execute()

            return updated_event['id']

        except HttpError as e:
            print(f"Error updating calendar event: {e}")
            raise

    def delete_appointment_event(self, appointment):
        """
        Delete calendar event for appointment.
        Only deletes events that were created by MLS3 (verified by extended properties).

        Args:
            appointment: Appointment object with google_event_id

        Returns:
            True if deleted successfully
        """
        if not appointment.google_event_id:
            return True  # Nothing to delete

        calendar_id = self._get_calendar_id(appointment.conductor)

        try:
            # First, verify this event was created by MLS3
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=appointment.google_event_id
            ).execute()

            # Check for MLS3 marker in extended properties
            extended_props = event.get('extendedProperties', {}).get('private', {})
            if extended_props.get('mls3_type') != 'appointment':
                print(f"WARNING: Event {appointment.google_event_id} not created by MLS3, skipping deletion")
                return False

            # Safe to delete - this is an MLS3-created event
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=appointment.google_event_id
            ).execute()

            return True

        except HttpError as e:
            if e.resp.status == 404:
                # Event already deleted, that's okay
                return True
            print(f"Error deleting calendar event: {e}")
            raise


def is_calendar_enabled() -> bool:
    """Check if Google Calendar integration is enabled and configured"""
    return (
        config.GOOGLE_CALENDAR_ENABLED and
        os.path.exists(config.CREDENTIALS_FILE) and
        config.BISHOP_CALENDAR_ID and
        config.COUNSELOR_CALENDAR_ID
    )


def is_online() -> bool:
    """
    Check if internet connection is available.

    Returns:
        True if online, False if offline
    """
    import socket
    try:
        # Try to connect to Google's DNS server
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False
