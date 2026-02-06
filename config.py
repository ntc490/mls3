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

# Application settings
NEXT_CANDIDATE_COUNT = 3  # Number of next-up candidates to show per gender
DATE_FORMAT = '%Y-%m-%d'  # ISO format for CSV storage
DISPLAY_DATE_FORMAT = '%B %d, %Y'  # "February 9, 2026" for display
