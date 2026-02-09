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

### Potential Features
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
