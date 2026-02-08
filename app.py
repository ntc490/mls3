"""
MLS3 - Member Leadership Scheduling System
Flask application entry point
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for
from datetime import datetime, date, timedelta

import config
from models import (
    MemberDatabase, PrayerAssignmentDatabase, MessageTemplates,
    AppointmentTypesDatabase, AppointmentDatabase
)


app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

# Initialize data models
members_db = MemberDatabase()
assignments_db = PrayerAssignmentDatabase()
templates = MessageTemplates()
appointment_types_db = AppointmentTypesDatabase()
appointments_db = AppointmentDatabase()


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

    # Get events for current week (today through next Sunday)
    today = date.today()
    next_sunday = get_next_sunday(today)

    # If today is Sunday and it's before noon, include today
    if today.weekday() == 6:  # Sunday is 6
        from datetime import datetime as dt
        if dt.now().hour < 12:
            week_start = today
        else:
            # After noon on Sunday, show next week
            week_start = today + timedelta(days=1)
            next_sunday = get_next_sunday(week_start)
    else:
        week_start = today

    # Get prayer assignments for current week
    upcoming_assignments = [
        a for a in assignments_db.assignments
        if week_start <= a.date_obj <= next_sunday
    ]

    # Get appointments for current week (including completed)
    upcoming_appointments = [
        a for a in appointments_db.appointments
        if week_start <= a.date_obj <= next_sunday
    ]

    # Group calendar items by date
    items_by_date = defaultdict(list)

    # Add prayer assignments
    for assignment in upcoming_assignments:
        member = members_db.get_by_id(assignment.member_id)
        member_name = member.full_name if member else "Unknown"
        member_phone = member.phone if member else ""

        items_by_date[assignment.date].append({
            'type': 'prayer',
            'assignment_id': assignment.assignment_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'prayer_type': assignment.prayer_type,
            'state': assignment.state,
            'date_obj': assignment.date_obj
        })

    # Add appointments
    for appointment in upcoming_appointments:
        member = members_db.get_by_id(appointment.member_id)
        member_name = member.full_name if member else "Unknown"
        member_phone = member.phone if member else ""

        items_by_date[appointment.date].append({
            'type': 'appointment',
            'appointment_id': appointment.appointment_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'appointment_type': appointment.appointment_type,
            'time': appointment.time,
            'conductor': appointment.conductor,
            'state': appointment.state,
            'date_obj': appointment.date_obj
        })

    # Convert to sorted list of (date, items) tuples
    # Sort items within each date by time (appointments have time, prayers don't)
    for date_str, items in items_by_date.items():
        items.sort(key=lambda x: x.get('time', '23:59'))  # Prayers go last

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
    filtered_appointments = [
        a for a in appointments_db.appointments
        if date_from <= a.date_obj <= date_to
    ]

    # Group calendar items by date
    items_by_date = defaultdict(list)

    # Add prayer assignments
    for assignment in filtered_assignments:
        member = members_db.get_by_id(assignment.member_id)
        member_name = member.full_name if member else "Unknown"
        member_phone = member.phone if member else ""

        items_by_date[assignment.date].append({
            'type': 'prayer',
            'assignment_id': assignment.assignment_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'prayer_type': assignment.prayer_type,
            'state': assignment.state,
            'date_obj': assignment.date_obj
        })

    # Add appointments
    for appointment in filtered_appointments:
        member = members_db.get_by_id(appointment.member_id)
        member_name = member.full_name if member else "Unknown"
        member_phone = member.phone if member else ""

        items_by_date[appointment.date].append({
            'type': 'appointment',
            'appointment_id': appointment.appointment_id,
            'member_name': member_name,
            'member_phone': member_phone,
            'appointment_type': appointment.appointment_type,
            'time': appointment.time,
            'conductor': appointment.conductor,
            'state': appointment.state,
            'date_obj': appointment.date_obj
        })

    # Sort items within each date
    for date_str, items in items_by_date.items():
        items.sort(key=lambda x: x.get('time', '23:59'))

    # Convert to sorted list
    calendar_items = sorted(items_by_date.items(), key=lambda x: datetime.strptime(x[0], config.DATE_FORMAT).date())

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

    # Get all active assignments for other dates (the queue)
    all_active = assignments_db.get_active_assignments()
    target_sunday_str = target_sunday.strftime(config.DATE_FORMAT)

    # Filter to only future assignments not for target Sunday
    active_queue = [
        a for a in all_active
        if a.date != target_sunday_str and a.state != 'Completed'
    ]

    # Sort by date
    active_queue.sort(key=lambda a: a.date)

    # Calculate prev/next Sunday for navigation
    prev_sunday = target_sunday - timedelta(days=7)
    next_sunday_nav = target_sunday + timedelta(days=7)

    return render_template(
        'prayer_scheduler.html',
        target_sunday=target_sunday,
        next_sunday=get_next_sunday(),  # For "Create Assignment" default
        slot1=slot1,
        slot2=slot2,
        active_queue=active_queue,
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
    from utils.sms_handler import send_prayer_invitation

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Send SMS
    success = send_prayer_invitation(member, assignment, templates)

    if success:
        # Update state to Invited
        assignments_db.update_state(assignment_id, 'Invited')
        return jsonify({'success': True, 'message': 'SMS sent'})
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to launch SMS app',
            'phone': member.phone,
            'member': member.full_name
        }), 500


@app.route('/api/assignments/<int:assignment_id>/reminder-message', methods=['GET'])
def api_get_reminder_message(assignment_id):
    """Get the reminder message text for an assignment"""
    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Format the date
    from datetime import datetime
    formatted_date = datetime.strptime(assignment.date, config.DATE_FORMAT).strftime(config.DISPLAY_DATE_FORMAT)

    # Get the reminder message template
    message = templates.expand_template(
        'prayer',
        'reminder',
        first_name=member.display_name,
        prayer_type=assignment.prayer_type,
        date=formatted_date
    )

    return jsonify({
        'message': message,
        'phone': member.phone
    })


@app.route('/api/assignments/<int:assignment_id>/remind', methods=['POST'])
def api_send_reminder(assignment_id):
    """Send reminder SMS and update state to Reminded"""
    from utils.sms_handler import send_prayer_reminder

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Send SMS
    success = send_prayer_reminder(member, assignment, templates)

    if success:
        # Update state to Reminded
        assignments_db.update_state(assignment_id, 'Reminded')
        return jsonify({'success': True, 'message': 'SMS sent'})
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to launch SMS app',
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
        event_history.append({
            'type': 'appointment',
            'date': appointment.date,
            'date_obj': appointment.date_obj,
            'time': appointment.time,
            'appointment_type': appointment.appointment_type,
            'conductor': appointment.conductor,
            'state': appointment.state,
            'formatted_date': datetime.strptime(appointment.date, config.DATE_FORMAT).strftime(config.DISPLAY_DATE_FORMAT)
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
        'phone': member.phone,
        'recommend_expiration': member.recommend_expiration,
        'active': member.active,
        'dont_ask_prayer': member.dont_ask_prayer,
        'last_prayer_date': members_db.get_last_prayer_date(member_id, assignments_db),
        'notes': member.notes,
        'skip_until': member.skip_until,
        'flag': member.flag,
        'aka': member.aka,
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


@app.route('/appointment-scheduler')
def appointment_scheduler():
    """Appointment scheduler page"""
    # Can be accessed with member_id, appointment_id, or standalone
    return render_template('appointment_scheduler.html')


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
        # Filter by specific date
        appointments_list = [
            appt for appt in appointments_db.appointments
            if appt.date == date_filter and appt.state not in ['Completed', 'Cancelled']
        ]
    else:
        # Get all appointments
        appointments_list = appointments_db.appointments

    result = []
    for appt in appointments_list:
        member = members_db.get_by_id(appt.member_id)
        result.append({
            'appointment_id': appt.appointment_id,
            'member_id': appt.member_id,
            'member_name': member.full_name if member else "Unknown",
            'appointment_type': appt.appointment_type,
            'date': appt.date,
            'time': appt.time,
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

    # Get all appointments for this date and conductor
    existing_appointments = [
        appt for appt in appointments_db.appointments
        if appt.date == date_str
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
        conductor=conductor
    )

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
        conductor=conductor
    )

    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>/invite', methods=['POST'])
def send_appointment_invite(appointment_id):
    """Send appointment invitation to member"""
    print(f"[DEBUG] send_appointment_invite called for appointment_id={appointment_id}")

    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    print(f"[DEBUG] Member: {member.display_name}, Phone: {member.phone}")

    # Get message template
    template = templates.get_template('appointments', f'{appointment.appointment_type}_invite')
    if not template:
        template = templates.get_template('appointments', 'default_invite')

    # Format the message
    appt_datetime = appointment.datetime_obj
    message = template.format(
        member_name=member.display_name,
        appointment_type=appointment.appointment_type,
        date=appt_datetime.strftime(config.DISPLAY_DATE_FORMAT),
        time=appt_datetime.strftime('%I:%M %p'),
        conductor=format_conductor_for_message(appointment.conductor)
    )

    # Update state to Invited
    appointments_db.update_state(appointment_id, 'Invited')

    # Send SMS
    from utils.sms_handler import send_sms_intent
    send_sms_intent(member.phone, message)

    return jsonify({'success': True, 'message': message})


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

    # Format the message
    appt_datetime = appointment.datetime_obj
    message = template.format(
        member_name=member.display_name,
        appointment_type=appointment.appointment_type,
        date=appt_datetime.strftime(config.DISPLAY_DATE_FORMAT),
        time=appt_datetime.strftime('%I:%M %p'),
        conductor=format_conductor_for_message(appointment.conductor)
    )

    return jsonify({'message': message})


@app.route('/api/appointments/<int:appointment_id>/remind', methods=['POST'])
def send_appointment_reminder(appointment_id):
    """Send appointment reminder to member"""
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

    # Format the message
    appt_datetime = appointment.datetime_obj
    message = template.format(
        member_name=member.display_name,
        appointment_type=appointment.appointment_type,
        date=appt_datetime.strftime(config.DISPLAY_DATE_FORMAT),
        time=appt_datetime.strftime('%I:%M %p'),
        conductor=format_conductor_for_message(appointment.conductor)
    )

    # Update state to Reminded only if not already reminded
    # This allows sending multiple reminders
    if appointment.state != 'Reminded':
        appointments_db.update_state(appointment_id, 'Reminded')

    # Send SMS
    from utils.sms_handler import send_sms_intent
    send_sms_intent(member.phone, message)

    return jsonify({'success': True, 'message': message})


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
    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>/delete', methods=['POST'])
def delete_appointment(appointment_id):
    """Delete an appointment"""
    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    # Remove from list and save
    appointments_db.appointments = [a for a in appointments_db.appointments if a.appointment_id != appointment_id]
    appointments_db.save()

    return jsonify({'success': True})


@app.route('/api/appointments/<int:appointment_id>', methods=['GET'])
def get_appointment(appointment_id):
    """Get a single appointment by ID"""
    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)

    return jsonify({
        'appointment_id': appointment.appointment_id,
        'member_id': appointment.member_id,
        'member_name': member.full_name if member else "Unknown",
        'appointment_type': appointment.appointment_type,
        'date': appointment.date,
        'time': appointment.time,
        'duration_minutes': appointment.duration_minutes,
        'conductor': appointment.conductor,
        'state': appointment.state,
        'created_date': appointment.created_date,
        'last_updated': appointment.last_updated,
        'completed_date': appointment.completed_date
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
