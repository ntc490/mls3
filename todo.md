# MLS3 Todo List

## Current Status
- ✅ **Phase 1 Complete** - Prayer Scheduling (February 6, 2026)
- ✅ **Phase 2 Complete** - Appointment Management with Google Calendar (February 8, 2026)
- 📋 **Phase 3 Planned** - Completion Tracking (awaiting approval)

---

## Phase 3: Completion Tracking (Not Yet Started)

**Status**: Waiting for bishopric buy-in before implementation

**Detailed Plan**: See `docs/COMPLETION_TRACKING_PLAN.md`

### Tasks
- [ ] Get bishopric approval for completion tracking system
- [ ] Create Google Sheet for completion tracking
- [ ] Deploy Google Apps Script as web endpoint
- [ ] Add completion links to calendar event descriptions
- [ ] Implement MLS3 polling of Google Sheet
- [ ] Add completion status to appointment UI
- [ ] Test end-to-end completion workflow
- [ ] Add clerk self-service reporting
- [ ] Update documentation

---

## Testing & Quality Assurance

### Outstanding Testing Tasks
- [ ] Test what happens when week passes (time-expired events cleanup)
- [ ] Test prayer assignments past Sunday midnight (disappear from UI)
- [ ] Test appointment timezone handling across DST boundary
- [ ] Long-term testing with real member data
- [ ] Battery drain testing on Termux (multiple hours of use)

### Desktop Testing
- [x] Prayer scheduling workflow (complete)
- [x] SMS debug mode (complete)
- [x] Member management and import (complete)
- [x] Appointment scheduling workflow (complete)
- [x] Google Calendar sync (complete)

### Termux Testing (User to Complete)
- [ ] Deploy to Termux on Android
- [ ] Test actual SMS sending with own number
- [ ] Test Google Calendar sync on Termux
- [ ] Test OAuth token persistence across app restarts
- [ ] Performance testing on phone

---

## Future Enhancements (Post Phase 3)

### High Priority Features

#### Household Lookups for Youth Protection
**Priority**: High - Safeguarding feature

Youth protection when scheduling appointments with minors:
- [ ] Import household data from church CSV
  - Parent/guardian relationships
  - Household groupings
- [ ] Extend member database schema
  - Add `household_id` field
  - Add `parent_member_ids` field (for minors)
  - Add `is_minor` flag (age-based or manual)
- [ ] Update appointment scheduling UI
  - When selecting a minor, automatically show parent/guardian
  - Require parent selection for minor appointments
  - Display warning if attempting to contact minor directly
- [ ] SMS logic updates
  - Route all youth appointment SMS to parent/guardian
  - Include both youth and parent names in message
  - Template variables: `{youth_name}`, `{parent_name}`
- [ ] Member search improvements
  - Show household context in search results
  - "Search households" option
  - Filter: "Youth only" / "Adults only" / "All"
- [ ] Import script updates
  - Parse household relationships from church data
  - Match parents to children
  - Validate household integrity

**Use Cases**:
- Youth interviews → contact parents
- Temple recommend (youth) → contact parents
- Youth callings → contact parents
- Never send SMS directly to minors

#### Command-Line Interface Enhancement
**Priority**: Medium-High - Quality of life improvement

Transform MLS3 into a proper CLI tool for easier Termux usage:

**1. Shell Environment Setup**
- [ ] Add Zsh configuration (if user prefers zsh over bash)
  - Custom prompt showing MLS3 context
  - Useful aliases (mls3-start, mls3-backup, mls3-import, etc.)
  - Environment variable setup in .zshrc
- [ ] Add Bash completions (or Zsh completions)
  - Tab completion for commands
  - Tab completion for member names
  - Tab completion for appointment types

**2. CLI Script Restructuring**
- [ ] Rename utility scripts to CLI commands
  - `import_members.py` → `mls3-import`
  - `authorize_google_calendar.py` → `mls3-auth-calendar`
  - Add `mls3-backup`, `mls3-restore`, `mls3-report`, etc.
- [ ] Create main `mls3` CLI entry point
  - `mls start` - Start Flask server
  - `mls import <file>` - Import members
  - `mls backup` - Backup data
  - `mls restore <backup>` - Restore from backup
  - `mls auth calendar` - Authorize Google Calendar
  - `mls status` - Show system status
  - `mls config` - Show/edit configuration
  - `mls --help` - Show all commands

**3. Argument Parsing with argcomplete**
- [ ] Install and configure argcomplete
- [ ] Add argparse to all CLI scripts
  - Proper help messages
  - Argument validation
  - Flag support (--dry-run, --verbose, --quiet, etc.)
- [ ] Enable shell completion for all commands

**4. SSH Server for Remote Access**
- [ ] Install and configure OpenSSH in Termux
  - `pkg install openssh`
  - Configure sshd
  - Set up key-based authentication
- [ ] Documentation for SSH access
  - How to connect from desktop
  - Port forwarding for web UI access
  - Security best practices
- [ ] Optional: Tailscale integration
  - Secure remote access without port forwarding
  - Access MLS3 web UI from anywhere

**5. Additional CLI Features**
- [ ] Interactive member search from command line
  - `mls3 search "john smith"`
- [ ] Quick appointment creation
  - `mls3 appointment create --member "John Doe" --type "Temple Recommend" --date tomorrow --time 3pm`
- [ ] Prayer assignment from CLI
  - `mls3 prayer assign --opening "Jane Smith" --closing "Bob Jones" --date sunday`
- [ ] Status dashboard in terminal
  - Show upcoming prayers
  - Show upcoming appointments
  - Show pending invitations
- [ ] Log viewing
  - `mls3 logs` - Show recent Flask logs
  - `mls3 logs --follow` - Tail logs in real-time

**Benefits**:
- ✅ Faster workflow (no opening browser for simple tasks)
- ✅ Better Termux experience (proper CLI tool)
- ✅ Remote access via SSH (work from desktop)
- ✅ Professional CLI interface
- ✅ Tab completion makes it easier to use
- ✅ Scriptable (can automate tasks)

### Other Potential Features
- [ ] Google Docs integration (automated announcements)
- [ ] Batch reminders (send to multiple people at once)
- [ ] Analytics and reporting
  - Completion rates by member
  - Response time tracking
  - Rotation fairness metrics
- [ ] Auto-start service (Termux:Boot integration)
- [ ] Automated backup system
  - Schedule backups to cloud storage
  - Backup verification
- [ ] Import/sync improvements
  - Better conflict resolution
  - Incremental updates
  - Change detection

### Mobile UI Improvements
- [ ] Swipe gestures for common actions
- [ ] Dark mode support
- [ ] Offline indicators
- [ ] Better loading states
- [ ] Toast notifications for actions

### Additional Interview/Meeting Types
Only implement if needed by user:
- [ ] Youth Interview tracking
- [ ] Mission Interviews
- [ ] Ecclesiastical Interviews
- [ ] Baptism Interviews
- [ ] Family Visits
- [ ] Home teaching coordination

---

## Documentation Tasks

### Recently Completed (February 8, 2026)
- [x] Updated README.md for Phase 2
- [x] Updated TESTING.md with appointment tests
- [x] Updated DEPLOYMENT.md with Google Calendar setup
- [x] Updated mls-master-plan.md with Phase 2 completion
- [x] Renamed PHASE1-COMPLETE.md to PHASES-1-AND-2-COMPLETE.md
- [x] Rewrote this todo.md

### Remaining Minor Updates
- [ ] Minor updates to GOOGLE_CALENDAR_SETUP.md (recent bug fixes)
- [ ] Add status indicator to COMPLETION_TRACKING_PLAN.md

---

## Bug Fixes & Technical Debt

### Known Issues
None currently - all known issues have been fixed

### Fixed Recently
- [x] Appointment sorting (9 PM appearing before 11 AM) - added time_24h field
- [x] Calendar sync for Bishop calendar - fixed conductor change logic
- [x] Event not updating when conductor changed - fixed event ID save condition
- [x] Deletion not syncing to calendar - added deletion sync
- [x] Smart deletion - preserve completed appointments in calendar
- [x] Calendar color contrast - darker colors for better visibility
- [x] UTC/timezone handling - proper storage and display

### Technical Debt
- None currently - codebase is clean and well-documented

---

## Maintenance

### Regular Tasks
- [ ] Weekly: Backup data files (user responsibility)
- [ ] Monthly: Import updated member data from church
- [ ] As needed: Update message templates
- [ ] As needed: Update appointment types

### Monitoring
- [ ] Watch for Google Calendar API rate limits
- [ ] Monitor OAuth token expiration and refresh
- [ ] Check CSV file integrity periodically
- [ ] Review Flask console logs for errors

---

## Notes

### Design Philosophy
- Keep it simple, local, and under user control
- No automation surprises
- Manual state management
- CSV over database for simplicity
- Mobile-first UI

### Current Limitations (By Design)
- Single user only
- No multi-device sync
- Manual backups required
- Local only (no remote access)
- Termux/Android specific

These are intentional design decisions for simplicity and security.

---

*Last Updated: February 8, 2026*
*Status: Phases 1 & 2 Complete, Phase 3 Planned*
