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

### SMS Integration (Debug Mode)
- [ ] Clicking [Invite] prints message to console (debug mode)
- [ ] Message includes member name, date, and prayer type
- [ ] State changes to "Invited" after sending
- [ ] State badge shows "Invited" with correct color
- [ ] [Accept] and [Decline] buttons appear in Invited state

### State Transitions
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

### Multi-Week Support
- [ ] Can change assignment date to future Sunday
- [ ] Future assignment moves to Active Queue
- [ ] Active Queue section appears below current week
- [ ] Queue items sorted by date
- [ ] Queue items show date, type, member, state
- [ ] Can have multiple assignments in queue
- [ ] Current week shows only next Sunday's assignments

### Data Persistence
- [ ] Assignments saved to CSV after creation
- [ ] State changes saved to CSV
- [ ] Member updates saved to CSV
- [ ] Data persists after app restart
- [ ] CSV files remain valid (no corruption)

### UI/UX
- [ ] All buttons have adequate size (44x44px)
- [ ] Hover effects work on bubbles
- [ ] Loading cursor shows during operations
- [ ] Page reloads after state changes
- [ ] Animations smooth (fade-in effect)
- [ ] Mobile layout works (narrow browser window)

---

## Production Testing (Termux)

Test these features on your Android phone in Termux.

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

### Environment Configuration
- [ ] Can navigate to project directory
- [ ] MLS3_DATA_DIR environment variable works
- [ ] start.sh script is executable
- [ ] start.sh runs without errors

### App Startup
- [ ] Flask app starts in Termux
- [ ] Displays correct data directory path
- [ ] Loads members and assignments
- [ ] Shows running on http://127.0.0.1:5000
- [ ] Can open in browser with termux-open-url
- [ ] Browser opens to correct page

### SMS Integration (Production)
- [ ] **IMPORTANT**: Test with your own phone number first!
- [ ] Clicking [Invite] opens SMS app
- [ ] SMS app pre-fills message correctly
- [ ] SMS app shows correct phone number
- [ ] Message text is readable and correct
- [ ] Can edit message before sending
- [ ] Can send message successfully
- [ ] Pressing back returns to browser
- [ ] Assignment state updates to Invited
- [ ] Can do same test with [Remind] button

### Real-World Workflow Test
Perform a complete workflow:
1. [ ] Create Opening prayer assignment for next Sunday
2. [ ] Select a member from next-up candidates
3. [ ] Send invitation SMS (to yourself for testing)
4. [ ] Mark as Accepted
5. [ ] Send reminder SMS
6. [ ] Mark as Completed
7. [ ] Verify member's last_prayer_date updated
8. [ ] Verify member excluded from next-up list

### Multi-Device Testing
- [ ] Termux continues running in background
- [ ] Can switch to browser and back
- [ ] Can receive calls while app running
- [ ] Battery drain acceptable
- [ ] Termux doesn't get killed by Android

### Data Management
- [ ] Can import church CSV data
- [ ] Import preserves prayer history
- [ ] Can edit members.csv manually
- [ ] Can create manual backup
- [ ] Can restore from backup
- [ ] Changes persist across app restarts

### Edge Cases
- [ ] What happens if member declines?
  - [ ] Can clear and select new person
  - [ ] Original member returns to next-up pool
- [ ] What happens if same person scheduled twice?
  - [ ] Warning or prevented by candidate exclusion
- [ ] What happens if no members left for gender?
  - [ ] Shows empty next-up list (or all members)
- [ ] What happens if SMS app fails to open?
  - [ ] Shows error with phone number for manual fallback
- [ ] What happens if date is invalid?
  - [ ] Shows error message, date not changed
- [ ] What happens if network/browser closes?
  - [ ] Flask still running in Termux
  - [ ] Can reopen browser to same URL

---

## Performance Testing

### App Performance
- [ ] Pages load in < 2 seconds
- [ ] Candidate search responds instantly
- [ ] State changes save quickly
- [ ] No lag when switching pages
- [ ] Animations don't stutter

### Resource Usage
- [ ] Termux memory usage reasonable (< 200MB)
- [ ] Battery drain acceptable for duration of use
- [ ] Phone doesn't overheat
- [ ] Can run for 30+ minutes without issues

---

## Security Testing

### Data Privacy
- [ ] Member data stored locally only
- [ ] No network requests to external servers
- [ ] Flask only accessible on localhost
- [ ] Can't access from other devices on network
- [ ] CSV files have appropriate permissions

### SMS Security
- [ ] Always shows message before sending
- [ ] User must manually tap Send in SMS app
- [ ] Can cancel SMS before sending
- [ ] Phone numbers formatted correctly
- [ ] No message truncation or corruption

---

## Regression Testing (After Updates)

Whenever you update MLS3:
- [ ] All basic workflow tests pass
- [ ] Data files still load correctly
- [ ] No new errors in console
- [ ] SMS still works as expected
- [ ] Backup/restore still works

---

## Production Readiness Checklist

Before using with real members:
- [ ] All desktop tests passed
- [ ] All Termux tests passed
- [ ] SMS tested with own number successfully
- [ ] Imported actual member data
- [ ] Customized message templates
- [ ] Created initial data backup
- [ ] Set up backup routine
- [ ] Comfortable with complete workflow
- [ ] Tested member decline scenario
- [ ] Tested future date scheduling
- [ ] Know how to stop/restart app
- [ ] Know how to access logs if issues occur

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
**Result**: [ ] Pass  [ ] Fail  [ ] Partial

**Notes**:




---

*Use this checklist before each major deployment or after significant code changes.*
