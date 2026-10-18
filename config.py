"""
MLS3 Configuration
"""
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Base directory of the application
BASE_DIR = Path(__file__).parent

# Data directory - defaults to development mock data
# Set MLS3_DATA_DIR environment variable for production
# Example: export MLS3_DATA_DIR=/home/nlod/mls3-data
DATA_DIR = Path(os.getenv('MLS3_DATA_DIR', BASE_DIR / 'data'))

# Flask configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')
HOST = os.getenv('FLASK_HOST', '127.0.0.1')
PORT = int(os.getenv('FLASK_PORT', '5000'))

# Data file paths
MEMBERS_CSV = DATA_DIR / 'members.csv'
HOUSEHOLDS_CSV = DATA_DIR / 'households.csv'
PRAYER_ASSIGNMENTS_CSV = DATA_DIR / 'prayer_assignments.csv'
MESSAGE_TEMPLATES_YAML = DATA_DIR / 'message_templates.yaml'
APPOINTMENT_TYPES_YAML = DATA_DIR / 'appointment_types.yaml'
APPOINTMENTS_CSV = DATA_DIR / 'appointments.csv'

# Application settings
NEXT_CANDIDATE_COUNT = 3  # Number of next-up candidates to show per gender
DATE_FORMAT = '%Y-%m-%d'  # ISO format for CSV storage
DISPLAY_DATE_FORMAT = '%B %d, %Y'  # "February 9, 2026" for display
# The ward's timezone. The UI and text messages always show times here, and
# times typed into the scheduler are read as ward time - wherever the phone is.
# Calendar events carry it too, so Google shows them in each viewer's own zone.
# Set MLS3_TIMEZONE to an IANA name (e.g. America/Phoenix) for another ward.
HOME_TIMEZONE = os.getenv('MLS3_TIMEZONE', 'America/Denver')


def ward_now() -> datetime:
    """The current time in the ward's timezone (timezone-aware)"""
    return datetime.now(ZoneInfo(HOME_TIMEZONE))


def ward_today() -> date:
    """Today's date in the ward - not the phone's, which may be elsewhere"""
    return ward_now().date()

# SMS Configuration
# Set MLS3_DEBUG_SMS=true to print debug messages when sending SMS
DEBUG_SMS = os.getenv('MLS3_DEBUG_SMS', 'false').lower() in ('true', '1', 'yes')
# Set MLS3_DISABLE_SMS=true to skip actual SMS sending (for desktop testing)
DISABLE_SMS = os.getenv('MLS3_DISABLE_SMS', 'false').lower() in ('true', '1', 'yes')
# Set MLS3_TASKER_SMS=true to queue messages for Tasker instead of opening the
# default SMS app directly with Termux's am
TASKER_SMS = os.getenv('MLS3_TASKER_SMS', 'false').lower() in ('true', '1', 'yes')

# Google Calendar Configuration
# Set MLS3_GOOGLE_CALENDAR=true to enable Google Calendar sync
GOOGLE_CALENDAR_ENABLED = os.getenv('MLS3_GOOGLE_CALENDAR', 'false').lower() in ('true', '1', 'yes')
# Google Calendar credentials and token files
CREDENTIALS_FILE = DATA_DIR / 'credentials.json'
TOKEN_FILE = DATA_DIR / 'token.pickle'
# Calendar IDs for Bishop and Counselor schedules
BISHOP_CALENDAR_ID = os.getenv('MLS3_BISHOP_CALENDAR_ID', '')
COUNSELOR_CALENDAR_ID = os.getenv('MLS3_COUNSELOR_CALENDAR_ID', '')
