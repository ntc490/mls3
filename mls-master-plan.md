# MLS3 Master Plan

## Project Overview
MLS3 (Member Leadership Scheduling System v3) is a church scheduling and communication management tool designed to run in Termux on Android. The system helps coordinate various church activities, track member availability, send SMS communications, and manage calendar appointments.

## Technology Stack
- **Language**: Python 3
- **Web Framework**: Flask (mobile-responsive web UI)
- **Data Storage**: CSV files
- **SMS**: Android intents via termux-api
- **Calendar**: Google Calendar link generation (with future API integration planned)
- **Deployment**: Termux on Android phone
- **Development**: Prototype on computer, deploy to phone

## Core Design Principles
1. **Flexible, non-linear data entry** - "bubble" interface where fields can be edited in any order
2. **Manual state management** - user always controls state transitions
3. **CSV-based persistence** - simple, editable, portable data format
4. **Template-driven SMS** - configurable message templates per activity state
5. **Mobile-first UI** - optimized for phone screen usage

---

## Data Management

### Data Storage Strategy

**Separation of Code and Data:**
- **Code Repository** (git): All application code, mock data for development
- **Production Data** (outside git): Real member data stored separately, never committed

**Directory Structure:**
```
/home/nlod/
├── claude/mls3/              # Git repository
│   ├── .git/
│   ├── .gitignore            # Excludes production data
│   ├── app.py
│   ├── models.py
│   ├── config.py
│   ├── data/                 # Mock data for development (IN git)
│   │   ├── members.example.csv
│   │   ├── prayer_assignments.example.csv
│   │   └── message_templates.yaml
│   └── ...
└── mls3-data/                # Production data (NOT in git)
    ├── members.csv
    ├── prayer_assignments.csv
    ├── message_templates.yaml (copy from repo, customize)
    └── backups/
        ├── members_2026-02-05.csv
        └── prayer_assignments_2026-02-05.csv
```

**Configuration (config.py):**
```python
import os

# Data directory - defaults to development mock data
# Set MLS3_DATA_DIR environment variable for production
DATA_DIR = os.getenv('MLS3_DATA_DIR', './data')

# Usage in development:
#   python app.py
#   (uses ./data/ with mock data)

# Usage in production (Termux):
#   export MLS3_DATA_DIR=/home/nlod/mls3-data
#   python app.py
#   (uses real data from separate directory)
```

**Benefits:**
- Sensitive member data never committed to git
- Easy development with mock data (no setup required)
- Production data can live anywhere (Termux storage, SD card, cloud-synced folder)
- User controls backup strategy for production data
- Custom utility scripts can work with either mock or production data

**Backup Strategy (User Managed):**
- Manual file copies to cloud storage (Dropbox, Google Drive)
- Automated backups via separate scripts (user-created)
- Version snapshots saved in `backups/` subdirectory
- Git for code only, not data

---

## Data Model

### Member Database (members.csv)
Primary database of all church members with fields:
- `member_id` - Unique identifier
- `first_name` - Member's first name
- `last_name` - Member's last name
- `gender` - M/F for candidate selection
- `phone` - Mobile phone number for SMS
- `birthday` - Date of birth
- `recommend_expiration` - Temple recommend expiration date
- `last_prayer_date` - Last date they gave a prayer (for rotation tracking)
- `dont_ask_prayer` - Boolean flag (never ask for prayers)
- `active` - Boolean flag (currently active member)
- `notes` - Free-form notes field

**Data Sync**: Ongoing capability to import/merge CSV data from church website

### Prayer Assignments (prayer_assignments.csv)
Tracks all prayer assignments (past, present, future):
- `assignment_id` - Unique identifier
- `member_id` - Foreign key to members.csv
- `date` - Sunday date for the prayer
- `prayer_type` - Opening/Closing/Undecided
- `state` - Current assignment state (see workflow below)
- `created_date` - When assignment was created
- `last_updated` - Last state change timestamp
- `completed_date` - When marked complete (null until done)

### Message Templates (message_templates.yaml)
Configurable SMS message templates for each activity and state:
```yaml
prayer:
  invite: "Hi {first_name}, would you be willing to say a prayer in sacrament meeting on {date}? Please let me know if opening or closing works better for you."
  reminder: "Hi {first_name}, just a reminder that you're scheduled for the {prayer_type} prayer in sacrament meeting today. Thank you!"
  thank_you: "Thanks {first_name} for agreeing to say the {prayer_type} prayer on {date}!"
```

---

## Phase 1: Prayer Scheduling (Current Focus)

### Problem Statement
Need to schedule opening and closing prayers for sacrament meeting each week with:
- Fair rotation (each member ~once per year)
- Gender balance (typically one man, one woman)
- Short-term scheduling (Wednesday-Saturday for upcoming Sunday)
- SMS coordination and negotiation
- Reminder capability

### Prayer Assignment Workflow States

**Simplified State Flow:**

```
    ┌───────┐
    │ Draft │  (person selected, prayer type set)
    └───┬───┘
        │
        │ [Invite Button]
        │ (sends SMS)
        ↓
   ┌─────────┐
   │ Invited │  (awaiting response, negotiate via SMS)
   └────┬────┘
        │
        ├─→ [Accept Button] ──→ (manually press after they agree)
        │                       ↓
        │                   ┌──────────┐
        │                   │ Accepted │
        │                   └─────┬────┘
        │                         │
        │                         ├─→ [Remind Button] ──→ (send Sunday reminder)
        │                         │                        ↓
        │                         │                   ┌──────────┐
        │                         │                   │ Reminded │
        │                         │                   └─────┬────┘
        │                         │                         │
        │                         ├─→ [Complete Button] ────┤
        │                         │                         │
        │                         └─→ [Cancel Button] ──┐   │
        │                                                │   │
        └─→ [Decline Button] ──┐                        │   │
                                │                        │   │
                                ↓                        ↓   ↓
                            (back to Draft)          (back) │
                            (clear person)          to Draft│
                                                             │
                                                             ↓
                                                       ┌───────────┐
                                                       │ Completed │
                                                       └───────────┘
                                                       (disappears Sunday evening,
                                                        updates last_prayer_date)
```

**State Definitions:**
1. **Draft** - Assignment created, person may or may not be selected, prayer type may be Undecided
2. **Invited** - Initial SMS request sent to member, awaiting their response
3. **Accepted** - Member confirmed they'll do it, prayer type finalized (Opening or Closing)
4. **Reminded** - Sunday reminder SMS sent
5. **Completed** - Prayer given, assignment finished

**Available Actions by State:**
- **Draft**: [Invite] - sends invitation SMS, moves to Invited
- **Invited**: [Accept] - manually press after member agrees via SMS, moves to Accepted
- **Invited**: [Decline] - member said no, clears person, back to Draft
- **Accepted**: [Remind] - send Sunday morning reminder, moves to Reminded
- **Accepted**: [Complete] - mark prayer as done, moves to Completed
- **Accepted**: [Cancel] - member backed out, back to Draft
- **Reminded**: [Complete] - mark prayer as done, moves to Completed
- **Reminded**: [Cancel] - member backed out, back to Draft

### UI Design: Bubble/Card Interface

#### Current Week View (Main Focus)
Display two assignment cards side-by-side (if space) or stacked:

```
┌─────────────────────────────────────────┐
│  Opening Prayer - Feb 9, 2026           │
│  ┌──────────────┐ ┌────────┐ ┌────────┐│
│  │   Person     │ │  Date  │ │  Type  ││
│  │ Jane Doe     │ │ Feb 9  │ │Opening ││
│  │ (last: 3/15) │ │        │ │        ││
│  └──────────────┘ └────────┘ └────────┘│
│  State: Invited                         │
│  [Accept] [Decline]                     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Closing Prayer - Feb 9, 2026           │
│  ┌──────────────┐ ┌────────┐ ┌────────┐│
│  │   Person     │ │  Date  │ │  Type  ││
│  │ [Select]     │ │ Feb 9  │ │Closing ││
│  │              │ │        │ │        ││
│  └──────────────┘ └────────┘ └────────┘│
│  State: Draft                           │
│  [Next Up: John Smith (last: 2/1),     │
│   Mike Jones (last: 4/12)]             │
└─────────────────────────────────────────┘
```

#### Editable Bubbles/Fields
Each bubble is clickable/tappable to edit:

**Person Bubble**:
- Initially shows "next up" candidates (2-3 per gender)
- Displays: "Jane Doe (last: 2024-03-15)" with last prayer date
- Click to expand selection:
  - Shows next-up candidates at top
  - Fuzzy search box to find anyone
  - Warning icon if person already scheduled or recently prayed
- Selecting a person updates the bubble

**Date Bubble**:
- Defaults to upcoming Sunday
- Click to open date picker
- Can select future Sunday if member offers alternate date

**Prayer Type Bubble**:
- Options: Undecided / Opening / Closing
- Initial state: Undecided (before negotiating via SMS)
- Changes to Opening or Closing after negotiation
- Click to toggle between Opening/Closing

#### Contextual Action Buttons
Actions appear based on assignment completeness and current state:

**From Draft State**:
- [Invite] - Enabled when person selected and prayer type set (even if Undecided)
  - Opens SMS app with invitation template
  - Moves to Invited state

**From Invited State**:
- [Accept] - Member agreed via SMS negotiation
  - Must set prayer type (Opening/Closing) before accepting if still Undecided
  - Moves to Accepted state
- [Decline] - Member declined
  - Clears person selection
  - Returns to Draft state

**From Accepted State**:
- [Remind] - Send Sunday morning reminder
  - Opens SMS app with reminder template
  - Moves to Reminded state
- [Complete] - Prayer was given
  - Updates member's last_prayer_date in database
  - Moves to Completed state
  - Assignment disappears from UI after Sunday
- [Cancel] - Member backed out
  - Clears person selection
  - Returns to Draft state

**From Reminded State**:
- [Complete] - Prayer was given
  - Updates member's last_prayer_date
  - Moves to Completed state
- [Cancel] - Member backed out
  - Clears person selection
  - Returns to Draft state

#### Active Queue Display
Below the current week cards, show assignments in progress:

```
┌─────────────────────────────────────┐
│ Active Queue                        │
├─────────────────────────────────────┤
│ Feb 16 - Opening - Bob Smith       │
│ State: Accepted          [View]    │
├─────────────────────────────────────┤
│ Feb 23 - Closing - Mary Johnson    │
│ State: Invited           [View]    │
└─────────────────────────────────────┘
```

- Collapsed cards showing date, type, person, state
- Click [View] to expand and edit
- Future assignments stay here until their week arrives
- Then they move to "Current Week" focus area

#### Candidate Selection Algorithm
```python
def get_next_candidates(gender, count=3):
    """
    Get the next eligible candidates for prayer assignment.

    Returns members sorted by last_prayer_date (oldest first).
    Excludes anyone currently in active queue or marked dont_ask.
    """
    # Get all eligible members
    eligible = members.filter(
        gender=gender,
        active=True,
        dont_ask_prayer=False
    )

    # Exclude anyone currently in active assignments
    eligible = exclude_active_assignments(eligible)

    # Sort by last_prayer_date (oldest first, nulls first)
    # Nulls = never prayed, they go first
    eligible = eligible.sort(
        key=lambda m: m.last_prayer_date or date.min
    )

    return eligible[:count]
```

### SMS Integration Flow
1. User clicks action button (e.g., "Invite" or "Remind")
2. System generates SMS with expanded template:
   - Replaces `{first_name}`, `{date}`, `{prayer_type}` etc.
3. Opens Android SMS app via termux intent:
   ```python
   intent = f"sms:{phone_number}?body={url_encoded_message}"
   subprocess.run(['termux-open-url', intent])
   ```
4. User reviews message, potentially edits it
5. User manually taps "Send" in SMS app (or cancels)
6. User presses back button to return to MLS3 app
7. User manually updates assignment state with appropriate button
   - After sending invite: wait for response (no state change yet)
   - After member agrees via SMS: press [Accept] button
   - After sending reminder: press [Remind] button (if not auto-changed)

### Assignment Lifecycle
- **Wednesday-Saturday**: Create Draft assignments, send invites, negotiate, get acceptances
- **Focus**: Stay on current Sunday until both Opening and Closing are Accepted
- **Future Commitments**: If member offers different date, create assignment for that date
  - It moves to Active Queue
  - Doesn't block current week's progress
- **Sunday Morning**: Send reminders to Accepted assignments
- **Sunday During Meeting**: Prayers happen
- **Sunday Evening**: Mark as Complete, assignments disappear from UI
- **Rotation Update**: Completed prayer updates member's `last_prayer_date` for fair rotation

---

## Future Activities (Phase 2+)

These activities are documented for future planning but not yet implemented:

### Interview/Meeting Types
1. **Youth Interviews** - Regular interviews with youth (scheduled periodically)
2. **Temple Recommend Interviews** - Based on expiration tracking from member database
3. **Calling Interviews** - When extending new callings to members
4. **Setting Apart Meetings** - After calling is accepted, schedule setting apart
5. **Mission Interviews** - Pre-mission preparation interviews
6. **Ecclesiastical Interviews** - General leadership interviews (on-demand)
7. **Baptism Interviews** - Pre-baptism interviews (on-demand)
8. **Family Visits** - Home visits/ministering coordination

### Common Interview Features (Future Design)
Each activity type will likely need:
- Similar bubble/card interface pattern
- Activity-specific workflow states
- SMS message templates per state and activity
- Google Calendar integration (link generation → full API later)
- Scheduling constraints:
  - Some weekly (youth interviews)
  - Some on-demand (calling interviews)
  - Some scheduled per member based on dates (temple recommend expirations)
- Reminder queues per activity type
- Notes/documentation fields
- Duration/location fields

### Future Enhancements (Post Phase 2)
- **Google Calendar API Integration** - Direct event creation/updates (not just links)
- **Google Docs Integration** - Automated announcement document updates
- **Batch Reminders** - Send reminders to multiple people at once
- **Analytics/Reporting** - Track completion rates, response times, rotation fairness
- **Auto-start Script** - Termux service that starts Flask on device boot
- **Data Export Tools** - Generate reports, backup data to cloud
- **Import/Sync Improvements** - Better church website CSV sync, conflict resolution

---

## File Structure
```
mls3/
├── mls-master-plan.md          # This document
├── app.py                       # Flask application entry point
├── models.py                    # Data models and CSV handling
├── routes.py                    # Web routes and API endpoints
├── templates/                   # HTML templates (Jinja2)
│   ├── base.html               # Base template with mobile-responsive layout
│   ├── prayer_scheduler.html  # Main prayer scheduling interface
│   └── member_search.html      # Fuzzy search modal for member selection
├── static/                      # CSS, JS, images
│   ├── css/
│   │   └── style.css           # Mobile-responsive styles
│   └── js/
│       └── app.js              # Client-side interactivity (HTMX or vanilla JS)
├── data/                        # CSV data files
│   ├── members.csv             # Member database
│   ├── prayer_assignments.csv # Prayer assignment tracking
│   └── message_templates.yaml # SMS message templates
├── utils/                       # Utility scripts
│   ├── import_members.py       # CSV import/merge tool for church data
│   ├── sms_handler.py          # SMS intent generation and template expansion
│   └── candidate_selector.py  # Next-up algorithm implementation
├── config.py                    # Configuration settings
├── requirements.txt             # Python dependencies
└── README.md                    # Setup and usage instructions
```

---

## Development Phases

### Phase 1a: Core Infrastructure (Foundation)
**Goal**: Get Flask app running with basic routing and CSV data access

Tasks:
- Set up Python virtual environment
- Install Flask and dependencies (PyYAML, etc.)
- Create `app.py` with Flask app skeleton
- Create `config.py` with basic settings
- Create `models.py` with CSV data models:
  - Member class with CSV read/write
  - PrayerAssignment class with CSV read/write
  - MessageTemplate class with YAML read
- Create basic `templates/base.html` with mobile-responsive layout
- Create `static/css/style.css` with mobile-first styles
- Test: Can run Flask and see homepage

### Phase 1b: Member Database & Import
**Goal**: Load and manage member data

Tasks:
- Define `members.csv` schema
- Create sample member data for testing
- Implement `utils/import_members.py` script:
  - Read CSV from church website export
  - Transform/map fields to our schema
  - Merge with existing data
- Implement member CRUD operations in models
- Create member list view (for testing)
- Test: Can import members and view them

### Phase 1c: Prayer Scheduler UI - Draft State
**Goal**: Build the "Current Week" interface with editable bubbles

Tasks:
- Create `templates/prayer_scheduler.html`
- Implement two assignment cards (Opening, Closing)
- Create editable bubbles:
  - Person bubble (click to select)
  - Date bubble (click for date picker)
  - Prayer type bubble (click to toggle)
- Implement "next up" candidate display
- Show available actions based on state (Draft = [Invite])
- Test: Can create draft assignments by selecting people

### Phase 1d: Candidate Selection Algorithm
**Goal**: Implement fair rotation logic

Tasks:
- Implement `utils/candidate_selector.py`
- `get_next_candidates()` function:
  - Filter by gender, active, dont_ask_prayer
  - Exclude currently assigned people
  - Sort by last_prayer_date (nulls first)
  - Return top N candidates
- Integrate with Person bubble display
- Show last prayer date with each candidate
- Add fuzzy search for manual selection
- Test: Candidates rotate fairly based on last prayer date

### Phase 1e: SMS Integration
**Goal**: Generate and send SMS via Android intents

Tasks:
- Create `message_templates.yaml` with prayer templates
- Implement `utils/sms_handler.py`:
  - Load templates from YAML
  - Expand template variables ({first_name}, {date}, etc.)
  - Generate termux intent URL
  - Launch SMS app via subprocess
- Wire up [Invite] button to SMS handler
- Wire up [Remind] button to SMS handler
- Test: Can send SMS invitations and reminders

### Phase 1f: State Management & Workflow
**Goal**: Complete the full assignment lifecycle

Tasks:
- Implement all state transitions in backend
- Wire up action buttons:
  - Draft: [Invite] → Invited
  - Invited: [Accept] → Accepted
  - Invited: [Decline] → Draft (clear person)
  - Accepted: [Remind] → Reminded
  - Accepted: [Complete] → Completed
  - Accepted: [Cancel] → Draft
  - Reminded: [Complete] → Completed
  - Reminded: [Cancel] → Draft
- Update member's `last_prayer_date` on completion
- Hide completed assignments after Sunday
- Test: Can complete full workflow from draft to completion

### Phase 1g: Active Queue & Multi-Week Support
**Goal**: Handle future assignments and queue display

Tasks:
- Create Active Queue display section
- Show all non-Draft, non-Completed assignments
- Implement [View] button to expand/edit queued assignment
- Support creating assignments for future Sundays
- Automatically promote future assignments to "Current Week" when their week arrives
- Test: Can schedule multiple weeks, assignments move correctly

### Phase 1h: Polish & Mobile Optimization
**Goal**: Make UI smooth and usable on phone

Tasks:
- Refine mobile touch targets (min 44x44px)
- Add loading indicators for SMS intents
- Improve date picker for mobile
- Add confirmation dialogs for destructive actions (Cancel, Decline)
- Add visual feedback for state changes
- Optimize for portrait orientation
- Test: Use on actual Android phone in Termux

### Phase 1i: Testing & Documentation
**Goal**: Real-world usage and documentation

Tasks:
- Deploy to Termux on Android phone
- Create README.md with setup instructions:
  - Termux installation
  - Python setup
  - termux-api setup
  - Running the app
  - Data management
- Create user guide for prayer scheduling workflow
- Real-world testing with actual prayer scheduling
- Bug fixes and refinements
- Test: Successfully schedule prayers for multiple weeks

### Phase 2+: Additional Activities
*To be planned after Phase 1 is complete and validated*

Approach:
1. Pick one interview type as template (e.g., Temple Recommend Interviews)
2. Design its specific workflow and states
3. Create activity-specific UI (may reuse bubble pattern)
4. Implement SMS templates for that activity
5. Add Google Calendar integration
6. Replicate pattern for other interview types
7. Consider shared components and abstractions

---

## Technical Considerations

### Termux Setup Requirements
- **Termux app** - Terminal emulator for Android
- **Termux:API** - Add-on for Android integration (SMS, intents, etc.)
- **Python 3.x** - `pkg install python`
- **Flask** - `pip install flask`
- **PyYAML** - `pip install pyyaml` (for message templates)
- **Storage access** - `termux-setup-storage` for saving data

### Running the App in Termux
```bash
# Navigate to project directory
cd ~/storage/shared/mls3

# Activate virtual environment
source venv/bin/activate

# Run Flask app
python app.py

# Open browser to localhost
termux-open-url http://localhost:5000
```

### Mobile UI Design Guidelines
- **Touch targets**: Minimum 44x44px for buttons and interactive elements
- **Font sizes**: Minimum 16px to prevent auto-zoom on iOS
- **Viewport**: `<meta name="viewport" content="width=device-width, initial-scale=1">`
- **Layout**: Single column, minimal scrolling, critical info above fold
- **Performance**: Minimize JavaScript, prefer server-side rendering
- **Offline**: Works without internet (local Flask server)

### Data Management Strategy
**Why CSV?**
- Human-readable and editable with any text editor
- Easy to backup (git, Dropbox, Google Drive)
- Simple to debug and inspect
- No database server required
- Portable across systems

**CSV Operations**:
- Read entire file into memory (small datasets)
- Use Python's `csv.DictReader` and `csv.DictWriter`
- Implement locking for write operations (prevent concurrent edits)
- Validate data on load, handle missing fields gracefully

**Import/Merge Logic**:
```python
def merge_members(existing_csv, new_csv):
    # Load existing members
    existing = load_members(existing_csv)

    # Load new members from church website
    new = load_members(new_csv)

    # Match by name or ID
    for new_member in new:
        if new_member.id in existing:
            # Update fields: phone, birthday, recommend_expiration
            # Preserve: last_prayer_date, dont_ask_prayer, notes
            update_member(existing[new_member.id], new_member)
        else:
            # New member, add to database
            add_member(new_member)

    # Save merged data
    save_members(existing_csv, existing)
```

### SMS Template Variables
Standard variables available in all templates:
- `{first_name}` - Member's first name
- `{last_name}` - Member's last name
- `{date}` - Formatted date (e.g., "February 9")
- `{prayer_type}` - "opening" or "closing"
- `{day_of_week}` - "Sunday" (for prayers)

Activity-specific variables (future):
- `{time}` - Appointment time
- `{location}` - Meeting location
- `{duration}` - Meeting duration

### Android Intent for SMS
```python
import subprocess
from urllib.parse import quote_plus

def send_sms_intent(phone_number, message):
    """
    Opens Android SMS app with pre-filled message.
    User must manually press send.
    """
    # URL encode the message
    encoded_message = quote_plus(message)

    # Create SMS intent URL
    intent_url = f"sms:{phone_number}?body={encoded_message}"

    # Launch via termux-open-url
    subprocess.run(['termux-open-url', intent_url])

    # User is now in SMS app
    # When they press back, they return to browser/MLS3 app
```

### Google Calendar Link Generation (Phase 1)
```python
from datetime import datetime
from urllib.parse import urlencode

def create_calendar_link(title, start_datetime, end_datetime, description="", location=""):
    """
    Generates a Google Calendar link that opens in browser.
    User clicks to add event to their calendar.
    """
    base_url = "https://calendar.google.com/calendar/render"

    params = {
        'action': 'TEMPLATE',
        'text': title,
        'dates': f"{format_datetime(start_datetime)}/{format_datetime(end_datetime)}",
        'details': description,
        'location': location
    }

    return f"{base_url}?{urlencode(params)}"

def format_datetime(dt):
    """Format datetime for Google Calendar: YYYYMMDDTHHMMSSZ"""
    return dt.strftime('%Y%m%dT%H%M%SZ')
```

---

## Open Questions / Future Decisions

### Announcement Document Updates
**Question**: How should we handle updating the prayer announcement document?

**Options**:
1. Manual entry (user copies names from MLS3 to document)
2. Generate plain text output (user copy-pastes)
3. Google Docs API integration (auto-update document)

**Decision**: Start with manual entry. Can add text generation or API later.

### Multi-Week Planning
**Question**: Should we support scheduling many weeks ahead?

**Current Plan**: Focus on one week at a time, but allow future commitments via Active Queue

**Future**: Could add a "calendar view" to see multiple weeks at once

### Backup Strategy
**Question**: How to backup CSV data files?

**Options**:
1. Manual: User copies files to cloud storage
2. Git integration: Auto-commit changes
3. Dropbox/Drive sync: Store data folder in synced directory

**Decision**: Start manual, user's choice for backup method

### SMS Intent Failure Handling
**Question**: What if termux-open-url fails or SMS app doesn't open?

**Strategy**:
- Show error message in UI
- Provide fallback: display phone number and message text for manual copy
- Log errors for debugging

### State Conflict Resolution
**Question**: What if data becomes inconsistent (e.g., two people assigned to same slot)?

**Strategy**:
- UI should prevent this (disable conflicting actions)
- Backend validation before state changes
- If it happens, show warning in UI, let user resolve manually
- CSV is source of truth, reload if needed

### Date Handling - Week Boundaries
**Question**: When does a week transition from "current" to "past"?

**Decision**:
- Sunday evening at 11:59 PM
- Completed assignments disappear after this time
- Next Sunday becomes "current week"
- Could make this configurable (e.g., Monday morning)

---

## Success Criteria (Phase 1)

Prayer scheduling system is considered successful when:
1. ✅ Can schedule both opening and closing prayers for upcoming Sunday
2. ✅ System suggests next-up candidates based on fair rotation (oldest last_prayer_date first)
3. ✅ Can send SMS invitations with one tap, message opens in SMS app
4. ✅ Can track assignment states through complete workflow (Draft → Invited → Accepted → Reminded → Completed)
5. ✅ Can send Sunday reminders with one tap
6. ✅ Rotation tracking automatically updates when prayers marked completed
7. ✅ UI is usable on phone without frustration (mobile-responsive, touch-friendly)
8. ✅ Faster than current spreadsheet + manual SMS method
9. ✅ Can handle member declining and quickly find replacement
10. ✅ Can schedule future weeks when member offers alternate date

---

## Notes & Observations

### Design Philosophy
- **Keep UI simple and utilitarian** - Not flashy, just functional
- **Minimize typing** - Use fuzzy search, defaults, button selections
- **Manual control** - No automation surprises, user always in control
- **Flexible workflow** - Can edit any field any time, order doesn't matter
- **Focus on current task** - Current week is primary, future goes to queue
- **Fast feedback** - Quick tap-to-action, immediate visual updates

### Lessons from Current Process
- Spreadsheet tracking works but requires multiple tools
- Manual SMS is error-prone (typos, wrong numbers)
- Negotiation happens over SMS (can't automate this)
- Members sometimes decline (need quick recovery)
- Members sometimes offer alternate dates (need to track future)
- Reminders are important (easy to forget on Sunday morning)
- Rotation fairness matters (people notice if asked too often)

### Unique Challenges
- **Mobile-only usage** - Must work perfectly on phone screen
- **SMS round-trip** - Leave app, send SMS, return, update state
- **Non-linear workflow** - Can't predict order of data entry
- **Fair rotation with exceptions** - "Don't ask" flag, gender balance
- **Real-time coordination** - Often happens same week, sometimes day-of

### Future Extensibility
- Pattern established with prayers can extend to interviews
- SMS template system works for any activity
- Bubble UI pattern reusable for different data types
- State machine approach generalizes well
- CSV structure allows adding new activity types easily

---

## Revision History

- **2026-02-05 (v1.1)**: Added data management strategy
  - Documented code/data separation approach
  - Added config-based DATA_DIR with environment variable support
  - Specified mock data in git, production data outside git
  - Defined .gitignore strategy for sensitive data protection

- **2026-02-05 (v1.0)**: Initial master plan created
  - Defined project scope and Phase 1 goals
  - Documented simplified state workflow (Draft → Invited → Accepted → Reminded → Completed)
  - Specified bubble/card UI design
  - Outlined candidate selection algorithm
  - Documented future activities for planning
  - Status: Planning complete, ready to begin Phase 1a implementation

---

*Document Status: Planning Phase Complete*
*Next Step: Begin Phase 1a - Core Infrastructure*
