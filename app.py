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
    """List all active members (for testing)"""
    members = members_db.get_active_members()
    men = [m for m in members if m.gender == 'M']
    women = [m for m in members if m.gender == 'F']

    return render_template(
        'members_list.html',
        members=members,
        all_count=len(members),
        men_count=len(men),
        women_count=len(women)
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

    return render_template(
        'prayer_scheduler.html',
        next_sunday=next_sunday,
        opening_assignment=opening,
        closing_assignment=closing,
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

    # Convert to JSON-friendly format
    results = [
        {
            'id': m.member_id,
            'name': m.full_name,
            'gender': m.gender,
            'last_prayer_date': m.last_prayer_date,
            'phone': m.phone
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

    results = [
        {
            'id': c['member'].member_id,
            'name': c['member'].full_name,
            'last_prayer_date': c['last_prayer_date_display'],
            'priority': c['priority']
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
