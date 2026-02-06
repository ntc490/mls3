# MLS3 Deployment Guide for Termux

Complete guide for deploying MLS3 on your Android phone using Termux.

---

## Prerequisites

### 1. Install Termux
Download and install from **F-Droid** (not Google Play):
- Visit https://f-droid.org/
- Search for "Termux"
- Install Termux and Termux:API

**Important**: Termux from Google Play is outdated and won't work properly.

### 2. Grant Permissions
After installing Termux:API, grant it SMS and other permissions:
- Open Android Settings → Apps → Termux:API
- Enable all requested permissions

---

## Initial Setup

### 1. Open Termux and Update Packages

```bash
pkg update && pkg upgrade
```

### 2. Install Required Packages

```bash
# Install Python
pkg install python

# Install Git
pkg install git

# Install Termux:API tools
pkg install termux-api

# Grant storage access
termux-setup-storage
```

### 3. Clone or Copy the Project

**Option A: From Git (if you have a repo)**
```bash
cd ~/storage/shared
git clone <your-repo-url> mls3
cd mls3
```

**Option B: Manual Copy**
- Copy the mls3 folder to `/storage/emulated/0/` (shared storage)
- In Termux:
```bash
cd ~/storage/shared/mls3
```

### 4. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Data Setup

### 1. Create Production Data Directory

```bash
mkdir -p ~/mls3-data
mkdir -p ~/mls3-data/backups
```

### 2. Copy Initial Data Files

```bash
# Copy example files to production directory
cp data/members.example.csv ~/mls3-data/members.csv
cp data/prayer_assignments.example.csv ~/mls3-data/prayer_assignments.csv
cp data/message_templates.yaml ~/mls3-data/message_templates.yaml
```

### 3. Import Your Member Data

You have two options:

**Option A: Use the import script**
1. Download CSV from your church website
2. Copy it to Termux storage
3. Run:
```bash
source venv/bin/activate
python utils/import_members.py ~/storage/shared/Downloads/church_export.csv
```

**Option B: Edit manually**
```bash
# Edit members.csv directly
nano ~/mls3-data/members.csv
```

### 4. Customize Message Templates (Optional)

```bash
nano ~/mls3-data/message_templates.yaml
```

Edit the SMS messages to match your style.

---

## Running MLS3

### Quick Start

```bash
cd ~/storage/shared/mls3

# Set production data directory
export MLS3_DATA_DIR=~/mls3-data

# Run the app
./start.sh
```

The app will start and show:
```
MLS3 starting...
Data directory: /data/data/com.termux/files/home/mls3-data
Members CSV: /data/data/com.termux/files/home/mls3-data/members.csv
Loaded 32 members
Loaded 4 assignments
 * Running on http://127.0.0.1:5000
```

### Open in Browser

In Termux, run:
```bash
termux-open-url http://localhost:5000
```

Your default browser will open with MLS3.

---

## Daily Usage

### Starting the App

```bash
cd ~/storage/shared/mls3
export MLS3_DATA_DIR=~/mls3-data
./start.sh
```

Or create an alias in `~/.bashrc`:
```bash
echo 'alias mls3="cd ~/storage/shared/mls3 && export MLS3_DATA_DIR=~/mls3-data && ./start.sh"' >> ~/.bashrc
source ~/.bashrc
```

Then just type:
```bash
mls3
```

### Stopping the App

Press `Ctrl+C` in Termux to stop the Flask server.

### Accessing the App

1. Start the app in Termux
2. Keep Termux running in the background
3. Open your browser to http://localhost:5000
4. Schedule prayers, send invites, etc.
5. When you need to send SMS, the app will open your SMS app
6. Press back to return to the browser
7. Continue managing assignments

---

## Backing Up Your Data

### Manual Backup

```bash
# Backup to a timestamped file
cp ~/mls3-data/members.csv ~/mls3-data/backups/members_$(date +%Y%m%d).csv
cp ~/mls3-data/prayer_assignments.csv ~/mls3-data/backups/assignments_$(date +%Y%m%d).csv
```

### Backup to Cloud

**Option A: Google Drive**
- Install a file manager app (like Solid Explorer)
- Navigate to `/storage/emulated/0/Android/data/com.termux/files/home/mls3-data/`
- Copy files to Google Drive folder

**Option B: Termux with rsync (advanced)**
```bash
# Install rsync
pkg install rsync

# Sync to cloud storage
rsync -av ~/mls3-data/ ~/storage/shared/MyDrive/mls3-backup/
```

### Restore from Backup

```bash
# Copy backup file back
cp ~/mls3-data/backups/members_20260205.csv ~/mls3-data/members.csv
```

---

## Updating Member Data

### Import New Data from Church

```bash
cd ~/storage/shared/mls3
source venv/bin/activate
export MLS3_DATA_DIR=~/mls3-data

# Download CSV from church website first, then:
python utils/import_members.py ~/storage/shared/Downloads/church_export.csv

# Preview first with dry-run
python utils/import_members.py ~/storage/shared/Downloads/church_export.csv --dry-run

# Sync active status (mark absent members as inactive)
python utils/import_members.py church_export.csv --activate-present --deactivate-absent
```

The import will:
- Add new members
- Update phone numbers, birthdays, gender
- Preserve prayer history and notes
- Default: leaves active/inactive status unchanged

### Import Prayer History

If you have historical prayer data:
```bash
python utils/import_members.py --update-prayed prayer_dates.csv
```

File format: Name (tab) Prayed (supports various date formats)

### Manage Don't Ask List

```bash
# Mark members who shouldn't be asked
python utils/import_members.py --dont-ask dont_ask_list.csv

# Re-enable members
python utils/import_members.py --do-ask can_ask_again.csv
```

File format: Single Name column (tab-separated)

### Manual Editing

```bash
nano ~/mls3-data/members.csv
```

Or use a spreadsheet app on your phone to edit the CSV.

---

## Troubleshooting

### SMS App Doesn't Open

**Problem**: Clicking "Invite" or "Remind" doesn't open SMS app.

**Solution**:
1. Check termux-api is installed: `pkg list-installed | grep termux-api`
2. Verify Termux:API app is installed from F-Droid
3. Grant SMS permissions to Termux:API
4. Test: `termux-open-url "sms:5551234567?body=Test"`

### Can't Access http://localhost:5000

**Problem**: Browser shows "Can't connect" error.

**Solution**:
1. Make sure Flask app is running in Termux
2. Check for error messages in Termux
3. Try: `termux-open-url http://127.0.0.1:5000` instead
4. Verify port 5000 isn't used by another app

### Data Not Persisting

**Problem**: Changes don't save after restarting app.

**Solution**:
1. Verify `MLS3_DATA_DIR` is set: `echo $MLS3_DATA_DIR`
2. Check data directory exists: `ls -la ~/mls3-data/`
3. Check file permissions: `ls -l ~/mls3-data/*.csv`
4. Look for error messages when saving

### Import Script Fails

**Problem**: `import_members.py` errors or doesn't find fields.

**Solution**:
1. Check the file format:
   - Must be tab-separated (not comma-separated)
   - Must have header row
   - Expected columns: Name, Gender, Birth Date, Phone Number
   - Name format: "Last, First" (comma between last and first)
2. Use `--dry-run` to preview without making changes
3. Check for error messages about missing columns
4. See `data/sample_church_export.tsv` for correct format

**Problem**: Names not found in database

**Solution**:
- The script will list all unmatched names at the end
- Check for spelling differences, nicknames, or name changes
- Names can be "Last, First" OR "First Last" format
- Search is case-insensitive

### App Crashes on Startup

**Problem**: Flask won't start, shows errors.

**Solution**:
1. Check Python version: `python --version` (need 3.8+)
2. Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
3. Check CSV files are valid (no corrupted lines)
4. Look at error message for specific file/line causing issue

### Termux Closes Unexpectedly

**Problem**: Termux gets killed by Android when in background.

**Solution**:
1. In Android Settings → Apps → Termux
2. Disable battery optimization
3. Enable "Run in background"
4. Or use Termux:Boot to auto-start on phone boot

---

## Performance Tips

### 1. Keep Termux Alive
- Acquire a wakelock: `termux-wake-lock`
- Prevents Android from killing Termux
- Release when done: `termux-wake-unlock`

### 2. Notification Persistence
Create a persistent notification to keep Termux running:
```bash
termux-notification --title "MLS3" --content "Running on port 5000" --id mls3 --ongoing
```

### 3. Use Termux:Widget
Create a home screen widget to start MLS3 with one tap:
1. Install Termux:Widget from F-Droid
2. Create `~/.shortcuts/mls3.sh`:
```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/storage/shared/mls3
export MLS3_DATA_DIR=~/mls3-data
./start.sh
```
3. Make executable: `chmod +x ~/.shortcuts/mls3.sh`
4. Add Termux:Widget to home screen

---

## Advanced: Auto-Start on Boot

### Using Termux:Boot

1. Install Termux:Boot from F-Droid
2. Create `~/.termux/boot/start-mls3.sh`:
```bash
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/storage/shared/mls3
export MLS3_DATA_DIR=~/mls3-data
./start.sh &
```
3. Make executable: `chmod +x ~/.termux/boot/start-mls3.sh`
4. Restart phone to test

---

## Security Notes

1. **Data Privacy**: Your member data stays on your phone only
2. **No Cloud Sync**: MLS3 doesn't send data anywhere
3. **Local Access Only**: Flask only listens on localhost (127.0.0.1)
4. **Backup Important**: No automatic backups - you must do manual backups
5. **SMS Verification**: Always review SMS messages before sending

---

## Getting Help

### Check Logs

View Flask app logs in Termux for error messages.

### Common Issues Document

See `TROUBLESHOOTING.md` for more detailed solutions.

### Master Plan Reference

See `mls-master-plan.md` for system architecture and design decisions.

---

## Next Steps After Deployment

1. ✅ Test creating a prayer assignment
2. ✅ Test member selection (next-up candidates)
3. ✅ Test SMS invite (in debug mode first!)
4. ✅ Test state transitions (Accept, Complete, etc.)
5. ✅ Test date changes for future weeks
6. ✅ Import your actual member data
7. ✅ Customize SMS message templates
8. ✅ Set up backups
9. ✅ Create home screen shortcut
10. ✅ Schedule your first real prayers!

---

*Last Updated: 2026-02-06*
*For MLS3 Version: 1.0 (Phase 1 Complete)*
