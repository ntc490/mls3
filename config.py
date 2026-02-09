"""
MLS3 Configuration
"""
import os
from pathlib import Path

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
PRAYER_ASSIGNMENTS_CSV = DATA_DIR / 'prayer_assignments.csv'
MESSAGE_TEMPLATES_YAML = DATA_DIR / 'message_templates.yaml'
APPOINTMENT_TYPES_YAML = DATA_DIR / 'appointment_types.yaml'
APPOINTMENTS_CSV = DATA_DIR / 'appointments.csv'

# Application settings
NEXT_CANDIDATE_COUNT = 3  # Number of next-up candidates to show per gender
DATE_FORMAT = '%Y-%m-%d'  # ISO format for CSV storage
DISPLAY_DATE_FORMAT = '%B %d, %Y'  # "February 9, 2026" for display
HOME_TIMEZONE = 'America/Denver'  # US Mountain Time - used for migrating legacy appointment times

# SMS Configuration
# Set MLS3_DEBUG_SMS=true to print debug messages when sending SMS
DEBUG_SMS = os.getenv('MLS3_DEBUG_SMS', 'false').lower() in ('true', '1', 'yes')
# Set MLS3_DISABLE_SMS=true to skip actual SMS sending (for desktop testing)
DISABLE_SMS = os.getenv('MLS3_DISABLE_SMS', 'false').lower() in ('true', '1', 'yes')

# Google Calendar Configuration
# Set MLS3_GOOGLE_CALENDAR=true to enable Google Calendar sync
GOOGLE_CALENDAR_ENABLED = os.getenv('MLS3_GOOGLE_CALENDAR', 'false').lower() in ('true', '1', 'yes')
# Google Calendar credentials and token files
CREDENTIALS_FILE = DATA_DIR / 'credentials.json'
TOKEN_FILE = DATA_DIR / 'token.pickle'
# Calendar IDs for Bishop and Counselor schedules
BISHOP_CALENDAR_ID = os.getenv('MLS3_BISHOP_CALENDAR_ID', '')
COUNSELOR_CALENDAR_ID = os.getenv('MLS3_COUNSELOR_CALENDAR_ID', '')
