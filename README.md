# MLS3 - Member Leadership Scheduling System

A church scheduling and communication management tool designed to run in Termux on Android, with desktop development support.

## Features

### Prayer Scheduling
- **Prayer Scheduling**: Schedule opening and closing prayers for sacrament meetings
- **Fair Rotation**: Automatically tracks last prayer dates to ensure fair rotation
- **Multi-Week Planning**: Plan multiple weeks in advance with active queue
- **SMS Integration**: Generate SMS messages via Android intents (Termux)

### Appointment Management
- **Appointment Scheduling**: Schedule appointments with members (Temple Recommend, Youth Interviews, Callings, etc.)
- **Configurable Types**: Fully customizable appointment types with default durations
- **State Workflow**: Track appointments through Draft → Invited → Reminded → Completed
- **Conductor Assignment**: Separate appointments for Bishop and Counselor

### Google Calendar Integration
- **Auto-Sync**: Appointments automatically sync to Google Calendar
- **Separate Calendars**: Bishop and Counselor appointments in different calendars
- **State Indicators**: Visual indicators for appointment states in calendar
- **Smart Deletion**: Preserves completed appointments as history
- **Manual Sync**: Optional manual sync button for troubleshooting

### General Features
- **Mobile-First UI**: Touch-friendly, responsive interface optimized for phone use
- **CSV-Based Data**: Simple, editable data storage with no database required
- **Timezone Support**: Proper UTC/local timezone handling for appointments
- **Smart Templates**: Powerful template system for SMS messages

## Quick Start

### Development Setup (Desktop)

1. **Clone the repository:**
   ```bash
   cd /home/nlod/claude/mls3
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Open in browser:**
   Navigate to `http://localhost:5000`

### Production Setup (Termux on Android)

1. **Install Termux and Termux:API from F-Droid**

2. **Install Python and dependencies:**
   ```bash
   pkg install python
   pkg install termux-api
   ```

3. **Clone repository:**
   ```bash
   cd ~/storage/shared
   git clone <repository-url> mls3
   cd mls3
   ```

4. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Set up production data directory:**
   ```bash
   mkdir -p ~/mls3-data
   export MLS3_DATA_DIR=~/mls3-data
   ```

6. **Copy initial data files:**
   ```bash
   cp data/*.example.csv ~/mls3-data/
   cp data/message_templates.yaml ~/mls3-data/
   cp data/appointment_types.yaml ~/mls3-data/

   # Rename example files
   cd ~/mls3-data
   mv members.example.csv members.csv
   mv prayer_assignments.example.csv prayer_assignments.csv
   ```

7. **(Optional) Set up Google Calendar integration:**
   See **[docs/GOOGLE_CALENDAR_SETUP.md](docs/GOOGLE_CALENDAR_SETUP.md)** for complete instructions.

   ```bash
   # Enable Google Calendar
   export MLS3_GOOGLE_CALENDAR=true
   export BISHOP_CALENDAR_ID="your_bishop_calendar_id"
   export COUNSELOR_CALENDAR_ID="your_counselor_calendar_id"
   ```

8. **Run the application:**
   ```bash
   cd ~/storage/shared/mls3
   source venv/bin/activate
   export MLS3_DATA_DIR=~/mls3-data
   python app.py
   ```

9. **Open in browser:**
   ```bash
   termux-open-url http://localhost:5000
   ```

## Data Management

### Separation of Code and Data

- **Code (in git)**: All application code, mock data for development
- **Production Data (outside git)**: Real member data stored separately, never committed

### Data Files

The system uses five main data files:

1. **members.csv** - Member database with names, phone numbers, prayer history
2. **prayer_assignments.csv** - All prayer assignments (past, present, future)
3. **appointments.csv** - Appointment tracking database
4. **message_templates.yaml** - Customizable SMS message templates
5. **appointment_types.yaml** - Configurable appointment types with default durations

### Using Mock Data (Development)

By default, the app uses mock data from `./data/`:

```bash
python app.py
# Uses ./data/members.example.csv (automatically copied to members.csv)
```

### Using Real Data (Production)

Set the `MLS3_DATA_DIR` environment variable:

```bash
export MLS3_DATA_DIR=/home/nlod/mls3-data
python app.py
# Uses /home/nlod/mls3-data/members.csv
```

### Importing Church Data

The import utility supports multiple modes for managing member data:

#### **Import Member Data**
Download tab-separated data from your church website with these columns:
- Name (format: "Last, First")
- Gender (M or F)
- Birth Date (format: "5 Dec 1953")
- Phone Number (format: "801-555-1234")

```bash
# Import members (updates existing, adds new)
python utils/import_members.py church_export.csv

# Preview changes without saving
python utils/import_members.py church_export.csv --dry-run

# Mark members in import as active, others as inactive (sync mode)
python utils/import_members.py church_export.csv --activate-present --deactivate-absent
```

#### **Import Prayer Dates**
Tab-separated file with columns: Name, Prayed
```bash
python utils/import_members.py --update-prayed prayer_history.csv
```

#### **Import Don't Ask Flags**
Tab-separated file with single Name column:
```bash
# Mark members as "don't ask for prayers"
python utils/import_members.py --dont-ask dont_ask_list.csv

# Re-enable members for prayer assignments
python utils/import_members.py --do-ask can_ask_list.csv
```

**See `data/sample_*.csv` for example file formats.**

### Backing Up Data

Your production data directory should be backed up regularly:

```bash
# Manual backup
cp -r ~/mls3-data ~/mls3-data-backup-$(date +%Y%m%d)

# Or sync to cloud storage
cp -r ~/mls3-data ~/storage/shared/Dropbox/mls3-backup/
```

## Project Structure

```
mls3/
├── app.py                           # Flask application entry point
├── models.py                        # Data models (Member, PrayerAssignment, Appointment)
├── config.py                        # Configuration settings
├── requirements.txt                 # Python dependencies
├── authorize_google_calendar.py     # OAuth setup for Google Calendar
├── templates/                       # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── prayer_scheduler.html
│   ├── appointment_scheduler.html
│   ├── events.html
│   ├── members_list.html
│   └── sms_composer.html
├── static/
│   ├── css/
│   │   └── style.css               # Mobile-responsive styles
│   └── js/
│       ├── appointment_scheduler.js
│       ├── events.js
│       └── home.js
├── data/                            # Mock data (committed to git)
│   ├── members.example.csv
│   ├── prayer_assignments.example.csv
│   ├── message_templates.yaml
│   └── appointment_types.yaml
├── utils/                           # Utility scripts
│   ├── import_members.py
│   ├── candidate_selector.py
│   ├── sms_handler.py
│   ├── template_expander.py
│   └── google_calendar.py          # Google Calendar integration
└── docs/                            # Documentation
    ├── DEPLOYMENT.md
    ├── TESTING.md
    ├── GOOGLE_CALENDAR_SETUP.md
    └── mls-master-plan.md
```

## Configuration

Edit `config.py` or use environment variables:

### General Settings
- `MLS3_DATA_DIR` - Path to data directory (default: `./data`)
- `FLASK_DEBUG` - Enable debug mode (default: `True`)
- `FLASK_HOST` - Host address (default: `127.0.0.1`)
- `FLASK_PORT` - Port number (default: `5000`)
- `SECRET_KEY` - Flask secret key (change in production)

### SMS Settings
- `MLS3_DEBUG_SMS` - Debug mode (prints SMS instead of sending, default: `false`)
- `MLS3_DISABLE_SMS` - Disable SMS completely (default: `false`)

### Google Calendar Settings
- `MLS3_GOOGLE_CALENDAR` - Enable Google Calendar sync (default: `false`)
- `BISHOP_CALENDAR_ID` - Google Calendar ID for Bishop appointments
- `COUNSELOR_CALENDAR_ID` - Google Calendar ID for Counselor appointments

## Current Status

### ✅ Phase 1 Complete - Prayer Scheduling System
- ✅ Core Infrastructure
- ✅ Member Database & Import
- ✅ Prayer Scheduler UI
- ✅ Candidate Selection Algorithm
- ✅ SMS Integration
- ✅ State Management & Workflow
- ✅ Active Queue & Multi-Week Support
- ✅ Mobile Optimization & Polish
- ✅ Documentation & Deployment

### ✅ Phase 2 Complete - Appointment Management
- ✅ Appointment data model with UTC timezone support
- ✅ Appointment types (Temple Recommend, Youth Interviews, Callings, etc.)
- ✅ Appointment scheduler UI with state workflow
- ✅ Google Calendar integration with OAuth
- ✅ Separate Bishop/Counselor calendars
- ✅ Auto-sync on create/update/delete/state change
- ✅ Smart deletion (preserves completed appointments)
- ✅ Manual sync button
- ✅ Timezone bug fixes and proper UTC/local handling
- ✅ Mobile-optimized calendar event colors

### 📋 Phase 3 Planned - Completion Tracking
- Conductor completion links in calendar events
- Google Sheet integration for clerk reports
- Self-service reporting without MLS3 access

**Ready to Use:**
- Full prayer scheduling workflow
- Full appointment scheduling workflow
- Fair rotation candidate selection
- SMS invitations and reminders
- Multi-week prayer planning with active queue
- Google Calendar integration (optional)
- Mobile-optimized interface
- Termux deployment support

## Development

### Running in Development Mode

```bash
source venv/bin/activate

# Enable SMS debug mode (skips actual SMS sending, prints to console)
export MLS3_DEBUG_SMS=true

# Optional: Enable Google Calendar (requires setup)
export MLS3_GOOGLE_CALENDAR=true

python app.py
```

Access at `http://localhost:5000`

**SMS Debug Mode**: When `MLS3_DEBUG_SMS=true`, clicking Invite or Remind buttons will:
- Skip opening the SMS app
- Print the message to console instead
- Still update the assignment/appointment state as if sent
- Great for testing on desktop without Termux

### Available Routes

- `/` - Homepage with system overview
- `/members` - List of all active members
- `/prayer-scheduler` - Prayer scheduling interface
- `/appointment-scheduler` - Appointment scheduling interface
- `/events` - Calendar view of all events
- `/sms-composer` - Standalone SMS message composer
- `/api/members/search?q=<query>` - Search members API
- `/api/appointments/...` - Appointment management API
- `/api/prayers/...` - Prayer assignment API

## Contributing

See `docs/mls-master-plan.md` for detailed development roadmap and architecture.

## License

Private project for personal church use.

## Documentation

- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Complete Termux deployment guide
- **[docs/TESTING.md](docs/TESTING.md)** - Testing checklist for verification
- **[docs/GOOGLE_CALENDAR_SETUP.md](docs/GOOGLE_CALENDAR_SETUP.md)** - Google Calendar integration setup
- **[docs/COMPLETION_TRACKING_PLAN.md](docs/COMPLETION_TRACKING_PLAN.md)** - Future: Completion tracking system
- **[docs/mls-master-plan.md](docs/mls-master-plan.md)** - System architecture and design
- **[README.md](README.md)** - This file (quick start guide)

## Getting Started

### For Development (Desktop)
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export MLS3_DEBUG_SMS=true
python app.py
```

### For Production (Termux)
See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for complete setup guide.

Quick start:
```bash
cd ~/storage/shared/mls3
export MLS3_DATA_DIR=~/mls3-data
./start.sh
```

### For Google Calendar Integration
See **[docs/GOOGLE_CALENDAR_SETUP.md](docs/GOOGLE_CALENDAR_SETUP.md)** for complete setup guide.

## Support

- **Deployment Issues**: See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Testing**: See [docs/TESTING.md](docs/TESTING.md)
- **Google Calendar**: See [docs/GOOGLE_CALENDAR_SETUP.md](docs/GOOGLE_CALENDAR_SETUP.md)
- **Architecture**: See [docs/mls-master-plan.md](docs/mls-master-plan.md)
- **Questions**: Create an issue in the repository
