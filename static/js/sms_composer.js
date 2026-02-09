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
        updateCharCount();
        return;
    }

    // Get template text
    const templateText = templates[templateName];
    if (!templateText) {
        console.error('Template not found:', templateName);
        return;
    }

    // Store original template for re-expansion
    originalTemplate = templateText;

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
