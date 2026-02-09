# Appointment Completion Tracking System - Implementation Plan

**Status**: 📋 **PLANNED - Not Yet Implemented**
**Phase**: Phase 3
**Date Created**: February 7, 2026
**Current Status**: Awaiting bishopric buy-in before implementation

---

## Executive Summary

This document outlines a proposed system for conductors to easily record appointment completions via clickable links, with immediate feedback for conductors and self-service reporting for the clerk.

**Key Benefits:**
- ✅ **Conductors:** One-tap links in calendar, instant confirmation
- ✅ **Clerk:** Generate detailed reports anytime without waiting
- ✅ **Bishopric:** Automatic sync to MLS3 when convenient
- ✅ **Privacy:** No personal data stored in public systems

---

## Current Situation

### How Completion Tracking Works Today
1. Conductor meets with member
2. Conductor informs bishopric via GroupMe/text/in-person
3. Bishopric manually updates MLS3
4. Clerk asks for updates to record callings, set-aparts, etc.

### Problems with Current Approach
- ❌ Information scattered across GroupMe, texts, verbal
- ❌ No historical record
- ❌ Privacy concerns (personal info in group chat)
- ❌ Clerk has to wait for updates
- ❌ Manual data entry required

---

## Proposed Solution

### Architecture Overview

```
Conductor clicks link → Google Apps Script → Private Google Sheet
                                                      ↓
Clerk runs report ← Reads calendar details ← Sheet stores IDs only
                                                      ↓
                    MLS3 polls sheet (async) → Updates appointment states
```

### Three Components

#### 1. Completion Links in Calendar Events
Each appointment in Google Calendar includes clickable links:
- ✓ Completed
- ✗ No-show
- 📋 Accepted (calling)
- ❌ Declined (calling)
- 🙏 Set Apart
- 📤 Released

#### 2. Private Google Sheet (Data Collection)
Stores minimal data only:
```
Timestamp | AppointmentID | Action | CalendarLink | Status
```
**No personal information** - just IDs and links

#### 3. Clerk Report Script
Custom menu in Google Sheet: "MLS3 Reports → Generate Report"
- Reads calendar events to get member names and details
- Creates formatted report with full information
- Runs on-demand, anytime clerk needs it

---

## Workflow Examples

### Scenario 1: Temple Recommend Interview Completed

**What Happens:**
1. **Bishop interviews John Smith**
2. **Bishop taps "✓ Completed" link** in calendar event
3. **Confirmation page appears:** "Thank you! Appointment recorded."
4. **Sheet records:** `2026-02-08 | 123 | complete | [calendar link] | pending`
5. **Clerk checks sheet later** that evening
6. **Clerk runs report:** Sees "John Smith - Temple Recommend - Completed"
7. **MLS3 syncs** when you next open the app (could be days later)

**Time to clerk:** Immediate (no waiting for you to run MLS3)

### Scenario 2: Calling Extended and Accepted

**What Happens:**
1. **Counselor meets with Sarah Jones** to extend calling
2. **Sarah accepts**
3. **Counselor taps "📋 Accepted" link** in calendar
4. **Clerk runs report:** Sees "Sarah Jones - Calling - Accepted"
5. **Clerk records in LCR** that Sarah accepted Relief Society President calling

**Benefit:** Clerk doesn't need to wait for bishopric meeting or GroupMe update

### Scenario 3: Member Didn't Show Up

**What Happens:**
1. **Bishop waits for appointment**, member doesn't show
2. **Bishop taps "✗ No-show" link**
3. **Sheet records no-show**
4. **You see it later in MLS3:** Follow up to reschedule

---

## Security & Privacy

### What's Protected
✅ **Private Google Sheet** - Only bishopric/clerk have access
✅ **No personal data in sheet** - Just appointment IDs and calendar links
✅ **Calendar links require authorization** - Only those with calendar access can view
✅ **Apps Script URL is "secret"** - Long random ID, not published

### What's in URLs
- Appointment ID (number: 123)
- Calendar event ID (random string: abc123xyz)
- Calendar ID (identifies Bishop/Counselor calendar)
- Action (complete, no-show, etc.)

### What's NOT in URLs
- ❌ Member names
- ❌ Phone numbers
- ❌ Addresses
- ❌ Any personal information

### Attack Scenarios

**"What if the script URL leaks?"**
- Worst case: Someone could spam fake completions
- Impact: You'd see invalid appointment IDs, ignore them
- No personal data exposed (sheet is private)
- Can add signature verification if needed

**"What if the sheet is accidentally shared publicly?"**
- Sheet only contains appointment IDs and calendar links
- No names or personal information
- Calendar links still require authorization to view

---

## Mobile Experience

### How Links Appear in Calendar

**Calendar Event Description:**
```
Appointment: Temple Recommend
Member: John Smith
State: Invited
Duration: 20 minutes

━━━━━━━━━━━━━━━━━━━━━━
RECORD COMPLETION:

✓ Completed
https://script.google.com/.../exec?...

✗ No-show
https://script.google.com/.../exec?...

FOR CALLINGS:

📋 Accepted
https://script.google.com/.../exec?...

❌ Declined
https://script.google.com/.../exec?...

🙏 Set Apart
https://script.google.com/.../exec?...

📤 Released
https://script.google.com/.../exec?...
━━━━━━━━━━━━━━━━━━━━━━

Managed by MLS3
```

**On Mobile:**
- Each URL becomes a tappable button automatically
- Clear labels with emojis for easy identification
- One link per line = bigger tap target (easy for "fat fingers")
- Confirmation page is mobile-optimized

**Optional Enhancement:** URL shortening (TinyURL) to make links shorter/prettier

---

## Clerk Workflow

### Daily/Weekly Completion Check

1. **Open Google Sheet** (shared with clerk)
2. **See new completions** in "Completions" tab:
   ```
   2026-02-08 14:30 | 123 | complete | [link] | pending
   2026-02-08 15:45 | 124 | set-apart | [link] | pending
   ```
3. **Menu: MLS3 Reports → Generate Completion Report**
4. **Wait 5-10 seconds** (script reads calendar)
5. **View "Report" tab** with full details:
   ```
   Timestamp    | Member      | Type             | Date/Time  | Conductor | Action     | Status
   2026-02-08   | John Smith  | Temple Recommend | 2026-02-08 | Bishop    | complete   | pending
   2026-02-08   | Sarah Jones | Calling          | 2026-02-08 | Counselor | set-apart  | pending
   ```

6. **Export if needed:**
   - File → Download → CSV or PDF
   - Copy/paste into email or document

### Benefits for Clerk
- ✅ Self-service (no waiting for bishopric)
- ✅ Real-time access (see completions as they happen)
- ✅ Full details (names, types, dates)
- ✅ Exportable for records
- ✅ Better than GroupMe (organized, private, searchable)

---

## MLS3 Integration (Asynchronous)

### Background Polling
When MLS3 is running:
- Checks Google Sheet every 60 seconds
- Reads pending completions
- Updates appointment states in MLS3
- Marks sheet rows as "processed"
- Syncs back to Google Calendar

### Manual Sync
Optional button: "Sync Completions Now"
- Forces immediate check of sheet
- Updates all pending completions
- Useful if you want to manually trigger sync

### Key Point: MLS3 Doesn't Need to Run Immediately
- Conductors get instant confirmation
- Clerk can generate reports anytime
- MLS3 sync can happen hours or days later
- Everything still works

---

## Implementation Effort

### Setup Tasks

#### Phase 1: Google Sheet (10 minutes)
- Create Google Sheet "MLS3 Completions"
- Add header row
- Share with clerk (Editor access)

#### Phase 2: Google Apps Script (30 minutes)
- Create Apps Script project
- Add completion recording code (doGet function)
- Add clerk report generator code
- Deploy as web app
- Test with dummy data

#### Phase 3: MLS3 Code Changes (2 hours)
- Add completion link generation to calendar sync
- Create polling module
- Integrate poller into app startup
- Add manual sync endpoint

#### Phase 4: OAuth Permissions (5 minutes)
- Add Sheets API scope
- Re-authorize (grant Sheets permission)

#### Phase 5: Testing (30 minutes)
- Create test appointment
- Click completion link
- Verify sheet update
- Run clerk report
- Verify MLS3 sync

**Total Effort: ~3-3.5 hours**

### Files Created/Modified

**New Files:**
- `utils/completion_poller.py` (~100 lines)
- Google Apps Script `Code.gs` (~200 lines)
- This planning document

**Modified Files:**
- `utils/google_calendar.py` - Link generation, description formatting
- `app.py` - Start background poller
- `config.py` - Add COMPLETION_SHEET_ID

**No Database Changes:**
- No CSV schema changes
- No data migrations
- No new Python dependencies

---

## Rollback Plan

If the system doesn't work out:

1. **Stop MLS3 polling** - Restart Flask app without poller
2. **Remove links from calendar** - Stop generating completion links
3. **Keep or delete sheet** - Up to you
4. **No data loss** - All appointment data stays in MLS3

**Risk Level:** Low
- Isolated feature (doesn't affect core MLS3 functionality)
- Can be disabled without breaking anything
- Easy to revert

---

## Questions for Bishopric

### For Conductors
1. Would you use clickable links in calendar to record completions?
2. Is having multiple action options (complete/no-show/accepted/etc.) useful?
3. Would you prefer shorter URLs (using URL shortener)?

### For Clerk
1. Would self-service reports be helpful for your work?
2. How often would you want to generate reports? (Daily? Weekly?)
3. What information do you need most? (Names, dates, actions?)

### General Concerns
1. Any privacy concerns with this approach?
2. Any security concerns?
3. Would this replace GroupMe updates, or supplement them?

---

## Alternatives Considered

### Alternative 1: Manual Calendar Editing
**Idea:** Conductor changes `[Invited]` to `[Completed]` in calendar title

**Problem:** MLS3 would overwrite manual changes on next sync
**Verdict:** Doesn't work with current architecture

### Alternative 2: Direct MLS3 Access
**Idea:** Give conductors access to MLS3 app

**Problems:**
- App runs on your phone only (not accessible)
- Security concerns (all member data exposed)
- Complex UI for simple task
**Verdict:** Too complex, security concerns

### Alternative 3: SMS-Based Completion
**Idea:** Reply to SMS with "COMPLETE" or similar

**Problems:**
- Can't receive SMS on Termux easily
- Would need SMS parsing logic
- Less flexible (harder to support multiple actions)
**Verdict:** More complex than links

### Alternative 4: Separate Mobile App
**Idea:** Build custom mobile app for completion tracking

**Problems:**
- Requires app installation
- Major development effort
- Maintenance burden
**Verdict:** Overkill for this use case

---

## Future Enhancements (Optional)

### Phase 2: Enhanced Features
- **Email notifications** - Apps Script emails you when completion recorded
- **URL shortening** - Shorter, prettier links using TinyURL
- **Action-specific handling** - "accepted" creates calling record in MLS3
- **Weekly digest** - Automated email to clerk on Sundays

### Phase 3: Advanced Reporting
- **Trend analysis** - Charts showing completion rates over time
- **Conductor dashboard** - See your own completion history
- **Automatic reminders** - Email if appointment not marked complete within 24 hours

---

## Cost Analysis

**Development Time:** 3-3.5 hours (one-time)
**Ongoing Maintenance:** Minimal (<30 min/month)
**Financial Cost:** $0 (all services free)

**Google Services Used:**
- Google Sheets: Free, unlimited
- Google Apps Script: Free (20,000 executions/day)
- Google Calendar API: Free (existing usage)

**Return on Investment:**
- Time saved per appointment: ~2-5 minutes (no manual data entry)
- Clerk time saved: ~30-60 minutes/week (self-service reports)
- **ROI:** Pays for itself after first week of use

---

## Next Steps

### Before Implementation
1. ✅ **Review this plan with bishopric** (get feedback)
2. ✅ **Get buy-in from conductors** (would they use it?)
3. ✅ **Confirm clerk needs** (is this useful for them?)
4. ✅ **Address any concerns** (privacy, security, usability)

### After Approval
1. Set up Google Sheet
2. Create and deploy Apps Script
3. Modify MLS3 code
4. Test with one or two appointments
5. Roll out to all appointments
6. Train conductors (show them how to tap links)
7. Train clerk (show them how to run reports)

---

## Contact for Questions

**Document Created:** 2026-02-08
**Author:** Claude (AI Assistant)
**For:** MLS3 Appointment Completion Tracking

**Questions or Concerns:**
- Review with bishopric in person
- Test with small group first
- Can always roll back if it doesn't work

---

## Appendix: Technical Details

### Google Apps Script Code Structure
```javascript
// Part 1: Public web app (doGet function)
// - Receives link clicks
// - Validates inputs
// - Stores to private sheet
// - Returns confirmation page

// Part 2: Clerk report generator
// - Reads completions from sheet
// - Fetches calendar event details
// - Generates formatted report
// - Exports to "Report" tab
```

### MLS3 Polling Logic
```python
# Background thread runs while Flask active
# Every 60 seconds:
#   1. Read sheet for pending rows
#   2. Update appointment states in MLS3
#   3. Mark rows as processed
#   4. Sync back to calendar
```

### Data Flow Diagram
```
Conductor          Apps Script         Google Sheet       Clerk             MLS3
   |                    |                    |              |                |
   |--- click link ---->|                    |              |                |
   |                    |--- append row ---->|              |                |
   |<--- confirm -------|                    |              |                |
   |                                         |              |                |
   |                                         |<-- generate  |                |
   |                                         |    report ---|                |
   |                                         |              |                |
   |                                         |<------------ poll ------------|
   |                                         |--- mark as processed -------->|
```

### Security Model
```
Public → Apps Script (runs with your permissions) → Private Sheet
  ↑                                                        ↓
  └─────────── No direct access to sheet ─────────────────┘
```

---

## Implementation Status

### Current Phase: Planning Complete
- ✅ System architecture designed
- ✅ Security model defined
- ✅ User experience flows documented
- ✅ Mobile interaction patterns specified
- ✅ Questions for bishopric prepared

### Next Steps
1. **Present to bishopric** for buy-in and approval
   - Review completion tracking benefits
   - Discuss security and privacy considerations
   - Address any concerns about Google Sheets access
   - Get approval to proceed with implementation

2. **Implementation** (once approved)
   - Create Google Sheet for completion tracking
   - Write and deploy Google Apps Script
   - Add completion links to calendar event descriptions
   - Implement MLS3 polling system
   - Add completion status to appointment UI
   - Test end-to-end workflow

3. **Testing & Rollout**
   - Test with sample appointments
   - Verify conductor mobile experience
   - Test clerk reporting workflow
   - Document for bishopric training
   - Deploy to production

### Dependencies
- **Blocked by**: Bishopric approval
- **Requires**: Google Calendar integration (Phase 2 - ✅ Complete)
- **Enables**: Self-service clerk reporting, automated completion tracking

---

**End of Planning Document**
*Last Updated: February 8, 2026*
*Status: Phase 3 - Planned, awaiting approval*
