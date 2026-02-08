# Smart Template Expansion - Implementation Plan

## Overview
Enhance MLS3's SMS template system with conditional flag-based expansions, smart date handling, and random pleasantries.

## Template Syntax Design

### 1. Conditional Flag Syntax: `{variable|flag?value_if_true:value_if_false}`

**Syntax Pattern**: `{var|flag?transform:transform}`
- `var` - variable name (e.g., name, date)
- `flag` - color flag to check (blue, yellow, red)
- `?` - conditional operator
- `transform:transform` - value if flag present : value if flag absent

**Examples**:
```yaml
# Name formality based on blue flag
"Hi {name|blue?formal:casual}, could you meet..."
# → Member has blue flag: "Hi Brother Smith, could you meet..."
# → Member lacks blue flag: "Hi John, could you meet..."

# Date verbosity based on red flag
"Reminder {smart_date|red?long:short}"
# → Member has red flag: "Reminder tomorrow, February 9, 2026"
# → Member lacks red flag: "Reminder tomorrow"
```

### 2. Smart Date Variable: `{smart_date}`

**Behavior**:
- Compares current date with appointment/event date
- Returns:
  - `"today"` if same day
  - `"tomorrow"` if next day
  - Formatted date string otherwise (e.g., "Sunday, February 9")

**Example**:
```yaml
reminder: "Hi {name|blue?formal:casual}, reminder for your appointment {smart_date} at {time}"
```

### 3. Random Selection: `{random:list_name}`

**Behavior**:
- Picks random item from predefined pleasantries list
- Lists defined in YAML under `pleasantries:` section
- Can include empty string `""` to allow "no pleasantry" option

**Example**:
```yaml
pleasantries:
  casual_greeting:
    - "I hope you're well."
    - "Hope all is well!"
    - ""  # Empty string = no greeting

appointments:
  default_invite: "Hi {name|blue?formal:casual}, {random:casual_greeting} Would you be available..."
```

## Transform Types

### Name Transforms
- **`formal`** → "Brother/Sister LastName" (gender-aware)
  - Male: "Brother Smith"
  - Female: "Sister Johnson"
- **`casual`** → "FirstName" (uses `member.display_name`: AKA or first word)
  - "John" or "Mike" (if AKA is set)
- **`full`** → "FirstName LastName"
  - "John Smith"

### Date Transforms (for future expansion)
- **`short`** → "Feb 9"
- **`long`** → "Sunday, February 9, 2026"
- Default (no transform) → "February 9"

Note: Start with basic formatted dates, can add short/long later if needed.

## Phase 1: Template Expansion Engine

### 1.1 Create `utils/template_expander.py`

New module dedicated to smart template expansion:

```python
"""
Smart Template Expander for MLS3
Handles conditional flag-based expansions, smart dates, and random pleasantries
"""
import re
import random
from datetime import date
from typing import Optional, Dict, Any
from models import Member
import config


class SmartTemplateExpander:
    """
    Expands message templates with smart variables.

    Supported syntax:
    - {variable|flag?transform:transform} - Conditional based on member flag
    - {smart_date} - Today/tomorrow/formatted date
    - {random:list_name} - Random selection from list
    - {simple_variable} - Standard variable substitution
    """

    # Regex patterns
    CONDITIONAL_PATTERN = re.compile(r'\{(\w+)\|(\w+)\?(\w+):(\w+)\}')
    RANDOM_PATTERN = re.compile(r'\{random:(\w+)\}')
    SMART_DATE_PATTERN = re.compile(r'\{smart_date(?:\|(\w+)\?(\w+):(\w+))?\}')
    SIMPLE_VAR_PATTERN = re.compile(r'\{(\w+)\}')

    def __init__(self, templates_obj):
        """
        Args:
            templates_obj: MessageTemplates instance with pleasantries loaded
        """
        self.templates = templates_obj

    def expand(self, template_str: str, member: Member,
               appointment=None, **kwargs) -> str:
        """
        Expand template with all smart variables.

        Args:
            template_str: Raw template string
            member: Member object
            appointment: Optional appointment/assignment object (for dates)
            **kwargs: Additional simple variables (e.g., conductor="Bishop")

        Returns:
            Fully expanded message string
        """
        result = template_str

        # 1. Expand {random:list_name}
        result = self._expand_random_variables(result)

        # 2. Expand {smart_date|flag?transform:transform} or {smart_date}
        if appointment:
            result = self._expand_smart_date_variables(result, member, appointment)

        # 3. Expand {variable|flag?transform:transform}
        result = self._expand_conditional_variables(result, member, appointment, kwargs)

        # 4. Expand remaining {simple_variable}
        result = self._expand_simple_variables(result, member, appointment, kwargs)

        return result

    def _expand_random_variables(self, text: str) -> str:
        """Expand {random:list_name} with random selection from pleasantries"""
        def replace_random(match):
            list_name = match.group(1)
            pleasantries_list = self.templates.pleasantries.get(list_name, [])
            if not pleasantries_list:
                return ""  # Empty if list not found
            return random.choice(pleasantries_list)

        return self.RANDOM_PATTERN.sub(replace_random, text)

    def _expand_smart_date_variables(self, text: str, member: Member, appointment) -> str:
        """Expand {smart_date} and {smart_date|flag?transform:transform}"""
        def replace_smart_date(match):
            flag = match.group(1)
            true_transform = match.group(2)
            false_transform = match.group(3)

            # Get base smart date value
            smart_date_value = self._calculate_smart_date(appointment)

            # If conditional, apply transform
            if flag and true_transform and false_transform:
                has_flag = member.has_flag(flag)
                transform = true_transform if has_flag else false_transform
                return self._apply_date_transform(smart_date_value, appointment, transform)

            return smart_date_value

        return self.SMART_DATE_PATTERN.sub(replace_smart_date, text)

    def _calculate_smart_date(self, appointment) -> str:
        """Calculate smart date string based on appointment date vs today"""
        if not appointment:
            return ""

        appt_date = appointment.date_obj
        today = date.today()
        delta = (appt_date - today).days

        if delta == 0:
            return "today"
        elif delta == 1:
            return "tomorrow"
        else:
            # Default format: "Sunday, February 9"
            return appt_date.strftime("%A, %B %d")

    def _apply_date_transform(self, base_value: str, appointment, transform: str) -> str:
        """Apply transform to date (for future: short, long, etc.)"""
        if not appointment:
            return base_value

        appt_date = appointment.date_obj

        if transform == "short":
            return appt_date.strftime("%b %d")  # "Feb 9"
        elif transform == "long":
            return appt_date.strftime("%A, %B %d, %Y")  # "Sunday, February 9, 2026"
        else:
            # Unknown transform, return base value
            return base_value

    def _expand_conditional_variables(self, text: str, member: Member,
                                     appointment, extra_vars: Dict) -> str:
        """Expand {variable|flag?transform:transform}"""
        def replace_conditional(match):
            var_name = match.group(1)
            flag = match.group(2)
            true_transform = match.group(3)
            false_transform = match.group(4)

            has_flag = member.has_flag(flag)
            transform = true_transform if has_flag else false_transform

            return self._apply_transform(var_name, transform, member, appointment, extra_vars)

        return self.CONDITIONAL_PATTERN.sub(replace_conditional, text)

    def _apply_transform(self, var_name: str, transform: str, member: Member,
                        appointment, extra_vars: Dict) -> str:
        """Apply named transform to variable"""

        # Name transforms
        if var_name == "name":
            if transform == "formal":
                # "Brother/Sister LastName"
                prefix = "Brother" if member.gender == "M" else "Sister"
                return f"{prefix} {member.last_name}"
            elif transform == "casual":
                # First name only (uses display_name: AKA or first word)
                return member.display_name
            elif transform == "full":
                # "FirstName LastName"
                return member.full_name
            else:
                # Unknown transform, default to casual
                return member.display_name

        # Date transforms (for variables other than smart_date)
        elif var_name == "date" and appointment:
            if transform == "short":
                return appointment.date_obj.strftime("%b %d")
            elif transform == "long":
                return appointment.date_obj.strftime("%A, %B %d, %Y")
            else:
                # Default date format from config
                return appointment.date_obj.strftime(config.DISPLAY_DATE_FORMAT)

        # Unknown variable/transform
        return f"{{{var_name}}}"  # Return unchanged

    def _expand_simple_variables(self, text: str, member: Member,
                                 appointment, extra_vars: Dict) -> str:
        """Expand {simple_variable} using standard substitution"""
        # Build context dictionary
        context = {
            'first_name': member.display_name,
            'last_name': member.last_name,
            'member_name': member.display_name,  # For backward compatibility
            'full_name': member.full_name,
        }

        # Add appointment/assignment variables if present
        if appointment:
            context['date'] = appointment.date_obj.strftime(config.DISPLAY_DATE_FORMAT)

            # Check if it's a prayer assignment or appointment
            if hasattr(appointment, 'prayer_type'):
                context['prayer_type'] = appointment.prayer_type.lower()
            elif hasattr(appointment, 'appointment_type'):
                context['appointment_type'] = appointment.appointment_type
                context['time'] = appointment.datetime_obj.strftime('%I:%M %p')
                context['conductor'] = appointment.conductor

        # Add extra variables
        context.update(extra_vars)

        # Use Python's format method
        try:
            return text.format(**context)
        except KeyError as e:
            # Variable not found, return text as-is
            return text
```

### 1.2 Update `models.py` - MessageTemplates Class

Add pleasantries loading and smart expansion method:

```python
class MessageTemplates:
    def __init__(self, yaml_path: Path = None):
        self.yaml_path = yaml_path or config.MESSAGE_TEMPLATES_YAML
        self.templates = {}
        self.pleasantries = {}  # NEW
        self.load()

    def load(self):
        """Load templates from YAML file"""
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

            # Extract pleasantries section (NEW)
            self.pleasantries = data.get('pleasantries', {})

            # Load templates (exclude pleasantries)
            self.templates = {k: v for k, v in data.items() if k != 'pleasantries'}

    def get_template(self, activity: str, template_name: str) -> str:
        """Get a specific template"""
        return self.templates.get(activity, {}).get(template_name, "")

    def expand_template(self, activity: str, template_name: str, **kwargs) -> str:
        """Get template and expand variables (LEGACY - simple expansion only)"""
        template = self.get_template(activity, template_name)
        return template.format(**kwargs)

    def expand_smart(self, activity: str, template_name: str,  # NEW METHOD
                     member, appointment=None, **kwargs) -> str:
        """
        Get template and expand with smart variables.

        Args:
            activity: Template category (prayer, appointments, adhoc)
            template_name: Template name within category
            member: Member object
            appointment: Optional appointment/assignment object
            **kwargs: Additional simple variables

        Returns:
            Fully expanded message string
        """
        from utils.template_expander import SmartTemplateExpander

        template = self.get_template(activity, template_name)
        expander = SmartTemplateExpander(self)
        return expander.expand(template, member, appointment, **kwargs)
```

## Phase 2: Update Message Templates YAML

### 2.1 Add Pleasantries Section

At the top of `data/message_templates.yaml`:

```yaml
pleasantries:
  casual_greeting:
    - "I hope you're well."
    - "Hope all is well!"
    - "Hope you're doing great!"
    - ""  # Empty string option (no greeting)

  casual_reminder:
    - ""  # Empty most of the time
    - "Just a friendly reminder:"
    - "Quick reminder:"

prayer:
  invite: "Hi {name|blue?formal:casual}, would you be willing to say a prayer in sacrament meeting on {date}? Is opening or closing better for you?"
  reminder: "Hi {name|blue?formal:casual}, {random:casual_reminder} Reminder that you're scheduled for the {prayer_type} prayer in sacrament meeting {smart_date}. Thank you!"
  thank_you: "Thanks {name|blue?formal:casual} for agreeing to say the {prayer_type} prayer on {date}!"

appointments:
  default_invite: "Hi {name|blue?formal:casual}, would you be available to meet with {conductor} on {date} at {time}?"
  default_reminder: "Hi {name|blue?formal:casual}, {random:casual_reminder} Reminder for your {appointment_type} appointment with {conductor} {smart_date} at {time}"

  Set apart_invite: "Hi {name|blue?formal:casual}, could you meet with {conductor} to be set apart on {date} at {time}?"
  Set apart_reminder: "Hi {name|blue?formal:casual}, sending a reminder to be set apart at {time} with {conductor}"

  Temple recommend_invite: "Hi {name|blue?formal:casual}, could you meet with {conductor} for a temple recommend interview on {date} at {time}?"
  Temple recommend_reminder: "Hi {name|blue?formal:casual}, sending a reminder for your Temple recommend interview at {time} with {conductor}"

  # ... update all remaining appointment types similarly
```

Note: Update all 14 appointment types with the new syntax.

## Phase 3: Update SMS Handler

### 3.1 Refactor `utils/sms_handler.py`

Replace prayer-specific functions with generic smart expansion:

```python
# Remove old expand_prayer_template function
# Remove old send_prayer_invitation, send_prayer_reminder, send_thank_you

def expand_and_send(activity: str, template_name: str, member: Member,
                    templates, appointment=None, **kwargs) -> bool:
    """
    Generic function to expand template with smart variables and send SMS.

    Args:
        activity: Template category (prayer, appointments, adhoc)
        template_name: Template name within category (invite, reminder, etc.)
        member: Member object
        templates: MessageTemplates instance
        appointment: Optional appointment/assignment object
        **kwargs: Additional variables (e.g., conductor="Bishop")

    Returns:
        True if SMS was successfully queued, False otherwise
    """
    # Check for phone number
    if not member.phone or member.phone.strip() == '':
        print(f"ERROR: Cannot send SMS - {member.full_name} has no phone number")
        return False

    # Expand template with smart variables
    message = templates.expand_smart(activity, template_name, member, appointment, **kwargs)

    # Send via Tasker
    return send_sms_intent(member.phone, message)


# Keep send_sms_intent unchanged
def send_sms_intent(phone_number: str, message: str) -> bool:
    """
    Opens Android SMS app with pre-filled message using termux-open-url.
    User must manually press send.
    """
    # ... existing implementation unchanged
```

## Phase 4: Update Backend Routes

### 4.1 Update Prayer Routes in `app.py`

Replace old `send_prayer_invitation()` calls with new `expand_and_send()`:

```python
@app.route('/api/assignments/<int:assignment_id>/invite', methods=['POST'])
def api_send_invitation(assignment_id):
    """Send invitation SMS and update state to Invited"""
    from utils.sms_handler import expand_and_send  # NEW IMPORT

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Update state to Invited (do this first)
    assignments_db.update_state(assignment_id, 'Invited')

    # Check if member has phone number
    if not member.phone or member.phone.strip() == '':
        return jsonify({'error': f'{member.full_name} has no phone number on file'}), 400

    # Send SMS using smart templates
    success = expand_and_send('prayer', 'invite', member, templates, assignment)

    if success:
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
    from utils.sms_handler import expand_and_send  # NEW IMPORT

    assignment = assignments_db.get_by_id(assignment_id)
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    if not assignment.member_id or assignment.member_id == 0:
        return jsonify({'error': 'No member assigned'}), 400

    member = members_db.get_by_id(assignment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Send SMS using smart templates
    success = expand_and_send('prayer', 'reminder', member, templates, assignment)

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
```

### 4.2 Update Appointment Routes in `app.py`

Replace inline template expansion with `expand_and_send()`:

```python
@app.route('/api/appointments/<int:appointment_id>/invite', methods=['POST'])
def send_appointment_invite(appointment_id):
    """Send appointment invitation to member"""
    from utils.sms_handler import expand_and_send  # NEW IMPORT

    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Update state to Invited (do this first)
    appointments_db.update_state(appointment_id, 'Invited')

    # Check if member has phone number
    if not member.phone or member.phone.strip() == '':
        return jsonify({'error': f'{member.full_name} has no phone number on file'}), 400

    # Get template name (specific or default)
    template_name = f'{appointment.appointment_type}_invite'
    if not templates.get_template('appointments', template_name):
        template_name = 'default_invite'

    # Send SMS using smart templates (NEW)
    success = expand_and_send('appointments', template_name, member, templates, appointment)

    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to send SMS'}), 500

@app.route('/api/appointments/<int:appointment_id>/remind', methods=['POST'])
def send_appointment_reminder(appointment_id):
    """Send appointment reminder to member"""
    from utils.sms_handler import expand_and_send  # NEW IMPORT

    appointment = appointments_db.get_by_id(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404

    member = members_db.get_by_id(appointment.member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Check if member has phone number
    if not member.phone or member.phone.strip() == '':
        return jsonify({'error': f'{member.full_name} has no phone number on file'}), 400

    # Get template name (specific or default)
    template_name = f'{appointment.appointment_type}_reminder'
    if not templates.get_template('appointments', template_name):
        template_name = 'default_reminder'

    # Send SMS using smart templates (NEW)
    success = expand_and_send('appointments', template_name, member, templates, appointment)

    if success:
        # Update state to Reminded (allows multiple reminders)
        appointments_db.update_state(appointment_id, 'Reminded')
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to send SMS'}), 500
```

## Testing Strategy

### Unit Tests (Manual)

1. **Conditional Name Expansion**
   - Create test member with blue flag → verify formal name used
   - Create test member without blue flag → verify casual name used
   - Test both genders (Brother vs Sister)

2. **Smart Date Expansion**
   - Create appointment for today → verify "today"
   - Create appointment for tomorrow → verify "tomorrow"
   - Create appointment for future date → verify formatted date string

3. **Random Pleasantries**
   - Send multiple messages → verify different pleasantries chosen
   - Verify empty string option works (no pleasantry)

4. **Backward Compatibility**
   - Test old templates with `{first_name}` → should still work
   - Test old templates with `{member_name}` → should still work

### Integration Tests

1. **Prayer Workflow**
   - Create prayer assignment
   - Assign member with blue flag
   - Send invite → verify formal name in message
   - Send reminder with smart_date → verify correct date text

2. **Appointment Workflow**
   - Create appointment for tomorrow
   - Assign member without blue flag
   - Send invite → verify casual name in message
   - Send reminder → verify "tomorrow" in message

3. **Edge Cases**
   - Member with no flags → should use "else" value
   - Member with multiple flags → each template checks independently
   - Appointment in past → smart_date should still work (show date string)
   - Empty pleasantry list → should return empty string

## Implementation Checklist

- [ ] Create `utils/template_expander.py` with SmartTemplateExpander class
- [ ] Update `models.py` MessageTemplates class
  - [ ] Add `pleasantries` dictionary
  - [ ] Add `expand_smart()` method
  - [ ] Update `load()` to parse pleasantries
- [ ] Update `data/message_templates.yaml`
  - [ ] Add pleasantries section
  - [ ] Update prayer templates with new syntax
  - [ ] Update all 14 appointment types with new syntax
- [ ] Update `utils/sms_handler.py`
  - [ ] Add `expand_and_send()` function
  - [ ] Remove old prayer-specific functions
- [ ] Update `app.py` routes
  - [ ] Prayer invite route
  - [ ] Prayer reminder route
  - [ ] Appointment invite route
  - [ ] Appointment reminder route
- [ ] Test all functionality
  - [ ] Unit tests for expansion logic
  - [ ] Integration tests for SMS sending
  - [ ] Edge case testing

## Backward Compatibility Notes

All existing templates will continue to work:
- Simple variables like `{first_name}`, `{date}`, `{time}` work as before
- Python's `.format()` method handles simple substitution
- New syntax is optional and additive
- No breaking changes to existing functionality

## Future Enhancements (Not in This Plan)

- Date transform variations (short, long) - can add when needed
- Additional name transforms - can add when needed
- More pleasantry lists - easy to add in YAML
- Conditional logic beyond flags - would need syntax extension
