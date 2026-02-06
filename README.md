# MLS3 - Member Leadership Scheduling System

A church scheduling and communication management tool designed to run in Termux on Android, with desktop development support.

## Features

- **Prayer Scheduling**: Schedule opening and closing prayers for sacrament meetings
- **Fair Rotation**: Automatically tracks last prayer dates to ensure fair rotation
- **SMS Integration**: Generate SMS messages via Android intents (Termux)
- **Mobile-First UI**: Touch-friendly, responsive interface optimized for phone use
- **CSV-Based Data**: Simple, editable data storage with no database required

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

   # Rename example files
   cd ~/mls3-data
   mv members.example.csv members.csv
   mv prayer_assignments.example.csv prayer_assignments.csv
   ```

7. **Run the application:**
   ```bash
   cd ~/storage/shared/mls3
   source venv/bin/activate
   export MLS3_DATA_DIR=~/mls3-data
   python app.py
   ```

8. **Open in browser:**
   ```bash
   termux-open-url http://localhost:5000
   ```

## Data Management

### Separation of Code and Data

- **Code (in git)**: All application code, mock data for development
- **Production Data (outside git)**: Real member data stored separately, never committed

### Data Files

The system uses three main data files:

1. **members.csv** - Member database with names, phone numbers, prayer history
2. **prayer_assignments.csv** - All prayer assignments (past, present, future)
3. **message_templates.yaml** - Customizable SMS message templates

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
├── app.py                       # Flask application entry point
├── models.py                    # Data models (Member, PrayerAssignment)
├── config.py                    # Configuration settings
├── requirements.txt             # Python dependencies
├── templates/                   # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── prayer_scheduler.html
│   └── members_list.html
├── static/
│   └── css/
│       └── style.css           # Mobile-responsive styles
├── data/                        # Mock data (committed to git)
│   ├── members.example.csv
│   ├── prayer_assignments.example.csv
│   └── message_templates.yaml
└── utils/                       # Utility scripts (coming soon)
```

## Configuration

Edit `config.py` or use environment variables:

- `MLS3_DATA_DIR` - Path to data directory (default: `./data`)
- `FLASK_DEBUG` - Enable debug mode (default: `True`)
- `FLASK_HOST` - Host address (default: `127.0.0.1`)
- `FLASK_PORT` - Port number (default: `5000`)
- `SECRET_KEY` - Flask secret key (change in production)

## Current Status

### ✅ Phase 1 Complete - Prayer Scheduling System Ready for Production!

**Completed Features:**
- ✅ Phase 1a: Core Infrastructure
- ✅ Phase 1b: Member Database & Import
- ✅ Phase 1c: Prayer Scheduler UI
- ✅ Phase 1d: Candidate Selection Algorithm
- ✅ Phase 1e: SMS Integration
- ✅ Phase 1f: State Management & Workflow
- ✅ Phase 1g: Active Queue & Multi-Week Support
- ✅ Phase 1h: Mobile Optimization & Polish
- ✅ Phase 1i: Documentation & Deployment

**Ready to Use:**
- Full prayer scheduling workflow
- Fair rotation candidate selection
- SMS invitations and reminders
- Multi-week planning with active queue
- Mobile-optimized interface
- Termux deployment support

## Development

### Running in Development Mode

```bash
source venv/bin/activate

# Enable SMS debug mode (skips actual SMS sending, prints to console)
export MLS3_DEBUG_SMS=true

python app.py
```

Access at `http://localhost:5000`

**SMS Debug Mode**: When `MLS3_DEBUG_SMS=true`, clicking Invite or Remind buttons will:
- Skip opening the SMS app
- Print the message to console instead
- Still update the assignment state as if sent
- Great for testing on desktop without Termux

### Available Routes

- `/` - Homepage with system overview
- `/members` - List of all active members (for testing)
- `/prayer-scheduler` - Main prayer scheduling interface
- `/api/members/search?q=<query>` - Search members API

## Contributing

See `mls-master-plan.md` for detailed development roadmap and architecture.

## License

Private project for personal church use.

## Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete Termux deployment guide
- **[TESTING.md](TESTING.md)** - Testing checklist for verification
- **[mls-master-plan.md](mls-master-plan.md)** - System architecture and design
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
See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete setup guide.

Quick start:
```bash
cd ~/storage/shared/mls3
export MLS3_DATA_DIR=~/mls3-data
./start.sh
```

## Support

- **Deployment Issues**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Testing**: See [TESTING.md](TESTING.md)
- **Architecture**: See [mls-master-plan.md](mls-master-plan.md)
- **Questions**: Create an issue in the repository
