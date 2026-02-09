/**
 * SMS Composer JavaScript
 * Handles template selection, variable expansion, and SMS sending
 */

// Standard variables that don't need custom input
const STANDARD_VARS = [
    'name', 'first_name', 'last_name', 'member_name', 'full_name',
    'date', 'smart_date', 'time', 'conductor', 'prayer_type',
    'appointment_type', 'parent_greeting', 'child_name'
];

// Store the original template text for re-expansion
let originalTemplate = null;

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
        originalTemplate = null;
        window.currentTemplateName = null;
        updateCharCount();
        return;
    }

    // Get template text
    const templateText = templates[templateName];
    if (!templateText) {
        console.error('Template not found:', templateName);
        return;
    }

    // Store original template and name for re-expansion
    originalTemplate = templateText;
    window.currentTemplateName = templateName;

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
    // Use original template if available, otherwise use current text
    const templateText = originalTemplate || document.getElementById('messageText').value.trim();

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
                template_name: window.currentTemplateName,
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

        // Show which template was used (if different from selected)
        if (result.template_used && result.template_used !== window.currentTemplateName) {
            console.log(`Using parent template: ${result.template_used}`);
        }

    } catch (error) {
        console.error('Error expanding template:', error);
        alert('Failed to expand template: ' + error.message);
    }
}

/**
 * Send SMS
 * Handles parent routing for minors
 */
async function sendSMS() {
    const message = document.getElementById('messageText').value.trim();

    if (!message) {
        alert('Please enter a message');
        return;
    }

    try {
        // Get phone number(s) via API (handles parent routing for minors)
        const phoneResponse = await fetch(`/api/members/${memberId}/sms-direct`, {
            method: 'POST'
        });

        const phoneResult = await phoneResponse.json();

        if (!phoneResponse.ok) {
            alert(phoneResult.error || 'Failed to get phone number');
            return;
        }

        // Open SMS app with the message pre-filled
        const smsUrl = `sms:${phoneResult.phone}?body=${encodeURIComponent(message)}`;
        window.location.href = smsUrl;

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
