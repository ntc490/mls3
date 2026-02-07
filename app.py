"""
MLS3 - Member Leadership Scheduling System
Flask application entry point
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for
from datetime import datetime, date, timedelta

import config
from models import MemberDatabase, PrayerAssignmentDatabase, MessageTemplates


app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

# Initialize data models
members_db = MemberDatabase()
assignments_db = PrayerAssignmentDatabase()
templates = MessageTemplates()


def get_next_sunday(from_date: date = None) -> date:
    """Get the next Sunday from a given date (or today)"""
    if from_date is None:
        from_date = date.today()

    days_ahead = 6 - from_date.weekday()  # Sunday is 6
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


@app.route('/')
def index():
    """Homepage"""
    return render_template(
        'index.html',
        member_count=len(members_db.get_active_members()),
        next_sunday=get_next_sunday()
    )


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
            'gender': m.gender,
            'phone': m.phone,
            'birthday': m.birthday,
            'age': calc_age(m.birthday),
            'last_prayer_date': m.last_prayer_date,
            'dont_ask_prayer': m.dont_ask_prayer,
            'active': m.active,
            'notes': m.notes
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
    next_sunday = get_next_sunday()

    # Get existing assignments for next Sunday
    sunday_assignments = assignments_db.get_assignments_for_date(next_sunday)

    # Find opening and closing assignments
    opening = None
    closing = None

    for assignment in sunday_assignments:
        if assignment.state != 'Completed':
            if assignment.prayer_type == 'Opening':
                opening = assignment
            elif assignment.prayer_type == 'Closing':
                closing = assignment

    # Get all active assignments for other dates (the queue)
    all_active = assignments_db.get_active_assignments()
    next_sunday_str = next_sunday.strftime(config.DATE_FORMAT)

    # Filter to only future assignments not for next Sunday
    active_queue = [
        a for a in all_active
        if a.date != next_sunday_str and a.state != 'Completed'
    ]

    # Sort by date
    active_queue.sort(key=lambda a: a.date)

    return render_template(
        'prayer_scheduler.html',
        next_sunday=next_sunday,
        opening_assignment=opening,
        closing_assignment=closing,
        active_queue=active_queue,
        members_db=members_db
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
            'last_prayer_date': m.last_prayer_date,
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

    assignments_db.update_assignment(
        assignment_id,
        member_id=member_id,
        prayer_type=prayer_type,
        date=target_date
    )

    return jsonify({'success': True})


@app.route('/api/assignments/<int:assignment_id>/state', methods=['POST'])
def api_update_assignment_state(assignment_id):
    """Update assignment state"""
    data = request.json
    new_state = data.get('state')

    if not new_state:
        return jsonify({'error': 'Missing state'}), 400

    assignments_db.update_state(assignment_id, new_state)

    # If completed, update member's last prayer date
    if new_state == 'Completed':
        assignment = assignments_db.get_by_id(assignment_id)
        if assignment:
            members_db.update_last_prayer_date(assignment.member_id, assignment.date_obj)

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
        'last_prayer_date': member.last_prayer_date,
        'notes': member.notes,
        'prayer_history': prayer_history
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
