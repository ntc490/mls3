# Completion Tracking POC - Quick Start Guide

**Goal**: Test the completion tracking workflow in under 15 minutes

## Step 1: Create Google Sheet (2 minutes)

1. Go to https://sheets.google.com
2. Create new sheet: **"MLS3 Appointment Tracking"**
3. Rename "Sheet1" to **"Completions"**
4. Add headers in row 1:
   - A1: `Timestamp`
   - B1: `Appointment ID`
   - C1: `Member Name`
   - D1: `Appointment Type`
   - E1: `Conductor`
   - F1: `Status`
5. Format row 1 as bold

## Step 2: Deploy Apps Script (5 minutes)

1. In your Google Sheet: **Extensions → Apps Script**
2. Delete default code
3. Copy code from `docs/COMPLETION_TRACKING_POC.md` (search for "Script: Code.gs")
4. Paste into script editor
5. Save project (Ctrl+S) - name it "MLS3 Completion Tracking"
6. Click **Deploy → New deployment**
   - Type: **Web app**
   - Description: "MLS3 Completion POC"
   - Execute as: **Me**
   - Who has access: **Anyone** (temporary for testing)
7. Click **Deploy**
8. Click **Authorize access** and grant permissions
9. Copy the **Web App URL** (looks like: `https://script.google.com/macros/s/...../exec`)

## Step 3: Create Test Calendar Event (1 minute)

Run the test script with your Web App URL:

```bash
cd /home/nlod/claude/mls3
source venv/bin/activate

# Make sure Google Calendar is enabled
export MLS3_GOOGLE_CALENDAR=true

# Create test event (replace URL with your actual Web App URL)
python utils/create_test_completion_event.py "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
```

The script will:
- Create a test appointment for tomorrow at 3 PM
- Add completion links to the event description
- Display event details and link

## Step 4: Test the Workflow (5 minutes)

### Test on Phone (Recommended)
1. Open Google Calendar app on phone
2. Find the **[TEST] Temple Recommend** event
3. Open event details
4. Scroll to bottom and click **"✓ Completed"** link
5. Browser opens with success message
6. Go to your Google Sheet
7. Verify new row appeared with completion data

### Test on Desktop
1. Open Google Calendar in browser
2. Click the test event
3. Click one of the completion links
4. Verify Google Sheet updates

### Test Different Statuses
- Click "⊗ No-show" link → verify status in sheet
- Click "⚠ Rescheduled" link → verify status in sheet

## Step 5: Review and Decide (2 minutes)

**Questions to answer:**
- ✓ Did links work reliably?
- ✓ Was it faster than manual entry?
- ✓ Is the workflow intuitive?
- ✓ Would bishopric actually use this?

If YES to all → Implement Phase 3 (full integration)
If NO to any → Stick with manual workflow

## Cleanup

After testing, delete:
1. Test calendar event
2. Test rows in Google Sheet

Keep the sheet and script if you want to do more testing.

## What's Next?

If POC is successful, Phase 3 will add:
- MLS3 auto-sync (checks sheet every 5 minutes)
- Automatic completion link generation
- Better security (restrict to bishopric accounts)
- Notes field for conductors
- Undo functionality

See `docs/COMPLETION_TRACKING_POC.md` for full details.

---

## Troubleshooting

### "Script not authorized" error
- Go back to Apps Script
- Run the `testRecordCompletion()` function manually
- Authorize the script when prompted
- Try deployment again

### "Sheet 'Completions' not found" error
- Verify sheet tab is named exactly "Completions" (capital C)
- No extra spaces in the name

### Link doesn't work
- Verify Web App URL is correct
- Check it ends with `/exec` not `/dev`
- Make sure deployment is set to "Anyone" for POC

### No row appears in sheet
- Check Apps Script logs: **View → Logs**
- Verify sheet name is correct
- Try running `testRecordCompletion()` manually

---

**Total Time: ~15 minutes**
**Difficulty: Easy**
**Result: Working completion tracking POC**
