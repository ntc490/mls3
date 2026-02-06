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

To import member data from your church's website:

1. Download CSV from church website
2. Use the import utility (coming in Phase 1b):
   ```bash
   python utils/import_members.py church_export.csv
   ```

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

**Phase 1a: Core Infrastructure - COMPLETE ✅**

- Flask app running with basic routing
- CSV data models for members and assignments
- Mobile-responsive UI foundation
- Mock data for development
- Data separation strategy implemented

**Next Steps:**
- Phase 1b: Member database and import functionality
- Phase 1c: Prayer scheduler UI with editable bubbles
- Phase 1d: Candidate selection algorithm
- Phase 1e: SMS integration

## Development

### Running in Development Mode

```bash
source venv/bin/activate
python app.py
```

Access at `http://localhost:5000`

### Available Routes

- `/` - Homepage with system overview
- `/members` - List of all active members (for testing)
- `/prayer-scheduler` - Main prayer scheduling interface
- `/api/members/search?q=<query>` - Search members API

## Contributing

See `mls-master-plan.md` for detailed development roadmap and architecture.

## License

Private project for personal church use.

## Support

For issues or questions, refer to the master plan document or create an issue in the repository.
