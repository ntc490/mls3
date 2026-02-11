"""
MLS3 - Member Leadership Scheduling System
Flask application entry point
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for
from datetime import datetime, date, timedelta

import config
from models import (
    MemberDatabase, PrayerAssignmentDatabase, MessageTemplates,
    AppointmentTypesDatabase, AppointmentDatabase, HouseholdDatabase
)
from utils.google_calendar import (
    get_calendar_service, CalendarSync, is_calendar_enabled, is_online
)


app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

# Initialize data models
members_db = MemberDatabase()
households_db = HouseholdDatabase()
assignments_db = PrayerAssignmentDatabase()
templates = MessageTemplates()
appointment_types_db = AppointmentTypesDatabase()
appointments_db = AppointmentDatabase()

# Print debug mode status on startup
print(f"\n{'='*60}")
print(f"MLS3 Starting Up")
print(f"{'='*60}")
print(f"DEBUG_SMS: {config.DEBUG_SMS} (print debug messages)")
print(f"DISABLE_SMS: {config.DISABLE_SMS} (skip actual SMS sending)")
print(f"GOOGLE_CALENDAR: {config.GOOGLE_CALENDAR_ENABLED} (sync to Google Calendar)")
print(f"Data directory: {config.DATA_DIR}")
print(f"{'='*60}\n")


def sync_appointment_to_calendar(appointment, old_conductor=None):
    """
    Sync appointment to Google Calendar if enabled.
    Handles errors gracefully and logs issues.

    Args:
        appointment: Appointment object to sync
        old_conductor: Previous conductor value if changed (for moving between calendars)

    Returns:
        True if sync successful or disabled, False if sync failed
    """
    if not is_calendar_enabled():
        return True  # Calendar disabled, no sync needed

    if not is_online():
        print("Warning: Offline, skipping calendar sync")
        return False

    try:
        service = get_calendar_service()
        sync = CalendarSync(service)
        member = members_db.get_by_id(appointment.member_id)

        if not member:
            print(f"Warning: Member {appointment.member_id} not found, skipping calendar sync")
            return False

        # Sync appointment (creates or updates, handles conductor changes)
        event_id = sync.sync_appointment(appointment, member, old_conductor)

        # Store event ID (could be new or updated)
        if event_id and event_id != appointment.google_event_id:
            appointment.google_event_id = event_id
            appointments_db.save()

        return True

    except Exception as e:
        print(f"Error syncing appointment to calendar: {e}")
        return False


def get_next_sunday(from_date: date = None) -> date:
    """Get the next Sunday from a given date (or today)"""
    if from_date is None:
        from_date = date.today()

    days_ahead = 6 - from_date.weekday()  # Sunday is 6
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def format_conductor_for_message(conductor: str) -> str:
    """Format conductor name for message templates"""
    if conductor == "Bishop":
        return "Bishop"
    elif conductor == "Counselor":
        return "a counselor"
    else:
        return conductor  # Fallback


@app.route('/')
def index():
    """Homepage with calendar view"""
    from collections import defaultdict

    # Get events for current week only
    today = date.today()

    # Determine the target Sunday based on what day it is
    if today.weekday() == 6:  # Sunday (0=Monday, 6=Sunday)
        # On Sunday, show this Sunday's events (today)
        target_sunday = today
    else:
        # Monday-Saturday, show next Sunday's events
        target_sunday = get_next_sunday(today)

    # Show events from Monday of the target week through the target Sunday
    # Calculate Monday of the target week
    # Sunday is weekday 6, so we need to go back 6 days to get to Monday
    days_since_monday = 6  # Always go back 6 days from Sunday to get to Monday
    week_start = target_sunday - timedelta(days=days_since_monday)

    # Show ALL events for the current week (including past days and completed)

    # Get prayer assignments for current week
    upcoming_assignments = [
        a for a in assignments_db.assignments
        if week_start <= a.date_obj <= target_sunday
    ]

    # Get appointments for current week (including completed)
    # Filter by local date, not UTC date
    upcoming_appointments = [
        a for a in appointments_db.appointments
        if week_start <= a.datetime_local(config.HOME_TIMEZONE).date() <= target_sunday
    ]

    # Group calendar items by date
    items_by_date = defaultdict(list)

    # Add prayer assignments
    for assignment in upcoming_assignments:
        member = members_db.get_by_id(assignment.member_id)
        member_name = member.display_name_with_last if member else "Unknown"
        member_phone = member.phone if member else ""

        items_by_date[assignment.date].append({
            'type': 'prayer',
            'assignment_id': assignment.assignment_id,
            'member_id': assignment.member_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'prayer_type': assignment.prayer_type,
            'state': assignment.state,
            'date_obj': assignment.date_obj
        })

    # Add appointments
    for appointment in upcoming_appointments:
        member = members_db.get_by_id(appointment.member_id)
        member_name = member.display_name_with_last if member else "Unknown"
        member_phone = member.phone if member else ""

        local_date = appointment.date_local(config.HOME_TIMEZONE)
        local_dt = appointment.datetime_local(config.HOME_TIMEZONE)
        items_by_date[local_date].append({
            'type': 'appointment',
            'appointment_id': appointment.appointment_id,
            'member_id': appointment.member_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'appointment_type': appointment.appointment_type,
            'time': appointment.time_local(config.HOME_TIMEZONE),
            'time_24h': local_dt.strftime('%H:%M'),  # For sorting
            'conductor': appointment.conductor,
            'state': appointment.state,
            'date_obj': local_dt.date()
        })

    # Convert to sorted list of (date, items) tuples
    # Sort items within each date by time in reverse (latest first, prayers go first)
    for date_str, items in items_by_date.items():
        items.sort(key=lambda x: x.get('time_24h', '00:00'), reverse=True)  # Prayers go first (have 00:00)

    calendar_items = sorted(items_by_date.items(), key=lambda x: datetime.strptime(x[0], config.DATE_FORMAT).date())

    return render_template(
        'index.html',
        member_count=len(members_db.get_active_members()),
        next_sunday=get_next_sunday(),
        calendar_items=calendar_items
    )


@app.route('/events')
def events():
    """Events page with date filtering"""
    from collections import defaultdict

    # Get date range from query params
    date_from_str = request.args.get('from')
    date_to_str = request.args.get('to')

    # Default to next 30 days if no params
    today = date.today()
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, config.DATE_FORMAT).date()
        except ValueError:
            date_from = today
    else:
        date_from = today

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, config.DATE_FORMAT).date()
        except ValueError:
            date_to = today + timedelta(days=30)
    else:
        date_to = today + timedelta(days=30)

    # Get prayer assignments in range
    filtered_assignments = [
        a for a in assignments_db.assignments
        if date_from <= a.date_obj <= date_to
    ]

    # Get appointments in range (including completed)
    # Filter by local date, not UTC date
    filtered_appointments = [
        a for a in appointments_db.appointments
        if date_from <= a.datetime_local(config.HOME_TIMEZONE).date() <= date_to
    ]

    # Group calendar items by date
    items_by_date = defaultdict(list)

    # Add prayer assignments
    for assignment in filtered_assignments:
        member = members_db.get_by_id(assignment.member_id)
        member_name = member.display_name_with_last if member else "Unknown"
        member_phone = member.phone if member else ""

        items_by_date[assignment.date].append({
            'type': 'prayer',
            'assignment_id': assignment.assignment_id,
            'member_id': assignment.member_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'prayer_type': assignment.prayer_type,
            'state': assignment.state,
            'date_obj': assignment.date_obj
        })

    # Add appointments
    for appointment in filtered_appointments:
        member = members_db.get_by_id(appointment.member_id)
        member_name = member.display_name_with_last if member else "Unknown"
        member_phone = member.phone if member else ""

        local_date = appointment.date_local(config.HOME_TIMEZONE)
        local_dt = appointment.datetime_local(config.HOME_TIMEZONE)
        items_by_date[local_date].append({
            'type': 'appointment',
            'appointment_id': appointment.appointment_id,
            'member_id': appointment.member_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'appointment_type': appointment.appointment_type,
            'time': appointment.time_local(config.HOME_TIMEZONE),
            'time_24h': local_dt.strftime('%H:%M'),  # For sorting
            'conductor': appointment.conductor,
            'state': appointment.state,
            'date_obj': local_dt.date()
        })

    # Sort items within each date in reverse (latest first, prayers go first)
    for date_str, items in items_by_date.items():
        items.sort(key=lambda x: x.get('time_24h', '00:00'), reverse=True)  # Prayers go first (have 00:00)

    # Convert to sorted list in reverse chronological order (newest first)
    calendar_items = sorted(items_by_date.items(), key=lambda x: datetime.strptime(x[0], config.DATE_FORMAT).date(), reverse=True)

    return render_template('events.html', calendar_items=calendar_items)


@app.route('/members')
def members_list():
    """List all members"""
    # Helper function to calculate age
    def calc_age(birthday_str):
        if not birthday_str:
            return None
        try:
            birth_date = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            today = date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            return None

    # Create member dicts with age
    all_members = []
    for m in members_db.members:
        member_dict = {
            'member_id': m.member_id,
            'full_name': m.full_name,
            'first_name': m.first_name,
            'last_name': m.last_name,
            'display_name': m.display_name,
            'gender': m.gender,
            'phone': m.phone,
            'birthday': m.birthday,
            'age': calc_age(m.birthday),
            'last_prayer_date': members_db.get_last_prayer_date(m.member_id, assignments_db),
            'dont_ask_prayer': m.dont_ask_prayer,
            'active': m.active,
            'notes': m.notes,
            'flag': m.flag
        }
        all_members.append(member_dict)

    active_members = [m for m in all_members if m['active']]
    inactive_members = [m for m in all_members if not m['active']]

    active_men = [m for m in active_members if m['gender'] == 'M']
    active_women = [m for m in active_members if m['gender'] == 'F']

    return render_template(
        'members_list.html',
        members=all_members,  # Pass all members now
        active_count=len(active_members),
        inactive_count=len(inactive_members),
        men_count=len(active_men),
        women_count=len(active_women)
    )


@app.route('/prayer-scheduler')
def prayer_scheduler():
    """Main prayer scheduling interface"""
    # Allow viewing different dates via query param
    date_param = request.args.get('date')
    if date_param:
        try:
            target_sunday = datetime.strptime(date_param, config.DATE_FORMAT).date()
        except ValueError:
            target_sunday = get_next_sunday()
    else:
        target_sunday = get_next_sunday()

    # Get existing assignments for target Sunday
    sunday_assignments = assignments_db.get_assignments_for_date(target_sunday)

    # Find slot assignments (two unnamed slots)
    # Sort by assignment_id only - keep in creation order
    sorted_assignments = sorted(sunday_assignments, key=lambda a: a.assignment_id)

    slot1 = sorted_assignments[0] if len(sorted_assignments) > 0 else None
    slot2 = sorted_assignments[1] if len(sorted_assignments) > 1 else None

    # Calculate prev/next Sunday for navigation
    prev_sunday = target_sunday - timedelta(days=7)
    next_sunday_nav = target_sunday + timedelta(days=7)

    return render_template(
        'prayer_scheduler.html',
        target_sunday=target_sunday,
        next_sunday=get_next_sunday(),  # For "Create Assignment" default
        slot1=slot1,
        slot2=slot2,
        members_db=members_db,
        prev_sunday=prev_sunday,
        next_sunday_nav=next_sunday_nav
    )


@app.route('/api/members/search')
def api_members_search():
    """API endpoint for member search"""
    query = request.args.get('q', '')
    gender = request.args.get('gender', None)

    if query:
        from utils.candidate_selector import find_member_by_fuzzy_search
        members = find_member_by_fuzzy_search(members_db, query, gender=gender)
    else:
        members = members_db.get_active_members(gender=gender)

    # Helper function to calculate age
    def calc_age(birthday_str):
        if not birthday_str:
            return None
        try:
            birth_date = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            today = date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            return None

    # Convert to JSON-friendly format
    results = [
        {
            'id': m.member_id,
            'name': m.full_name,
            'gender': m.gender,
            'last_prayer_date': members_db.get_last_prayer_date(m.member_id, assignments_db),
            'phone': m.phone,
            'age': calc_age(m.birthday)
        }
        for m in members
    ]

    return jsonify(results)


@app.route('/api/candidates/<gender>')
def api_candidates(gender):
    """API endpoint to get next-up candidates"""
    from utils.candidate_selector import get_candidates_with_context

    count = int(request.args.get('count', config.NEXT_CANDIDATE_COUNT))
    candidates = get_candidates_with_context(members_db, assignments_db, gender, count)

    # Helper function to calculate age
    def calc_age(birthday_str):
        if not birthday_str:
            return None
        try:
            birth_date = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            today = date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            return None

    results = [
        {
            'id': c['member'].member_id,
            'name': c['member'].full_name,
            'last_prayer_date': c['last_prayer_date_display'],
            'priority': c['priority'],
            'age': calc_age(c['member'].birthday)
        }
        for c in candidates
    ]

    return jsonify(results)


@app.route('/api/assignments/create', methods=['POST'])
def api_create_assignment():
    """Create a new prayer assignment"""
    data = request.json

    member_id = data.get('member_id')  # Can be null initially
    date_str = data.get('date')
    prayer_type = data.get('prayer_type', 'Undecided')

    if not date_str:
        return jsonify({'error': 'Missing required field: date'}), 400

    # Parse date
    target_date = datetime.strptime(date_str, config.DATE_FORMAT).date()

    # Create assignment (member_id can be None/null)
    assignment = assignments_db.create_assignment(member_id, target_date, prayer_type)

    return jsonify({
        'success': True,
        'assignment_id': assignment.assignment_id
    })


@app.route('/api/assignments/<int:assignment_id>/update', methods=['POST'])
def api_update_assignment(assignment_id):
    """Update an existing assignment"""
    data = request.json

    member_id = data.get('member_id')
    prayer_type = data.get('prayer_type')
    date_str = data.get('date')

    target_date = None
    if date_str:
        target_date = datetime.strptime(date_str, config.DATE_FORMAT).date()

    # Handle updates with prayer type syncing
    if prayer_type:
        # User is manually toggling prayer type
        assignment = assignments_db.get_by_id(assignment_id)
        if assignment:
            # Update this assignment
            assignments_db.update_assignment(assignment_id, prayer_type=prayer_type)

            # If setting to Opening or Closing, set the other slot to the opposite
            if prayer_type in ['Opening', 'Closing']:
                same_date_assignments = assignments_db.get_assignments_for_date(
                    datetime.strptime(assignment.date, config.DATE_FORMAT).date()
                )
                opposite_type = 'Closing' if prayer_type == 'Opening' else 'Opening'

                for other in same_date_assignments:
                    if other.assignment_id != assignment_id and other.state != 'Completed':
                        # Always set other slot to the opposite type
                        assignments_db.update_assignment(other.assignment_id, prayer_type=opposite_type)
                        break
            # If setting to Undecided, leave the other slot alone
    elif member_id is not None:
        # Assigning a member - keep prayer type as-is
        assignments_db.update_assignment(assignment_id, member_id=member_id)
    elif target_date:
        # Date update
        assignments_db.update_assignment(assignment_id, date=target_date)

    return jsonify({'success': True})


@app.route('/api/assignments/<int:assignment_id>/state', methods=['POST'])
def api_update_assignment_state(assignment_id):
    """Update assignment state"""
    data = request.json
    new_state = data.get('state')

    if not new_state:
        return jsonify({'error': 'Missing state'}), 400

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    assignments_db.update_state(assignment_id, new_state)

    # If marking as Completed, update member's last_prayer_date
    if new_state == 'Completed' and assignment.member_id:
        members_db.update_member(assignment.member_id, last_prayer_date=assignment.date)

    return jsonify({'success': True})


@app.route('/api/assignments/<int:assignment_id>/decline', methods=['POST'])
def api_decline_assignment(assignment_id):
    """Handle member declining - clear them and skip for a few weeks"""
    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    # Get the member before clearing
    member_id = assignment.member_id
    skip_until_str = None

    if member_id and member_id > 0:
        # Set skip_until to 2 weeks from now
        from datetime import timedelta
        skip_until_date = date.today() + timedelta(weeks=2)
        skip_until_str = skip_until_date.strftime(config.DATE_FORMAT)

        # Update member's skip_until
        members_db.update_member(member_id, skip_until=skip_until_str)

    # Clear the member from assignment and reset to Draft
    assignments_db.update_assignment(assignment_id, member_id=0)
    assignments_db.update_state(assignment_id, 'Draft')

    return jsonify({
        'success': True,
        'skip_until': skip_until_str
    })


@app.route('/api/assignments/<int:assignment_id>/delete', methods=['POST'])
def api_delete_assignment(assignment_id):
    """Delete an assignment"""
    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    # Remove from list and save
    assignments_db.assignments = [a for a in assignments_db.assignments if a.assignment_id != assignment_id]
    assignments_db.save()

    return jsonify({'success': True})


@app.route('/api/assignments/<int:assignment_id>/invite', methods=['POST'])
def api_send_invitation(assignment_id):
    """Send invitation SMS and update state to Invited"""
    from utils.sms_handler import expand_and_send

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Update state to Invited (do this first, before attempting to send SMS)
    assignments_db.update_state(assignment_id, 'Invited')

    # Send SMS using smart template expansion
    success, error_msg = expand_and_send('prayer', 'invite', member, templates, members_db, assignment)

    if success:
        return jsonify({'success': True, 'message': 'SMS sent'})
    else:
        return jsonify({
            'success': False,
            'error': error_msg or 'Failed to launch SMS app',
            'phone': member.phone,
            'member': member.full_name
        }), 500


@app.route('/api/assignments/<int:assignment_id>/remind', methods=['POST'])
def api_send_reminder(assignment_id):
    """Send reminder SMS and update state to Reminded"""
    from utils.sms_handler import expand_and_send

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Send SMS using smart template expansion
    success, error_msg = expand_and_send('prayer', 'reminder', member, templates, members_db, assignment)

    if success:
        # Update state to Reminded
        assignments_db.update_state(assignment_id, 'Reminded')
        return jsonify({'success': True, 'message': 'SMS sent'})
    else:
        return jsonify({
            'success': False,
            'error': error_msg or 'Failed to launch SMS app',
            'phone': member.phone,
            'member': member.full_name
        }), 500


@app.route('/api/members/<int:member_id>')
def api_get_member(member_id):
    """Get member details with prayer history"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Calculate age from birthday
    age = None
    if member.birthday:
        try:
            birth_date = datetime.strptime(member.birthday, '%Y-%m-%d').date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            pass

    # Get prayer history for this member
    member_assignments = [
        a for a in assignments_db.assignments
        if a.member_id == member_id and a.state == 'Completed'
    ]

    # Sort by date descending (most recent first)
    member_assignments.sort(key=lambda a: a.date, reverse=True)

    # Format prayer history
    prayer_history = [
        {
            'date': a.date,
            'prayer_type': a.prayer_type,
            'formatted_date': datetime.strptime(a.date, config.DATE_FORMAT).strftime(config.DISPLAY_DATE_FORMAT)
        }
        for a in member_assignments
    ]

    # Get event history (prayers and appointments combined)
    event_history = []

    # Add all prayer assignments (not just completed)
    all_member_assignments = [
        a for a in assignments_db.assignments
        if a.member_id == member_id
    ]
    for assignment in all_member_assignments:
        event_history.append({
            'type': 'prayer',
            'assignment_id': assignment.assignment_id,
            'date': assignment.date,
            'date_obj': assignment.date_obj,
            'prayer_type': assignment.prayer_type,
            'state': assignment.state,
            'formatted_date': datetime.strptime(assignment.date, config.DATE_FORMAT).strftime(config.DISPLAY_DATE_FORMAT)
        })

    # Add all appointments for this member (including completed)
    member_appointments = [
        a for a in appointments_db.appointments
        if a.member_id == member_id
    ]
    for appointment in member_appointments:
        local_date = appointment.date_local(config.HOME_TIMEZONE)
        local_dt = appointment.datetime_local(config.HOME_TIMEZONE)
        event_history.append({
            'type': 'appointment',
            'appointment_id': appointment.appointment_id,
            'date': local_date,
            'date_obj': local_dt.date(),
            'time': appointment.time_local(config.HOME_TIMEZONE),  # Localized time for display
            'appointment_type': appointment.appointment_type,
            'conductor': appointment.conductor,
            'state': appointment.state,
            'formatted_date': local_dt.strftime(config.DISPLAY_DATE_FORMAT)
        })

    # Sort event history by date descending (most recent first)
    event_history.sort(key=lambda e: e['date_obj'], reverse=True)

    return jsonify({
        'id': member.member_id,
        'name': member.full_name,
        'first_name': member.first_name,
        'last_name': member.last_name,
        'gender': member.gender,
        'birthday': member.birthday,
        'age': age,
        'is_minor': member.is_minor,
        'phone': member.phone,
        'recommend_expiration': member.recommend_expiration,
        'active': member.active,
        'dont_ask_prayer': member.dont_ask_prayer,
        'last_prayer_date': members_db.get_last_prayer_date(member_id, assignments_db),
        'notes': member.notes,
        'skip_until': member.skip_until,
        'flag': member.flag,
        'aka': member.aka,
        'household_id': member.household_id,
        'prayer_history': prayer_history,
        'event_history': event_history
    })


@app.route('/api/members/<int:member_id>/toggle-active', methods=['POST'])
def api_toggle_member_active(member_id):
    """Toggle member active status"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Toggle the active status
    member.active = not member.active
    members_db.save()

    return jsonify({
        'success': True,
        'active': member.active
    })


@app.route('/api/members/<int:member_id>/toggle-dont-ask', methods=['POST'])
def api_toggle_dont_ask(member_id):
    """Toggle member dont_ask_prayer flag"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Toggle the dont_ask_prayer flag
    member.dont_ask_prayer = not member.dont_ask_prayer
    members_db.save()

    return jsonify({
        'success': True,
        'dont_ask_prayer': member.dont_ask_prayer
    })


@app.route('/api/members/<int:member_id>/skip-until', methods=['POST'])
def api_set_skip_until(member_id):
    """Set skip_until date for a member"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    data = request.json
    skip_until = data.get('skip_until')  # Can be date string or null

    member.skip_until = skip_until
    members_db.save()

    return jsonify({
        'success': True,
        'skip_until': member.skip_until
    })


@app.route('/api/members/<int:member_id>/aka', methods=['POST'])
def api_set_aka(member_id):
    """Set AKA (also known as / preferred name) for a member"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    data = request.json
    aka = data.get('aka', '').strip()  # Get AKA, default to empty string

    member.aka = aka
    members_db.save()

    return jsonify({
        'success': True,
        'aka': member.aka
    })


@app.route('/api/members/<int:member_id>/toggle-flag', methods=['POST'])
def api_toggle_member_flag(member_id):
    """Toggle a color flag for a member (can have multiple flags)"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    data = request.json
    flag = data.get('flag', '')  # 'red', 'yellow', or 'blue'

    # Validate flag value
    if flag not in ['red', 'yellow', 'blue']:
        return jsonify({'error': 'Invalid flag color'}), 400

    # Toggle the flag
    member.toggle_flag(flag)
    members_db.save()

    return jsonify({
        'success': True,
        'flag': member.flag,
        'flags_list': member.flags_list
    })


@app.route('/api/members/<int:member_id>/create-assignment', methods=['POST'])
def api_create_member_assignment(member_id):
    """Create a prayer assignment for a specific member"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Get target date (default to next Sunday)
    data = request.json or {}
    date_str = data.get('date')

    if date_str:
        target_date = datetime.strptime(date_str, config.DATE_FORMAT).date()
    else:
        target_date = get_next_sunday()

    # Don't allow creating prayers for past dates
    current_sunday = get_next_sunday()
    if target_date < current_sunday:
        return jsonify({
            'error': 'Cannot create prayer assignments for past weeks. Please use current or future dates.'
        }), 400

    # Check existing assignments for this date
    existing_assignments = assignments_db.get_assignments_for_date(target_date)

    # Filter to non-completed assignments
    active_assignments = [a for a in existing_assignments if a.state != 'Completed']

    # Check if this member already has an assignment for this date
    member_has_assignment = any(a.member_id == member_id for a in active_assignments)
    if member_has_assignment:
        # Member already assigned - just redirect to scheduler (success, no new assignment created)
        return jsonify({
            'success': True,
            'redirect': True,
            'message': 'Member already has an assignment for this date'
        })

    # Check how many slots exist and their types
    num_slots = len(active_assignments)

    # Find any empty slot (member_id=0 or None)
    empty_slot = None
    for a in active_assignments:
        if not a.member_id or a.member_id == 0:
            empty_slot = a
            break

    # Check if both slots are filled with members
    filled_slots = [a for a in active_assignments if a.member_id and a.member_id > 0]
    if len(filled_slots) >= 2:
        # Both slots full with different members
        return jsonify({
            'error': 'All prayer slots are full for this week. Please choose a different week or clear an existing slot.'
        }), 400

    # Determine what to do
    if empty_slot:
        # Fill the existing empty slot - keep its prayer type
        assignments_db.update_assignment(empty_slot.assignment_id, member_id=member_id)
        assignment = assignments_db.get_by_id(empty_slot.assignment_id)
    elif num_slots == 0:
        # No slots exist - create first one as Undecided
        assignment = assignments_db.create_assignment(member_id, target_date, 'Undecided')
    elif num_slots == 1:
        # One slot exists - check its prayer type
        existing = active_assignments[0]

        if existing.prayer_type == 'Undecided':
            # Existing slot is Undecided - create new one as Undecided
            new_prayer_type = 'Undecided'
        elif existing.prayer_type == 'Opening':
            # Existing slot is Opening - create new one as Closing
            new_prayer_type = 'Closing'
        else:  # Closing
            # Existing slot is Closing - create new one as Opening
            new_prayer_type = 'Opening'

        assignment = assignments_db.create_assignment(member_id, target_date, new_prayer_type)
    else:
        # Two slots exist but one is empty (already handled above)
        return jsonify({
            'error': 'Unable to create assignment - slots unavailable'
        }), 400

    return jsonify({
        'success': True,
        'assignment_id': assignment.assignment_id,
        'date': assignment.date,
        'prayer_type': assignment.prayer_type
    })


@app.route('/api/households/<int:household_id>')
def api_get_household(household_id):
    """Get household details with all members"""
    household = households_db.get_by_id(household_id)
    if not household:
        return jsonify({'error': 'Household not found'}), 404

    # Get all members in this household
    household_members = members_db.get_household_members(household_id)

    # Format member data
    members_data = []
    for member in household_members:
        # Calculate age
        age = None
        if member.birthday:
            try:
                birth_date = datetime.strptime(member.birthday, '%Y-%m-%d').date()
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            except ValueError:
                pass

        members_data.append({
            'member_id': member.member_id,
            'full_name': member.full_name,
            'display_name': member.display_name,
            'gender': member.gender,
            'phone': member.phone,
            'birthday': member.birthday,
            'age': age,
            'is_minor': member.is_minor
        })

    # Sort members: adults first (by age desc), then minors (by age desc)
    members_data.sort(key=lambda m: (m['is_minor'], -(m['age'] or 0)))

    return jsonify({
        'household_id': household.household_id,
        'name': household.name,
        'address': household.address,
        'phone': household.phone,
        'email': household.email,
        'members': members_data
    })


@app.route('/api/members/<int:member_id>/household')
def api_get_member_household(member_id):
    """Get household information for a specific member"""
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    if not member.household_id:
        return jsonify({'household': None})

    # Get household details
    household = households_db.get_by_id(member.household_id)
    if not household:
        return jsonify({'household': None})

    # Get parents if member is minor
    parents = []
    if member.is_minor:
        parent_members = members_db.get_parents(member_id)
        parents = [
            {
                'member_id': p.member_id,
                'full_name': p.full_name,
                'phone': p.phone
            }
            for p in parent_members
        ]

    # Get children if member is adult
    children = []
    if not member.is_minor:
        child_members = members_db.get_children(member_id)
        children = [
            {
                'member_id': c.member_id,
                'full_name': c.full_name,
                'age': c.age
            }
            for c in child_members
        ]

    return jsonify({
        'household': {
            'household_id': household.household_id,
            'name': household.name,
            'address': household.address,
            'phone': household.phone,
            'email': household.email
        },
        'parents': parents,
        'children': children
    })


@app.route('/appointment-scheduler')
def appointment_scheduler():
    """Appointment scheduler page"""
    # Can be accessed with member_id, appointment_id, or standalone
    return render_template(
        'appointment_scheduler.html',
        calendar_enabled=is_calendar_enabled()
    )


@app.route('/api/appointment-types')
def get_appointment_types():
    """Get all appointment types"""
    types_list = [
        {
            'name': t.name,
            'default_duration': t.default_duration,
            'default_conductor': t.default_conductor
        }
        for t in appointment_types_db.get_all()
    ]
    return jsonify({'appointment_types': types_list})


@app.route('/api/appointments')
def get_appointments():
    """Get all appointments, optionally filtered by date"""
    date_filter = request.args.get('date')

    if date_filter:
        # Filter by specific date (using local date)
        appointments_list = [
            appt for appt in appointments_db.appointments
            if appt.date_local(config.HOME_TIMEZONE) == date_filter and appt.state not in ['Completed', 'Cancelled']
        ]
    else:
        # Get all appointments
        appointments_list = appointments_db.appointments

    result = []
    for appt in appointments_list:
        member = members_db.get_by_id(appt.member_id)
        local_dt = appt.datetime_local(config.HOME_TIMEZONE)
        result.append({
            'appointment_id': appt.appointment_id,
            'member_id': appt.member_id,
            'member_name': member.full_name if member else "Unknown",
            'appointment_type': appt.appointment_type,
            'date': appt.date_local(config.HOME_TIMEZONE),  # Use local date
            'time': appt.time_local(config.HOME_TIMEZONE),  # Localized time for display (12-hour format)
            'time_24h': local_dt.strftime('%H:%M'),  # 24-hour format for sorting
            'duration_minutes': appt.duration_minutes,
            'conductor': appt.conductor,
            'state': appt.state,
            'created_date': appt.created_date,
            'last_updated': appt.last_updated,
            'completed_date': appt.completed_date
        })
    return jsonify({'appointments': result})


@app.route('/api/appointments/suggest-time')
def suggest_appointment_time():
    """Suggest next available appointment time for a given date and conductor"""
    date_str = request.args.get('date')
    conductor = request.args.get('conductor')
    duration = int(request.args.get('duration', 15))

    if not date_str or not conductor:
        return jsonify({'error': 'Missing date or conductor parameter'}), 400

    # Get all appointments for this date and conductor (using local date)
    existing_appointments = [
        appt for appt in appointments_db.appointments
        if appt.date_local(config.HOME_TIMEZONE) == date_str
        and appt.conductor == conductor
        and appt.state not in ['Completed', 'Cancelled']
    ]

    # Define scheduling window (11:00 AM - 12:00 PM)
    start_hour = 11
    start_minute = 0
    end_hour = 12
    end_minute = 0

    # Convert to minutes from midnight for easier math
    window_start = start_hour * 60 + start_minute  # 660 minutes (11:00 AM)
    window_end = end_hour * 60 + end_minute  # 720 minutes (12:00 PM)

    # Create list of occupied time slots
    occupied_slots = []
    for appt in existing_appointments:
        time_parts = appt.time.split(':')
        appt_start = int(time_parts[0]) * 60 + int(time_parts[1])
        appt_end = appt_start + appt.duration_minutes
        occupied_slots.append((appt_start, appt_end))

    # Sort occupied slots by start time
    occupied_slots.sort()

    # Find first available slot
    current_time = window_start
    suggested_time = None

    while current_time + duration <= window_end:
        # Check if this slot conflicts with any existing appointment
        proposed_end = current_time + duration
        conflicts = False

        for occupied_start, occupied_end in occupied_slots:
            # Check for overlap
            if not (proposed_end <= occupied_start or current_time >= occupied_end):
                conflicts = True
                # Jump to end of this occupied slot
                current_time = occupied_end
                break

        if not conflicts:
            # Found an available slot
            hours = current_time // 60
            minutes = current_time % 60
            suggested_time = f"{hours:02d}:{minutes:02d}"
            break

        if conflicts:
            continue

        # Move to next 5-minute increment
        current_time += 5

    if suggested_time:
        return jsonify({
            'suggested_time': suggested_time,
            'available': True
        })
    else:
        return jsonify({
            'suggested_time': None,
            'available': False,
            'message': 'No available slots in the 11:00 AM - 12:00 PM window'
        })


@app.route('/api/appointments/create', methods=['POST'])
def create_appointment():
    """Create a new appointment"""
    data = request.json
    member_id = data.get('member_id')
    appointment_type = data.get('appointment_type')
    date_str = data.get('date')
    time_str = data.get('time')
    duration_minutes = data.get('duration_minutes')
    conductor = data.get('conductor')
    timezone = data.get('timezone')  # Browser's detected timezone
    notes = data.get('notes')  # Optional notes

    if not all([member_id, appointment_type, date_str, time_str, duration_minutes, conductor]):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        appt_date = datetime.strptime(date_str, config.DATE_FORMAT).date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    appointment = appointments_db.create_appointment(
        member_id=member_id,
        appointment_type=appointment_type,
        date=appt_date,
        time=time_str,
        duration_minutes=int(duration_minutes),
        conductor=conductor,
        timezone=timezone,
        notes=notes
    )

    # Sync to Google Calendar
    sync_appointment_to_calendar(appointment)

    return jsonify({
        'success': True,
        'appointment_id': appointment.appointment_id
    })


@app.route('/api/appointments/<int:appointment_id>', methods=['POST'])
def update_appointment(appointment_id):
    """Update an existing appointment"""
    data = request.json
    appointment_type = data.get('appointment_type')
    date_str = data.get('date')
    time_str = data.get('time')
    duration_minutes = data.get('duration_minutes')
    conductor = data.get('conductor')
    timezone = data.get('timezone')  # Browser's detected timezone
    notes = data.get('notes')  # Optional notes

    # Get old appointment to check if conductor changed
    old_appointment = appointments_db.get_by_id(appointment_id)
    old_conductor = old_appointment.conductor if old_appointment else None

    appt_date = None
    if date_str:
        try:
            appt_date = datetime.strptime(date_str, config.DATE_FORMAT).date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    appointments_db.update_appointment(
        appointment_id=appointment_id,
        appointment_type=appointment_type,
        date=appt_date,
        time=time_str,
        duration_minutes=int(duration_minutes) if duration_minutes is not None else None,
        conductor=conductor,
        timezone=timezone,
        notes=notes
    )

    # Sync updated appointment to Google Calendar
    appointment = appointments_db.get_by_id(appointment_id)
    if appointment:
        sync_appointment_to_calendar(appointment, old_conductor)

    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>/invite', methods=['POST'])
def send_appointment_invite(appointment_id):
    """Send appointment invitation to member"""
    from utils.sms_handler import expand_and_send

    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Update state to Invited (do this first, before attempting to send SMS)
    appointments_db.update_state(appointment_id, 'Invited')

    # Determine template name (try specific type, fallback to default)
    template_name = f'{appointment.appointment_type}_invite'
    if not templates.get_template('appointments', template_name):
        template_name = 'default_invite'

    # Send SMS using smart template expansion
    success, error_msg = expand_and_send(
        'appointments',
        template_name,
        member,
        templates,
        members_db,
        appointment,
        conductor=format_conductor_for_message(appointment.conductor)
    )

    if success:
        return jsonify({'success': True, 'message': 'SMS sent'})
    else:
        return jsonify({
            'success': False,
            'error': error_msg or 'Failed to send SMS',
            'phone': member.phone,
            'member': member.full_name
        }), 500


@app.route('/api/appointments/<int:appointment_id>/reminder-message', methods=['GET'])
def get_appointment_reminder_message(appointment_id):
    """Get reminder message for an appointment"""
    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Get message template
    template = templates.get_template('appointments', f'{appointment.appointment_type}_reminder')
    if not template:
        template = templates.get_template('appointments', 'default_reminder')

    # Format the message with localized time
    appt_datetime_local = appointment.datetime_local(config.HOME_TIMEZONE)
    message = template.format(
        member_name=member.display_name,
        appointment_type=appointment.appointment_type,
        date=appt_datetime_local.strftime(config.DISPLAY_DATE_FORMAT),
        time=appt_datetime_local.strftime('%I:%M %p'),
        conductor=format_conductor_for_message(appointment.conductor)
    )

    return jsonify({'message': message})


@app.route('/api/appointments/<int:appointment_id>/remind', methods=['POST'])
def send_appointment_reminder(appointment_id):
    """Send appointment reminder to member"""
    from utils.sms_handler import expand_and_send

    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Determine template name (try specific type, fallback to default)
    template_name = f'{appointment.appointment_type}_reminder'
    if not templates.get_template('appointments', template_name):
        template_name = 'default_reminder'

    # Send SMS using smart template expansion
    success, error_msg = expand_and_send(
        'appointments',
        template_name,
        member,
        templates,
        members_db,
        appointment,
        conductor=format_conductor_for_message(appointment.conductor)
    )

    if success:
        # Update state to Reminded only if not already reminded
        # This allows sending multiple reminders
        if appointment.state != 'Reminded':
            appointments_db.update_state(appointment_id, 'Reminded')
        return jsonify({'success': True, 'message': 'SMS sent'})
    else:
        return jsonify({
            'success': False,
            'error': error_msg or 'Failed to send SMS',
            'phone': member.phone,
            'member': member.full_name
        }), 500


@app.route('/api/appointments/<int:appointment_id>/state', methods=['POST'])
def update_appointment_state(appointment_id):
    """Update appointment state"""
    data = request.json
    new_state = data.get('state')

    if not new_state:
        return jsonify({'error': 'State is required'}), 400

    valid_states = ['Draft', 'Invited', 'Accepted', 'Reminded', 'Completed', 'Cancelled']
    if new_state not in valid_states:
        return jsonify({'error': f'Invalid state. Must be one of: {", ".join(valid_states)}'}), 400

    appointments_db.update_state(appointment_id, new_state)

    # Sync state change to Google Calendar (updates description with new state)
    appointment = appointments_db.get_by_id(appointment_id)
    if appointment:
        sync_appointment_to_calendar(appointment)

    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>/delete', methods=['POST'])
def delete_appointment(appointment_id):
    """Delete an appointment"""
    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    # Delete from Google Calendar if it exists
    if (appointment.google_event_id and
        is_calendar_enabled() and
        is_online()):
        try:
            service = get_calendar_service()
            sync = CalendarSync(service)
            sync.delete_appointment_event(appointment)
            print(f"Deleted appointment from Google Calendar")
        except Exception as e:
            print(f"Warning: Could not delete from Google Calendar: {e}")
            # Continue with MLS3 deletion even if calendar deletion fails

    # Remove from list and save
    appointments_db.appointments = [a for a in appointments_db.appointments if a.appointment_id != appointment_id]
    appointments_db.save()

    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>/sync-calendar', methods=['POST'])
def sync_appointment_calendar(appointment_id):
    """Manually sync appointment to Google Calendar"""
    if not is_calendar_enabled():
        return jsonify({'error': 'Google Calendar integration not enabled'}), 400

    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    success = sync_appointment_to_calendar(appointment)

    if success:
        return jsonify({'success': True, 'message': 'Synced to Google Calendar'})
    else:
        return jsonify({'error': 'Failed to sync to calendar. Check connection.'}), 500


@app.route('/api/appointments/<int:appointment_id>', methods=['GET'])
def get_appointment(appointment_id):
    """Get a single appointment by ID"""
    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)

    # Get localized date and time for editing (convert from UTC to local timezone)
    local_dt = appointment.datetime_local(config.HOME_TIMEZONE)
    local_date = local_dt.strftime(config.DATE_FORMAT)  # Get LOCAL date, not UTC date
    local_time_24h = local_dt.strftime('%H:%M')

    return jsonify({
        'appointment_id': appointment.appointment_id,
        'member_id': appointment.member_id,
        'member_name': member.full_name if member else "Unknown",
        'appointment_type': appointment.appointment_type,
        'date': local_date,  # Use local date instead of UTC date
        'time': local_time_24h,  # Send localized time in 24-hour format for time input
        'duration_minutes': appointment.duration_minutes,
        'conductor': appointment.conductor,
        'state': appointment.state,
        'created_date': appointment.created_date,
        'last_updated': appointment.last_updated,
        'completed_date': appointment.completed_date,
        'notes': appointment.notes
    })


@app.route('/sms-composer')
def sms_composer():
    """
    SMS message composer page.

    Query params:
        member_id (int, required): Member to send message to

    Returns:
        Rendered template with member data and available templates
    """
    member_id = request.args.get('member_id', type=int)

    if not member_id:
        # No member specified, redirect to home
        return redirect('/')

    member = members_db.get_by_id(member_id)
    if not member:
        # Member not found, redirect to home
        return redirect('/')

    # Get adhoc template categories from YAML
    # Show all base templates (without _parent suffix) regardless of member type
    adhoc_templates = templates.templates.get('adhoc', {})

    # Filter to show only base templates (not _parent variants)
    filtered_templates = {
        name: text for name, text in adhoc_templates.items()
        if not name.endswith('_parent')
    }

    return render_template('sms_composer.html',
                          member=member,
                          adhoc_templates=filtered_templates)


@app.route('/api/expand-template', methods=['POST'])
def api_expand_template():
    """
    Expand template with member context and custom variables.
    Handles parent routing for minors.

    Request JSON:
        {
            "member_id": 123,
            "template": "Hi {name|blue?formal:casual}, {random:casual_greeting} ...",
            "template_name": "birthday" (optional - for auto-detecting _parent variant),
            "variables": {
                "event_name": "Ward Picnic",
                "calling_name": "Primary Teacher"
            }
        }

    Returns:
        {
            "expanded": "Hi John, I hope you're well. ...",
            "length": 145,
            "template_used": "birthday" or "birthday_parent",
            "recipient": "John Smith" or "Brother and Sister Wilson"
        }
    """
    from utils.template_expander import SmartTemplateExpander

    data = request.json
    member_id = data.get('member_id')
    template_str = data.get('template', '')
    template_name = data.get('template_name')  # Optional: for parent template lookup
    custom_vars = data.get('variables', {})

    if not member_id:
        return jsonify({'error': 'Missing member_id'}), 400

    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Check if member is a minor - try parent template first, fall back to base
    recipient_name = member.display_name
    actual_template_name = template_name

    if member.is_minor and template_name:
        # Try to find parent variant first
        parent_template_name = f"{template_name}_parent"
        parent_template = templates.get_template('adhoc', parent_template_name)

        if parent_template:
            # Parent template exists - use it
            template_str = parent_template
            actual_template_name = parent_template_name

            # Get parents to build greeting
            parents = members_db.get_parents(member_id)

            if parents:
                # Build parent greeting (same logic as sms_handler.py)
                any_formal = any(p.has_flag('blue') for p in parents)

                if len(parents) == 1:
                    parent = parents[0]
                    if parent.has_flag('blue'):
                        title = 'Brother' if parent.gender == 'M' else 'Sister'
                        parent_greeting = f"{title} {parent.last_name}"
                    else:
                        parent_greeting = parent.display_name
                elif any_formal:
                    parent_greeting = f"Brother and Sister {parents[0].last_name}"
                else:
                    parent_names_casual = [p.display_name for p in parents]
                    parent_greeting = ' & '.join(parent_names_casual)

                # Add parent-specific variables (auto-populated)
                custom_vars['child_name'] = member.display_name
                custom_vars['parent_greeting'] = parent_greeting
                recipient_name = parent_greeting
        # else: No parent template found - fall back to base template (template_str unchanged)

    # Expand template with smart variables
    expander = SmartTemplateExpander(templates)
    expanded = expander.expand(template_str, member, appointment=None, **custom_vars)

    return jsonify({
        'expanded': expanded,
        'length': len(expanded),
        'template_used': actual_template_name,
        'recipient': recipient_name
    })


@app.route('/api/queue-sms', methods=['POST'])
def api_queue_sms():
    """
    Queue SMS for sending via Tasker.
    Used by composer for ad-hoc messages.

    Request JSON:
        {
            "phone": "+1234567890",
            "message": "Hi John, ..."
        }

    Returns:
        {"success": true}
    """
    from utils.sms_handler import send_sms_intent

    data = request.json
    phone = data.get('phone')
    message = data.get('message')

    if not phone or not message:
        return jsonify({'error': 'Missing phone or message'}), 400

    # Send via Tasker
    success = send_sms_intent(phone, message)

    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to queue SMS'}), 500


@app.route('/api/members/<int:member_id>/sms-direct', methods=['POST'])
def send_direct_sms(member_id):
    """
    Open direct SMS to member (or parents if minor).
    Returns the phone number(s) to use for the SMS intent.

    Returns:
        {
            "phone": "+1234567890" or "+1234567890;+0987654321",
            "member_name": "John Smith"
        }
    """
    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Check if member is a minor - route to parents
    if member.is_minor:
        parents = members_db.get_parents(member_id)

        if not parents:
            return jsonify({
                'error': f"{member.display_name} is a minor with no parents found in household"
            }), 400

        # Collect parent phone numbers
        parent_phones = []
        for parent in parents:
            if parent.phone and parent.phone.strip():
                parent_phones.append(parent.phone.strip())

        if not parent_phones:
            return jsonify({
                'error': f"{member.display_name}'s parents have no phone numbers on file"
            }), 400

        # Return semicolon-separated phones for group SMS
        return jsonify({
            'phone': ';'.join(parent_phones),
            'member_name': member.display_name
        })

    # Normal member - check for phone
    if not member.phone or member.phone.strip() == '':
        return jsonify({
            'error': f"{member.display_name} has no phone number on file"
        }), 400

    return jsonify({
        'phone': member.phone,
        'member_name': member.display_name
    })


@app.template_filter('format_date')
def format_date_filter(date_obj):
    """Template filter to format dates"""
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, config.DATE_FORMAT).date()
    return date_obj.strftime(config.DISPLAY_DATE_FORMAT)


if __name__ == '__main__':
    # Check if data files exist, if not, copy from examples
    if not config.MEMBERS_CSV.exists():
        example_path = config.BASE_DIR / 'data' / 'members.example.csv'
        if example_path.exists():
            import shutil
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(example_path, config.MEMBERS_CSV)
            print(f"Copied example data to {config.MEMBERS_CSV}")

    if not config.PRAYER_ASSIGNMENTS_CSV.exists():
        example_path = config.BASE_DIR / 'data' / 'prayer_assignments.example.csv'
        if example_path.exists():
            import shutil
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(example_path, config.PRAYER_ASSIGNMENTS_CSV)
            print(f"Copied example data to {config.PRAYER_ASSIGNMENTS_CSV}")

    print(f"MLS3 starting...")
    print(f"Data directory: {config.DATA_DIR}")
    print(f"Members CSV: {config.MEMBERS_CSV}")
    print(f"Loaded {len(members_db.members)} members")
    print(f"Loaded {len(assignments_db.assignments)} assignments")

    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
