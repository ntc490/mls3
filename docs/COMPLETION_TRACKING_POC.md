# Completion Tracking - Proof of Concept

**Status**: Proof of Concept (February 9, 2026)

This document describes a minimal proof-of-concept implementation to test the completion tracking workflow before full implementation.

## Goals

- Test the user experience of clicking completion links in calendar events
- Verify Google Sheets + Apps Script can handle the workflow
- Validate the data flow: Calendar → Sheet → MLS3
- Get feedback from bishopric before full implementation

## Architecture Overview

```
┌─────────────────┐
│ Google Calendar │
│   Event         │
│  [Complete]     │  ← Conductor clicks link
└────────┬────────┘
         │ HTTPS GET request
         ↓
┌─────────────────┐
│ Apps Script     │
│  (Web App)      │  ← Writes to sheet
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Google Sheet    │
│ Completion Log  │  ← Stores completion record
└────────┬────────┘
         │
         ↓ (Manual for POC)
┌─────────────────┐
│ MLS3 Manual     │
│ Mark Complete   │  ← Clerk updates appointment state
└─────────────────┘
```

## Google Sheet Setup

### Sheet Structure: "Appointment Completions"

**Minimal data approach - Calendar is the source of truth**

| Timestamp | Calendar ID | Event ID | Status |
|-----------|-------------|----------|--------|
| 2026-02-09 14:32 | bishop@calendar.id | abc123xyz | Completed |
| 2026-02-09 15:45 | counselor@calendar.id | def456uvw | No-show |

**Why minimal?**
- Calendar events contain all the details (member name, type, conductor)
- Sheet just records WHICH event was completed and WHEN
- Clerk can generate detailed reports later by fetching calendar events
- No data duplication, calendar is single source of truth

### Setup Steps

1. **Create new Google Sheet**: "MLS3 Appointment Tracking"
2. **Create sheet tab**: "Completions"
3. **Add header row** (row 1):
   - A1: `Timestamp`
   - B1: `Calendar ID`
   - C1: `Event ID`
   - D1: `Status`

## Google Apps Script

### Script: Code.gs

```javascript
/**
 * MLS3 Appointment Completion Tracking
 * Handles completion link clicks from calendar events
 */

function doGet(e) {
  const params = e.parameter;
  const appointmentId = params.id;
  const status = params.status || 'Completed';

  // Validate required parameters
  if (!appointmentId) {
    return ContentService.createTextOutput('Error: Missing appointment ID')
      .setMimeType(ContentService.MimeType.TEXT);
  }

  // Record completion
  recordCompletion(appointmentId, status);

  // Return success page
  return HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            text-align: center;
          }
          .success {
            color: #28a745;
            font-size: 24px;
            margin-bottom: 20px;
          }
          .details {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
          }
        </style>
      </head>
      <body>
        <div class="success">✓ Recorded Successfully</div>
        <div class="details">
          <p><strong>Appointment ID:</strong> ${appointmentId}</p>
          <p><strong>Status:</strong> ${status}</p>
          <p><strong>Time:</strong> ${new Date().toLocaleString()}</p>
        </div>
        <p>You can close this window now.</p>
      </body>
    </html>
  `);
}

function recordCompletion(appointmentId, status) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Completions');

  if (!sheet) {
    throw new Error('Sheet "Completions" not found');
  }

  // Get appointment details (for POC, we'll fetch from calendar or hardcode)
  const details = getAppointmentDetails(appointmentId);

  // Append new row
  sheet.appendRow([
    new Date(),
    appointmentId,
    details.memberName,
    details.appointmentType,
    details.conductor,
    status
  ]);
}

function getAppointmentDetails(appointmentId) {
  // For POC: Hardcode some test data
  // In production, this would query the calendar event or a separate data sheet
  return {
    memberName: 'Test Member',
    appointmentType: 'Temple Recommend',
    conductor: 'Bishop'
  };
}

/**
 * Test function to verify script works
 */
function testRecordCompletion() {
  recordCompletion('TEST-123', 'Completed');
  Logger.log('Test completion recorded');
}
```

### Deployment

1. Open Google Sheet
2. **Extensions → Apps Script**
3. Paste code above
4. **Deploy → New deployment**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone** (for POC - will restrict later)
5. **Authorize** the script
6. Copy the **Web App URL** (looks like: `https://script.google.com/macros/s/.../exec`)

  https://script.google.com/macros/s/AKfycbwsSJmf57Ef32wdlIo825duaxrRFvjgLb1H7eP9KWAmn7rlzTCKwBB5uU6D5uzNn1k/exec

## Calendar Event Template

Create a test calendar event with this description:

```
Temple Recommend Interview
Member: John Doe
Phone: 801-555-1234

--- AFTER APPOINTMENT ---
Long-press one of the links below and select "Open link":

✓ Completed
https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec?calendar_id=CALENDAR_ID&event_id=EVENT_ID&status=Completed

⊗ No-show
https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec?calendar_id=CALENDAR_ID&event_id=EVENT_ID&status=No-show

⚠ Rescheduled
https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec?calendar_id=CALENDAR_ID&event_id=EVENT_ID&status=Rescheduled
```

**Note**: MLS3 knows both Calendar ID and Event ID when it creates the appointment, so it can automatically generate these links.

## Testing Workflow

### Test 1: Complete Appointment
1. Open calendar event on phone
2. **Long-press** "✓ Completed" link
3. Select "Open link" from menu
4. Verify browser opens with success message
5. Check Google Sheet for new row
6. Verify timestamp, calendar ID, event ID, and status

### Test 2: No-show
1. Open calendar event
2. **Long-press** "⊗ No-show" link
3. Select "Open link"
4. Verify success message
5. Check sheet for "No-show" status

### Test 3: Rescheduled
1. Open calendar event
2. **Long-press** "⚠ Rescheduled" link
3. Select "Open link"
4. Verify success message
5. Check sheet for "Rescheduled" status

## Manual MLS3 Update (POC)

For POC, clerk manually updates appointment state:

1. Check Google Sheet for new completions
2. Note Calendar ID + Event ID
3. Open MLS3 appointment scheduler
4. Find appointment by matching calendar event
5. Update state to "Completed"

## Generating Detailed Reports (Optional)

Clerk can add a report generation script to the Google Sheet:

```javascript
function generateCompletionReport() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Completions');
  const data = sheet.getDataRange().getValues();

  // For each completion row:
  for (let i = 1; i < data.length; i++) {
    const calendarId = data[i][1];
    const eventId = data[i][2];
    const status = data[i][3];

    // Fetch event from Google Calendar
    const event = CalendarApp.getCalendarById(calendarId).getEventById(eventId);

    // Extract details from event title/description
    // Generate detailed report row
  }
}
```

This keeps completion recording fast (just IDs), and detail extraction happens only when needed.

## Future Enhancements (Post-POC)

If POC is successful, implement:

1. **Auto-sync**: MLS3 polls Google Sheet every 5 minutes
2. **Automatic link generation**: MLS3 adds completion links when creating events
3. **Event lookup**: MLS3 uses Calendar ID + Event ID to find appointments
4. **Authentication**: Restrict web app access to bishopric only
5. **Undo functionality**: Link to undo completion if clicked by mistake
6. **Notes field**: Allow conductor to add notes with completion
7. **Report generation**: Script in sheet to generate detailed reports from calendar data

## Security Considerations

**For POC (Acceptable)**:
- Web app accessible by "Anyone"
- No authentication required
- Calendar/Event IDs are Google-generated (hard to guess but not secret)

**For Production (Required)**:
- Restrict to specific Google accounts (bishopric only)
- Consider adding HMAC signature to verify links not tampered with
- Log all access attempts
- Event IDs are already random Google-generated strings (reasonably secure)

## Decision Points

After testing POC, decide:

1. **Is this workflow better than manual updates?**
   - Does it save time?
   - Is it intuitive for bishopric?
   - Do they actually use it?

2. **What status options are needed?**
   - Just Completed/No-show?
   - Add Rescheduled/Cancelled?
   - Add notes field?

3. **Should MLS3 auto-sync or require manual check?**
   - Auto-sync every N minutes?
   - Manual "Check for completions" button?
   - Real-time webhook (more complex)?

4. **Who should have access?**
   - Just Bishop?
   - Bishop + Counselor?
   - Anyone with calendar access?

## Success Criteria

POC is successful if:
- ✓ Links work reliably on phone
- ✓ Google Sheet records completions correctly
- ✓ Workflow is faster than manual entry
- ✓ Bishopric finds it intuitive and useful
- ✓ No technical issues or confusion

If successful → Implement Phase 3
If not successful → Stay with manual workflow

---

## Quick Start for POC

### 1. Create Google Sheet
```
Sheet name: MLS3 Appointment Tracking
Tab: Completions
Headers: Timestamp | Calendar ID | Event ID | Status
```

### 2. Deploy Apps Script
- Extensions → Apps Script
- Paste code from above
- Deploy as Web App
- Copy Web App URL

### 3. Create Test Event
```bash
cd /home/nlod/claude/mls3
source venv/bin/activate
export MLS3_GOOGLE_CALENDAR=true

python utils/create_test_completion_event.py "YOUR_WEB_APP_URL"
```

This creates a test event with proper Calendar ID + Event ID in the links.

### 4. Test
- Open calendar event on phone
- Long-press link to open
- Verify sheet updates with Calendar ID, Event ID, Status
- Check success message displays

### 5. Gather Feedback
- Show to bishopric
- Get their thoughts
- Decide whether to proceed with Phase 3

---

*Created: February 9, 2026*
*Status: Ready to test*
