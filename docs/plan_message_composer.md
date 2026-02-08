# Ad-Hoc SMS Message Composer - Implementation Plan

## Overview
Build an SMS message composer that allows users to send ad-hoc text messages to members using smart templates. Accessible via "SMS+" button in member info cards.

## User Workflow

1. User opens member info card
2. User clicks "SMS+" button
3. Redirected to `/sms-composer?member_id={id}` page
4. User selects from named templates (dropdown)
5. Template expands into editable text box
6. User can edit the message or type custom variables
7. User clicks "Expand" button to re-evaluate variables (if edited)
8. User clicks "Send" button
9. Opens Android SMS app with message pre-filled for that member
10. User sends from SMS app

## UI Design

### SMS Composer Page Layout

```
┌─────────────────────────────────────┐
│ SMS Composer                        │
│ To: John Smith                      │
├─────────────────────────────────────┤
│                                     │
│ Message Template: [Dropdown ▼]     │
│   - General Check-in                │
│   - Event Invitation                │
│   - Calling Extension               │
│   - Birthday                        │
│   - Custom...                       │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ Custom Variables (if needed)    │ │
│ ├─────────────────────────────────┤ │
│ │ Event Name: [____________]      │ │
│ │ Calling Name: [____________]    │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Message:                            │
│ ┌─────────────────────────────────┐ │
│ │ Hi John, I hope you're well.    │ │
│ │ Just wanted to check in and     │ │
│ │ see how you're doing. Let me    │ │
│ │ know if there's anything I      │ │
│ │ can help with.                  │ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
│ 145 characters                      │
│                                     │
│ [Expand Variables] [Send SMS]       │
└─────────────────────────────────────┘
```

## Phase 1: Backend Routes

### 1.1 New Route: `/sms-composer` (GET)

```python
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
    adhoc_templates = templates.templates.get('adhoc', {})

    return render_template('sms_composer.html',
                          member=member,
                          adhoc_templates=adhoc_templates)
```

### 1.2 New Route: `/api/expand-template` (POST)

```python
@app.route('/api/expand-template', methods=['POST'])
def api_expand_template():
    """
    Expand template with member context and custom variables.

    Request JSON:
        {
            "member_id": 123,
            "template": "Hi {name|blue?formal:casual}, {random:casual_greeting} ...",
            "variables": {
                "event_name": "Ward Picnic",
                "calling_name": "Primary Teacher"
            }
        }

    Returns:
        {
            "expanded": "Hi John, I hope you're well. ...",
            "length": 145
        }
    """
    from utils.template_expander import SmartTemplateExpander

    data = request.json
    member_id = data.get('member_id')
    template_str = data.get('template', '')
    custom_vars = data.get('variables', {})

    if not member_id:
        return jsonify({'error': 'Missing member_id'}), 400

    member = members_db.get_by_id(member_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    # Expand template with smart variables
    expander = SmartTemplateExpander(templates)
    expanded = expander.expand(template_str, member, appointment=None, **custom_vars)

    return jsonify({
        'expanded': expanded,
        'length': len(expanded)
    })
```

### 1.3 New Route: `/api/queue-sms` (POST)

```python
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
```

## Phase 2: Frontend Template

### 2.1 New Template: `templates/sms_composer.html`

```html
{% extends "base.html" %}

{% block title %}SMS Composer - {{ member.full_name }}{% endblock %}

{% block content %}
<div class="container">
    <div class="composer-header">
        <h1>SMS Composer</h1>
        <p class="member-name">To: {{ member.full_name }}</p>
        {% if not member.phone %}
        <p class="error-message">⚠️ This member has no phone number on file</p>
        {% endif %}
    </div>

    <div class="composer-form">
        <!-- Template Selector -->
        <div class="form-group">
            <label for="templateSelect">Message Template</label>
            <select id="templateSelect" class="form-select">
                <option value="">-- Select Template --</option>
                {% for template_name in adhoc_templates.keys() %}
                <option value="{{ template_name }}">
                    {{ template_name|replace('_', ' ')|title }}
                </option>
                {% endfor %}
            </select>
        </div>

        <!-- Custom Variables Section (shown dynamically) -->
        <div id="customVarsSection" class="custom-vars-section" style="display: none;">
            <h3>Custom Variables</h3>
            <div id="customVarInputs"></div>
        </div>

        <!-- Message Text Area -->
        <div class="form-group">
            <label for="messageText">Message</label>
            <textarea id="messageText"
                      class="form-textarea"
                      rows="8"
                      placeholder="Select a template or type your message..."></textarea>
            <div class="message-info">
                <span id="charCount">0 characters</span>
                <span class="text-muted">SMS messages are typically limited to 160 characters per segment</span>
            </div>
        </div>

        <!-- Action Buttons -->
        <div class="composer-actions">
            <button id="expandBtn" class="btn btn-secondary">
                Expand Variables
            </button>
            <button id="sendBtn" class="btn btn-primary" {% if not member.phone %}disabled{% endif %}>
                Send SMS
            </button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
    // Pass data to JavaScript
    const memberId = {{ member.member_id }};
    const memberPhone = "{{ member.phone }}";
    const templates = {{ adhoc_templates|tojson }};
</script>
<script src="{{ url_for('static', filename='js/sms_composer.js') }}"></script>
{% endblock %}
```

## Phase 3: Frontend JavaScript

### 3.1 New JavaScript: `static/js/sms_composer.js`

```javascript
/**
 * SMS Composer JavaScript
 * Handles template selection, variable expansion, and SMS sending
 */

// Standard variables that don't need custom input
const STANDARD_VARS = [
    'name', 'first_name', 'last_name', 'member_name', 'full_name',
    'date', 'smart_date', 'time', 'conductor', 'prayer_type',
    'appointment_type'
];

/**
 * Initialize composer
 */
document.addEventListener('DOMContentLoaded', () => {
    // Template selection handler
    document.getElementById('templateSelect').addEventListener('change', handleTemplateSelect);

    // Expand button handler
    document.getElementById('expandBtn').addEventListener('click', expandMessage);

    // Send button handler
    document.getElementById('sendBtn').addEventListener('click', sendSMS);

    // Character counter
    document.getElementById('messageText').addEventListener('input', updateCharCount);

    // Initial character count
    updateCharCount();
});

/**
 * Handle template selection
 */
async function handleTemplateSelect(e) {
    const templateName = e.target.value;

    if (!templateName) {
        // Cleared selection
        document.getElementById('messageText').value = '';
        document.getElementById('customVarsSection').style.display = 'none';
        updateCharCount();
        return;
    }

    // Get template text
    const templateText = templates[templateName];
    if (!templateText) {
        console.error('Template not found:', templateName);
        return;
    }

    // Set template in text area
    document.getElementById('messageText').value = templateText;

    // Detect custom variables
    detectAndShowCustomVars(templateText);

    // Auto-expand
    await expandMessage();
}

/**
 * Detect custom variables in template and show input fields
 */
function detectAndShowCustomVars(templateText) {
    // Pattern: {variable} or {variable|flag?transform:transform}
    const varPattern = /\{([^|}]+)(?:\|[^}]+)?\}/g;
    const customVars = new Set();

    let match;
    while ((match = varPattern.exec(templateText)) !== null) {
        const varName = match[1];

        // Skip standard variables and random:* variables
        if (!STANDARD_VARS.includes(varName) && !varName.startsWith('random:')) {
            customVars.add(varName);
        }
    }

    if (customVars.size > 0) {
        showCustomVarInputs(Array.from(customVars));
    } else {
        document.getElementById('customVarsSection').style.display = 'none';
    }
}

/**
 * Show input fields for custom variables
 */
function showCustomVarInputs(varNames) {
    const container = document.getElementById('customVarInputs');
    container.innerHTML = '';

    varNames.forEach(varName => {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        const label = document.createElement('label');
        label.textContent = varName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        label.htmlFor = `var_${varName}`;

        const input = document.createElement('input');
        input.type = 'text';
        input.id = `var_${varName}`;
        input.className = 'form-input';
        input.dataset.var = varName;
        input.placeholder = `Enter ${varName.replace(/_/g, ' ')}`;

        formGroup.appendChild(label);
        formGroup.appendChild(input);
        container.appendChild(formGroup);
    });

    document.getElementById('customVarsSection').style.display = 'block';
}

/**
 * Get values of custom variables
 */
function getCustomVarValues() {
    const inputs = document.querySelectorAll('#customVarInputs input');
    const values = {};

    inputs.forEach(input => {
        const varName = input.dataset.var;
        const value = input.value.trim();
        if (value) {
            values[varName] = value;
        }
    });

    return values;
}

/**
 * Expand template variables
 */
async function expandMessage() {
    const templateText = document.getElementById('messageText').value.trim();

    if (!templateText) {
        return;
    }

    // Get custom variable values
    const customVars = getCustomVarValues();

    try {
        const response = await fetch('/api/expand-template', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                member_id: memberId,
                template: templateText,
                variables: customVars
            })
        });

        if (!response.ok) {
            throw new Error('Failed to expand template');
        }

        const result = await response.json();

        // Update text area with expanded message
        document.getElementById('messageText').value = result.expanded;

        // Update character count
        updateCharCount();

    } catch (error) {
        console.error('Error expanding template:', error);
        alert('Failed to expand template: ' + error.message);
    }
}

/**
 * Send SMS
 */
async function sendSMS() {
    const message = document.getElementById('messageText').value.trim();

    if (!message) {
        alert('Please enter a message');
        return;
    }

    if (!memberPhone) {
        alert('This member has no phone number on file');
        return;
    }

    try {
        const response = await fetch('/api/queue-sms', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                phone: memberPhone,
                message: message
            })
        });

        if (!response.ok) {
            throw new Error('Failed to queue SMS');
        }

        // Success - redirect to home
        window.location.href = '/';

    } catch (error) {
        console.error('Error sending SMS:', error);
        alert('Failed to send SMS: ' + error.message);
    }
}

/**
 * Update character count
 */
function updateCharCount() {
    const text = document.getElementById('messageText').value;
    const length = text.length;
    const segments = Math.ceil(length / 160) || 0;

    const countText = `${length} characters`;
    const segmentText = segments > 1 ? ` (${segments} SMS segments)` : '';

    document.getElementById('charCount').textContent = countText + segmentText;
}
```

## Phase 4: Update Member Info Modal

### 4.1 Update `templates/base.html`

Change SMS button label and handler:

```html
<!-- In member info modal -->
<div class="member-actions-section">
    <button id="sendTextBtn" class="btn btn-secondary">SMS+</button>  <!-- Changed label -->
    <button id="apptBtn" class="btn btn-primary">Appt</button>
    <button id="prayBtn" class="btn btn-primary">Pray</button>
</div>
```

### 4.2 Update `static/js/member_modal.js`

Change `sendTextMessage()` function:

```javascript
/**
 * Send text message - opens SMS composer
 */
function sendTextMessage() {
    if (!currentMemberId) return;

    // Redirect to SMS composer
    window.location.href = `/sms-composer?member_id=${currentMemberId}`;
}
```

## Phase 5: Add Ad-Hoc Templates to YAML

### 5.1 Add `adhoc:` Section to `data/message_templates.yaml`

```yaml
# ... existing pleasantries, prayer, appointments sections ...

adhoc:
  general_checkin: "Hi {name|blue?formal:casual}, {random:casual_greeting} Just wanted to check in and see how you're doing. Let me know if there's anything I can help with."

  event_invitation: "Hi {name|blue?formal:casual}, {random:casual_greeting} We're having {event_name} on {date} at {time}. Hope you can join us!"

  calling_extension: "Hi {name|blue?formal:casual}, I wanted to reach out about extending your calling as {calling_name}. Would you be willing to continue serving?"

  birthday: "Hi {name|blue?formal:casual}, Happy Birthday! Hope you have a wonderful day!"

  thank_you: "Hi {name|blue?formal:casual}, thank you so much for {action}. It really means a lot!"

  follow_up: "Hi {name|blue?formal:casual}, {random:casual_greeting} Just following up on {topic}. Let me know if you have any questions."
```

## Phase 6: CSS Styling

### 6.1 Add to `static/css/style.css`

```css
/* SMS Composer Styles */
.composer-header {
    margin-bottom: 2rem;
}

.composer-header h1 {
    margin-bottom: 0.5rem;
}

.composer-header .member-name {
    font-size: 1.1rem;
    color: var(--text-muted);
    margin: 0;
}

.composer-header .error-message {
    color: var(--danger-color);
    font-weight: 500;
    margin-top: 0.5rem;
}

.composer-form {
    max-width: 600px;
}

.custom-vars-section {
    background: var(--light-bg);
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
}

.custom-vars-section h3 {
    margin-top: 0;
    margin-bottom: 1rem;
    font-size: 1rem;
    color: var(--text-dark);
}

.form-textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-family: inherit;
    font-size: 1rem;
    resize: vertical;
    min-height: 150px;
}

.form-textarea:focus {
    outline: none;
    border-color: var(--primary-color);
}

.message-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.5rem;
    font-size: 0.9rem;
}

.message-info #charCount {
    font-weight: 500;
    color: var(--text-dark);
}

.composer-actions {
    display: flex;
    gap: 1rem;
    margin-top: 1.5rem;
}

.composer-actions .btn {
    flex: 1;
}
```

## Testing Strategy

### Manual Testing

1. **Basic Flow**
   - Open member info card
   - Click "SMS+" button
   - Verify redirect to composer with member name displayed
   - Select template from dropdown
   - Verify template loads into text area
   - Click "Expand Variables"
   - Verify variables are expanded correctly
   - Click "Send SMS"
   - Verify SMS app opens with message

2. **Custom Variables**
   - Select "Event Invitation" template
   - Verify "Event Name", "Date", "Time" input fields appear
   - Enter values
   - Click "Expand Variables"
   - Verify custom values are substituted

3. **Smart Variables**
   - Member with blue flag → verify formal name in expanded message
   - Member without blue flag → verify casual name in expanded message
   - Verify {random:casual_greeting} picks different greetings

4. **Edge Cases**
   - Member with no phone → verify "Send SMS" button is disabled
   - Empty template → verify no error
   - Missing custom variable → verify graceful handling
   - Very long message → verify character count updates correctly

### Integration Testing

1. **End-to-End**
   - Complete workflow from member card to SMS send
   - Verify Tasker receives message correctly
   - Verify message format is correct

2. **Multiple Members**
   - Send to member with blue flag
   - Send to member without blue flag
   - Verify different names used appropriately

## Implementation Checklist

- [ ] Add backend routes to `app.py`
  - [ ] `/sms-composer` (GET)
  - [ ] `/api/expand-template` (POST)
  - [ ] `/api/queue-sms` (POST)
- [ ] Create `templates/sms_composer.html`
- [ ] Create `static/js/sms_composer.js`
- [ ] Update `templates/base.html` (SMS button label)
- [ ] Update `static/js/member_modal.js` (`sendTextMessage()` function)
- [ ] Add `adhoc:` section to `data/message_templates.yaml`
- [ ] Add CSS styles to `static/css/style.css`
- [ ] Test complete workflow
  - [ ] Basic template selection and expansion
  - [ ] Custom variables
  - [ ] Smart variables (flags, random, etc.)
  - [ ] SMS sending
  - [ ] Edge cases

## Dependencies

This plan depends on **Smart Template Expansion** being implemented first:
- `utils/template_expander.py` must exist
- `models.py` MessageTemplates must have `expand_smart()` method
- Templates must support `{var|flag?transform:transform}` syntax
- Templates must support `{random:list}` syntax

## Future Enhancements (Not in This Plan)

- Template search/filtering
- Save custom messages as new templates
- Message history/recently sent
- Quick-send favorites
- Bulk messaging to multiple members
