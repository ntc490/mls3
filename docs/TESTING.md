# MLS3 Testing Checklist

Use this checklist to verify all features work correctly before production use.

---

## Pre-Deployment Testing (Desktop)

Test these features on your computer before deploying to Termux.

### Setup
- [ ] Virtual environment created and activated
- [ ] Dependencies installed from requirements.txt
- [ ] `MLS3_DEBUG_SMS=true` environment variable set
- [ ] Flask app starts without errors
- [ ] Can access http://localhost:5000

### Member Management
- [ ] Members list displays correctly
- [ ] Can filter by gender (All/Men/Women)
- [ ] Search box filters members in real-time
- [ ] Member cards show all data (name, phone, last prayer date)
- [ ] Members with "don't ask" flag are marked
- [ ] Import script runs without errors
- [ ] Import adds new members correctly
- [ ] Import updates existing members without losing prayer history

### Prayer Scheduler - Basic UI
- [ ] Prayer scheduler page loads
- [ ] Shows current week date correctly
- [ ] Two cards visible (Opening and Closing)
- [ ] "Create Assignment" buttons work
- [ ] New assignments appear after creation

### Candidate Selection
- [ ] Click person bubble opens modal
- [ ] "Next Up" shows 3 men + 3 women initially
- [ ] Candidates sorted by last prayer date (oldest first)
- [ ] Members who never prayed appear first
- [ ] Search box filters candidates
- [ ] Selecting a candidate updates assignment
- [ ] Member's gender restricts subsequent selections
- [ ] Members with active assignments excluded from next-up list

### Prayer Assignment Workflow - Draft State
- [ ] Can create Opening prayer assignment
- [ ] Can create Closing prayer assignment
- [ ] Can select person for assignment
- [ ] Person bubble shows member name and last prayer date
- [ ] Can clear selected person with × button
- [ ] Clear button asks for confirmation
- [ ] Prayer type can be toggled (Opening/Closing)
- [ ] Date bubble shows correct date
- [ ] Date can be changed by clicking date bubble
- [ ] [Invite] button appears when person selected

### Prayer SMS Integration (Debug Mode)
- [ ] Clicking [Invite] prints message to console (debug mode)
- [ ] Message includes member name, date, and prayer type
- [ ] State changes to "Invited" after sending
- [ ] State badge shows "Invited" with correct color
- [ ] [Accept] and [Decline] buttons appear in Invited state

### Prayer State Transitions
- [ ] Draft → [Invite] → Invited
- [ ] Invited → [Accept] → Accepted
- [ ] Invited → [Decline] → Draft (person cleared)
- [ ] Invited → [Cancel] → Draft (person kept)
- [ ] Accepted → [Remind] → Reminded
- [ ] Accepted → [Complete] → Completed
- [ ] Accepted → [Cancel] → Draft
- [ ] Reminded → [Complete] → Completed
- [ ] Reminded → [Cancel] → Draft
- [ ] Decline button shows confirmation dialog
- [ ] Completed assignments update last_prayer_date

### Multi-Week Support (Prayers)
- [ ] Can change assignment date to future Sunday
- [ ] Future assignment moves to Active Queue
- [ ] Active Queue section appears below current week
- [ ] Queue items sorted by date
- [ ] Queue items show date, type, member, state
- [ ] Can have multiple assignments in queue
- [ ] Current week shows only next Sunday's assignments

---

## Appointment Management Testing

### Appointment Scheduler - Basic UI
- [ ] Appointment scheduler page loads correctly
- [ ] Member search autocomplete works
- [ ] Appointment type dropdown populates from appointment_types.yaml
- [ ] Date picker works
- [ ] Time picker works (24-hour or 12-hour depending on browser)
- [ ] Duration field accepts numeric input
- [ ] Conductor toggle buttons work (Bishop/Counselor)
- [ ] Form validation prevents submission with missing fields

### Appointment Creation
- [ ] Can create new appointment with all fields
- [ ] Default duration populates based on appointment type
- [ ] Member autocomplete shows relevant results
- [ ] Selected member appears in field
- [ ] Clear member button (×) works
- [ ] Save button creates draft appointment
- [ ] Appointment appears in scheduled list
- [ ] Appointment saved to appointments.csv

### Appointment Types
- [ ] All configured types appear in dropdown
- [ ] Selecting type populates default duration
- [ ] Can manually override duration
- [ ] Custom appointment types work (if added to yaml)
- [ ] Types display correctly in appointment list

### Appointment State Workflow
- [ ] Draft state: Shows [Save] and [Send Invite] buttons
- [ ] Draft → [Send Invite] → Invited
- [ ] Invited state: Shows [Accept], [Remind], [Delete] buttons
- [ ] Invited → [Accept] → Accepted
- [ ] Accepted state: Shows [Remind], [Complete], [Delete] buttons
- [ ] Accepted → [Remind] → Reminded
- [ ] Reminded → [Complete] → Completed
- [ ] Any state → [Delete] removes appointment
- [ ] State badges display correct colors
- [ ] State transitions save to CSV

### Appointment SMS Integration (Debug Mode)
- [ ] [Send Invite] prints invitation message to console
- [ ] Message includes member name, type, date, time, conductor
- [ ] [Remind] prints reminder message to console
- [ ] Reminder message includes appointment details
- [ ] SMS uses appointment-specific templates from message_templates.yaml

### Appointment Editing
- [ ] Can click existing appointment to edit
- [ ] Form populates with existing data
- [ ] Can change member
- [ ] Can change date/time
- [ ] Can change duration
- [ ] Can change conductor
- [ ] Can change appointment type
- [ ] [Update] button appears instead of [Save]
- [ ] Changes persist to CSV

### Conductor Management
- [ ] Can toggle between Bishop and Counselor
- [ ] Conductor selection affects calendar assignment
- [ ] Different conductors' appointments displayed separately
- [ ] Active conductor highlighted visually

### Scheduled Appointments List
- [ ] Appointments for selected date display correctly
- [ ] List sorted by time (earliest first)
- [ ] Shows appointment type, member name, time
- [ ] Shows current state badge
- [ ] Clicking appointment loads it in editor
- [ ] Can navigate between dates
- [ ] Empty states show helpful message

### Date/Time Handling
- [ ] Date picker defaults to today or selected date
- [ ] Time picker shows in correct format
- [ ] Appointments display in local timezone
- [ ] Date changes work correctly (no UTC drift)
- [ ] Sorting by time works correctly (9 AM before 11 AM, not 9 PM)
- [ ] 24-hour time used internally for sorting
- [ ] 12-hour time displayed to user (with AM/PM)

### Appointment Deletion
- [ ] Delete button shows confirmation dialog
- [ ] Deleting removes from CSV
- [ ] Deleted appointment disappears from list
- [ ] Cannot recover deleted appointments (expected behavior)

---

## Google Calendar Integration Testing

### Calendar Setup (if enabled)
- [ ] MLS3_GOOGLE_CALENDAR=true environment variable set
- [ ] credentials.json file present in data directory
- [ ] BISHOP_CALENDAR_ID configured
- [ ] COUNSELOR_CALENDAR_ID configured
- [ ] OAuth authorization completed (token.pickle exists)
- [ ] No errors on app startup related to calendar

### Calendar Event Creation
- [ ] Creating appointment creates calendar event
- [ ] Event appears in correct calendar (Bishop vs Counselor)
- [ ] Event title includes appointment type and member name
- [ ] Event description includes full details
- [ ] Event time matches appointment time
- [ ] Event duration matches appointment duration
- [ ] State indicator appears in event title (e.g., [Invited])

### Calendar Event Updates
- [ ] Updating appointment time updates calendar event
- [ ] Updating appointment date updates calendar event
- [ ] Changing appointment type updates event title
- [ ] Changing duration updates event duration
- [ ] State changes update event title (adds/removes state prefix)

### Calendar Conductor Changes
- [ ] Changing conductor from Bishop to Counselor moves event
- [ ] Old calendar event deleted
- [ ] New calendar event created in correct calendar
- [ ] Event details preserved during move
- [ ] No duplicate events created

### Calendar Event Deletion
- [ ] Deleting Draft appointment deletes calendar event
- [ ] Deleting Invited appointment deletes calendar event
- [ ] Deleting Accepted appointment deletes calendar event
- [ ] Deleting Reminded appointment deletes calendar event
- [ ] Deleting Completed appointment KEEPS calendar event (history preservation)
- [ ] Manual calendar events not created by MLS3 are never touched

### Manual Sync Button
- [ ] Sync button appears in appointment editor
- [ ] Clicking sync button triggers calendar sync
- [ ] Success/failure message displays
- [ ] Re-syncing existing event works
- [ ] Sync works for all appointment states

### Offline Behavior
- [ ] App works when internet disconnected
- [ ] Calendar sync fails gracefully (no crashes)
- [ ] Warning message logged to console
- [ ] Appointments still save to CSV
- [ ] Sync occurs when back online

### Calendar Permissions
- [ ] OAuth consent screen completed
- [ ] Calendar read/write permissions granted
- [ ] Token refresh works automatically
- [ ] App doesn't crash if token expires
- [ ] Re-authorization flow works if needed

### Calendar Event Colors
- [ ] Bishop appointments use peachy background (#f5d5cc)
- [ ] Counselor appointments use lavender-blue background (#d4ddf2)
- [ ] Colors provide sufficient contrast
- [ ] Events visually distinguishable in calendar

### Calendar Safety Features
- [ ] Only MLS3-created events have mls3_type property
- [ ] Deletion checks for MLS3 ownership before removing
- [ ] Manual calendar events not deleted by MLS3
- [ ] Extended properties stored correctly
- [ ] Calendar event IDs tracked in appointments.csv

---

## Events Page Testing

### Events Calendar View
- [ ] Events page loads correctly
- [ ] Shows calendar view of current month
- [ ] Prayer assignments appear on correct dates
- [ ] Appointments appear on correct dates
- [ ] Different event types visually distinguishable
- [ ] Bishop appointments have distinct color
- [ ] Counselor appointments have distinct color
- [ ] Opening prayers marked differently from closing prayers

### Event Details
- [ ] Clicking event shows details
- [ ] Event type clearly indicated
- [ ] Member name displayed
- [ ] Time displayed correctly
- [ ] State/status shown
- [ ] Can navigate to edit appointment from event

### Event Sorting
- [ ] Events on same day sorted by time
- [ ] Multiple events display without overlap
- [ ] Time sorting works correctly (AM before PM)
- [ ] 24-hour sorting prevents 9 PM appearing before 11 AM

---

## Timezone Testing

### UTC Storage
- [ ] Appointments stored in UTC in appointments.csv
- [ ] datetime_utc field in correct ISO 8601 format
- [ ] UTC timestamps include 'Z' suffix

### Local Display
- [ ] Appointments display in configured timezone (HOME_TIMEZONE)
- [ ] Date changes don't cause timezone drift
- [ ] Editing appointment preserves correct time
- [ ] Calendar events show correct local time

### DST Boundaries (if applicable)
- [ ] Appointments across DST change work correctly
- [ ] Time doesn't jump forward/backward unexpectedly
- [ ] Calendar sync handles DST correctly

### Multi-Timezone Testing (if applicable)
- [ ] Changing HOME_TIMEZONE in config.py updates display
- [ ] Existing appointments display in new timezone correctly
- [ ] New appointments save with correct UTC offset

---

## Data Persistence Testing

### CSV Storage
- [ ] Appointments saved to appointments.csv
- [ ] Prayers saved to prayer_assignments.csv
- [ ] Members updated in members.csv
- [ ] State changes persist across restarts
- [ ] Data files remain valid (no corruption)
- [ ] CSV headers correct

### Backup and Restore
- [ ] Can manually backup data directory
- [ ] Can restore from backup successfully
- [ ] Restored data loads correctly
- [ ] No data loss after restore

### Appointment CSV Schema
- [ ] appointment_id unique and sequential
- [ ] member_id references valid member
- [ ] datetime_utc in correct format
- [ ] duration_minutes is integer
- [ ] conductor is "Bishop" or "Counselor"
- [ ] state is valid (Draft/Invited/Accepted/Reminded/Completed/Cancelled)
- [ ] google_event_id populated when synced
- [ ] All fields properly escaped

---

## Production Testing (Termux)

### Initial Setup
- [ ] Termux installed from F-Droid (not Google Play)
- [ ] Termux:API installed from F-Droid
- [ ] Python 3 installed in Termux
- [ ] termux-api package installed
- [ ] Storage access granted (termux-setup-storage)
- [ ] Git installed (if using git clone)

### Project Setup
- [ ] Project files copied to ~/storage/shared/mls3
- [ ] Virtual environment created
- [ ] Dependencies installed successfully
- [ ] Production data directory created (~/mls3-data)
- [ ] Example data copied to production directory
- [ ] appointment_types.yaml copied to data directory

### Google Calendar Setup (Termux)
- [ ] credentials.json copied to ~/mls3-data/
- [ ] OAuth authorization completed via authorize_google_calendar.py
- [ ] token.pickle file created
- [ ] Environment variables set in ~/.bashrc
- [ ] Calendar sync works on Termux

### Environment Configuration
- [ ] Can navigate to project directory
- [ ] MLS3_DATA_DIR environment variable works
- [ ] MLS3_GOOGLE_CALENDAR environment variable works
- [ ] BISHOP_CALENDAR_ID and COUNSELOR_CALENDAR_ID set
- [ ] start.sh script is executable
- [ ] start.sh runs without errors

### App Startup
- [ ] Flask app starts in Termux
- [ ] Displays correct data directory path
- [ ] Loads members, prayers, and appointments
- [ ] Shows running on http://127.0.0.1:5000
- [ ] Can open in browser with termux-open-url
- [ ] Browser opens to correct page
- [ ] Calendar sync initializes (if enabled)

### SMS Integration (Production)
- [ ] **IMPORTANT**: Test with your own phone number first!
- [ ] Prayer invite opens SMS app correctly
- [ ] Appointment invite opens SMS app correctly
- [ ] SMS app pre-fills message correctly
- [ ] SMS app shows correct phone number
- [ ] Message text is readable and correct
- [ ] Can edit message before sending
- [ ] Can send message successfully
- [ ] Pressing back returns to browser
- [ ] State updates correctly after sending

### Appointment Real-World Workflow Test
Perform a complete appointment workflow:
1. [ ] Create Temple Recommend appointment for tomorrow
2. [ ] Select member from autocomplete
3. [ ] Set time to 3:00 PM
4. [ ] Set conductor to Bishop
5. [ ] Save as draft
6. [ ] Verify calendar event created (if sync enabled)
7. [ ] Send invitation SMS (to yourself for testing)
8. [ ] Mark as Accepted
9. [ ] Send reminder SMS
10. [ ] Mark as Completed
11. [ ] Verify calendar event preserved
12. [ ] Verify appointment in CSV with Completed state

### Multi-Device Testing
- [ ] Termux continues running in background
- [ ] Can switch to browser and back
- [ ] Can receive calls while app running
- [ ] Battery drain acceptable
- [ ] Termux doesn't get killed by Android
- [ ] Calendar sync works in background

---

## Edge Cases

### Prayer Edge Cases
- [ ] What happens if member declines prayer?
- [ ] Can clear and select new person
- [ ] Original member returns to next-up pool
- [ ] What happens if same person scheduled twice?
- [ ] What happens if no members left for gender?
- [ ] What happens if SMS app fails to open?

### Appointment Edge Cases
- [ ] What happens if appointment time is in the past?
- [ ] What happens if two appointments scheduled at same time?
- [ ] What happens if member deleted but has appointments?
- [ ] What happens if conductor calendar ID is wrong?
- [ ] What happens if OAuth token expires?
- [ ] What happens if calendar event manually deleted in Google?
- [ ] What happens if network fails during sync?
- [ ] What happens if appointment duration is 0 or negative?
- [ ] What happens if invalid date/time entered?

### Calendar Sync Edge Cases
- [ ] Sync when offline (fails gracefully)
- [ ] Sync with missing credentials.json (shows error)
- [ ] Sync with invalid calendar ID (shows error)
- [ ] Sync after changing conductor (moves between calendars)
- [ ] Multiple rapid updates (doesn't create duplicates)
- [ ] Deleting completed appointment (keeps in calendar)
- [ ] Manual sync button after automatic sync failure

---

## Performance Testing

### App Performance
- [ ] Pages load in < 2 seconds
- [ ] Member autocomplete responds instantly
- [ ] Candidate search responds instantly
- [ ] State changes save quickly
- [ ] Calendar sync doesn't block UI
- [ ] No lag when switching pages
- [ ] Animations don't stutter

### Resource Usage
- [ ] Termux memory usage reasonable (< 200MB)
- [ ] Battery drain acceptable for duration of use
- [ ] Phone doesn't overheat
- [ ] Can run for 30+ minutes without issues
- [ ] Calendar sync doesn't cause performance degradation

---

## Security Testing

### Data Privacy
- [ ] Member data stored locally only
- [ ] No network requests except Google Calendar API
- [ ] Flask only accessible on localhost
- [ ] Can't access from other devices on network
- [ ] CSV files have appropriate permissions
- [ ] credentials.json permissions secure (600)
- [ ] token.pickle permissions secure

### Google Calendar Security
- [ ] OAuth credentials never committed to git
- [ ] Calendar IDs in environment variables (not hardcoded)
- [ ] Only authorized calendars accessible
- [ ] Extended properties remain private
- [ ] No personal data in public calendar URLs

### SMS Security
- [ ] Always shows message before sending
- [ ] User must manually tap Send in SMS app
- [ ] Can cancel SMS before sending
- [ ] Phone numbers formatted correctly
- [ ] No message truncation or corruption

---

## Regression Testing (After Updates)

Whenever you update MLS3:
- [ ] All prayer workflow tests pass
- [ ] All appointment workflow tests pass
- [ ] Data files still load correctly
- [ ] No new errors in console
- [ ] SMS still works as expected
- [ ] Calendar sync still works (if enabled)
- [ ] Backup/restore still works
- [ ] Timezone handling still correct

---

## Production Readiness Checklist

Before using with real members:
- [ ] All desktop tests passed
- [ ] All Termux tests passed
- [ ] Prayer SMS tested with own number successfully
- [ ] Appointment SMS tested with own number successfully
- [ ] Imported actual member data
- [ ] Customized message templates for appointments
- [ ] Configured appointment types correctly
- [ ] Calendar integration tested (if using)
- [ ] Created initial data backup
- [ ] Set up backup routine
- [ ] Comfortable with prayer workflow
- [ ] Comfortable with appointment workflow
- [ ] Tested appointment state transitions
- [ ] Tested conductor changes
- [ ] Know how to stop/restart app
- [ ] Know how to access logs if issues occur
- [ ] Verified timezone handling correct for your area

---

## Known Issues / Limitations

Document any issues you encounter:

- Issue: _______________________________
  Workaround: _______________________________

- Issue: _______________________________
  Workaround: _______________________________

---

## Test Results Summary

**Date Tested**: _______________
**Tested By**: _______________
**Environment**: [ ] Desktop  [ ] Termux
**Features Tested**: [ ] Prayers  [ ] Appointments  [ ] Calendar Sync
**Result**: [ ] Pass  [ ] Fail  [ ] Partial

**Notes**:




---

*Use this checklist before each major deployment or after significant code changes.*
