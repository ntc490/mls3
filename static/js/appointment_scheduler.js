/**
 * Appointment Scheduler JavaScript
 * Handles appointment scheduling form logic
 */

let appointmentTypes = [];
let selectedConductor = null;
let memberId = null;
let appointmentId = null;
let isEditMode = false;

/**
 * Get browser's current timezone
 */
function getBrowserTimezone() {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/**
 * Initialize the appointment scheduler page
 */
async function initAppointmentScheduler() {
    // Get params from URL
    const urlParams = new URLSearchParams(window.location.search);
    memberId = urlParams.get('member_id');
    appointmentId = urlParams.get('appointment_id');

    // Determine mode
    isEditMode = !!appointmentId;

    // Check if we came from events page (via referrer)
    if (document.referrer && document.referrer.includes('/events')) {
        document.getElementById('backToEventsBtn').style.display = 'inline-block';
    }

    // Set up member autocomplete
    setupMemberAutocomplete();

    // Load appointment types
    await loadAppointmentTypes();

    if (isEditMode) {
        // Edit mode: Load existing appointment
        document.getElementById('pageTitle').textContent = 'Edit Appointment';
        document.getElementById('deleteBtn').style.display = 'inline-block';
        await loadAppointmentForEdit(appointmentId);
    } else {
        // Create mode: Set defaults
        document.getElementById('pageTitle').textContent = 'Schedule Appointment';

        // Pre-select member if provided
        if (memberId) {
            await loadMemberById(memberId);
        }

        // Set default date to next Sunday
        const nextSunday = getNextSunday();
        document.getElementById('appointmentDate').value = nextSunday;

        // Set default time to 11:00 AM
        document.getElementById('appointmentTime').value = '11:00';

        // Load appointments for the default Sunday
        await loadAppointmentsForDate(nextSunday);
    }

    // Set up event listeners
    setupEventListeners();
}

/**
 * Get next Sunday date in YYYY-MM-DD format
 */
function getNextSunday() {
    const today = new Date();
    const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, etc.

    // If today is Sunday, check the time
    if (dayOfWeek === 0) {
        const hour = today.getHours();
        // If it's before noon, use today; otherwise use next Sunday
        if (hour < 12) {
            return formatDate(today);
        }
    }

    // Calculate days until next Sunday
    const daysUntilSunday = (7 - dayOfWeek) % 7 || 7;
    const nextSunday = new Date(today);
    nextSunday.setDate(today.getDate() + daysUntilSunday);

    return formatDate(nextSunday);
}

/**
 * Format date as YYYY-MM-DD
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Set up member autocomplete
 */
function setupMemberAutocomplete() {
    const searchInput = document.getElementById('memberSearch');
    const resultsDiv = document.getElementById('memberResults');
    const hiddenInput = document.getElementById('selectedMemberId');
    const clearBtn = document.getElementById('clearMemberBtn');
    let searchTimeout;

    // Search as user types
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();

        // Show/hide clear button
        clearBtn.style.display = query.length > 0 ? 'block' : 'none';

        // Clear timeout
        clearTimeout(searchTimeout);

        if (query.length < 2) {
            resultsDiv.classList.remove('show');
            return;
        }

        // Debounce search
        searchTimeout = setTimeout(async () => {
            await searchMembers(query);
        }, 300);
    });

    // Clear selection if user modifies the text
    searchInput.addEventListener('input', function() {
        if (hiddenInput.value) {
            // Only clear if the text doesn't match the selected member
            hiddenInput.value = '';
        }
    });

    // Clear button click
    clearBtn.addEventListener('click', function() {
        searchInput.value = '';
        hiddenInput.value = '';
        clearBtn.style.display = 'none';
        document.getElementById('memberInfoBtn').style.display = 'none';
        resultsDiv.classList.remove('show');
        searchInput.focus();

        // Validate form to update button states
        validateForm();
    });

    // Close results when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !resultsDiv.contains(e.target)) {
            resultsDiv.classList.remove('show');
        }
    });

    // Show all members when focusing empty field
    searchInput.addEventListener('focus', async function() {
        if (this.value.trim().length === 0) {
            await searchMembers('');
        }
    });
}

/**
 * Search members via API
 */
async function searchMembers(query) {
    const resultsDiv = document.getElementById('memberResults');

    try {
        const url = query ? `/api/members/search?q=${encodeURIComponent(query)}` : '/api/members/search';
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Failed to search members');
        }

        const members = await response.json();
        displayMemberResults(members);

    } catch (error) {
        console.error('Error searching members:', error);
        resultsDiv.innerHTML = '<div class="no-results">Error searching members</div>';
        resultsDiv.classList.add('show');
    }
}

/**
 * Display member search results
 */
function displayMemberResults(members) {
    const resultsDiv = document.getElementById('memberResults');

    if (members.length === 0) {
        resultsDiv.innerHTML = '<div class="no-results">No members found</div>';
        resultsDiv.classList.add('show');
        return;
    }

    let html = '';
    members.forEach(member => {
        const details = [];
        if (member.age) details.push(`Age ${member.age}`);
        if (member.gender) details.push(member.gender === 'M' ? 'Male' : 'Female');

        html += `
            <div class="autocomplete-item" data-id="${member.id}" data-name="${member.name}">
                <div class="autocomplete-item-name">${member.name}</div>
                ${details.length > 0 ? `<div class="autocomplete-item-details">${details.join(' • ')}</div>` : ''}
            </div>
        `;
    });

    resultsDiv.innerHTML = html;
    resultsDiv.classList.add('show');

    // Add click handlers
    resultsDiv.querySelectorAll('.autocomplete-item').forEach(item => {
        item.addEventListener('click', function() {
            selectMember(this.dataset.id, this.dataset.name);
        });
    });
}

/**
 * Select a member from autocomplete
 */
function selectMember(id, name) {
    document.getElementById('memberSearch').value = name;
    document.getElementById('selectedMemberId').value = id;
    document.getElementById('clearMemberBtn').style.display = 'block';
    document.getElementById('memberInfoBtn').style.display = 'inline-block';
    document.getElementById('memberResults').classList.remove('show');

    // Update memberId variable
    memberId = id;

    // Validate form to update button states
    validateForm();
}

/**
 * Load member by ID and populate search field
 */
async function loadMemberById(id) {
    console.log('loadMemberById called with id:', id);
    try {
        const response = await fetch(`/api/members/${id}`);
        if (!response.ok) {
            throw new Error('Failed to load member');
        }

        const member = await response.json();
        console.log('Member loaded:', member);

        document.getElementById('memberSearch').value = member.name;
        document.getElementById('selectedMemberId').value = id;
        document.getElementById('clearMemberBtn').style.display = 'block';
        document.getElementById('memberInfoBtn').style.display = 'inline-block';

        console.log('Member field populated:', document.getElementById('memberSearch').value);

        // Update the global memberId variable
        memberId = id;

        // Validate form to update button states
        validateForm();

    } catch (error) {
        console.error('Error loading member:', error);
    }
}

/**
 * Load existing appointment for editing
 */
async function loadAppointmentForEdit(apptId) {
    try {
        const response = await fetch(`/api/appointments/${apptId}`);
        if (!response.ok) {
            throw new Error('Failed to load appointment');
        }

        const appt = await response.json();

        // Set member name in search field (read-only in edit mode)
        document.getElementById('memberSearch').value = appt.member_name;
        document.getElementById('selectedMemberId').value = appt.member_id;
        document.getElementById('clearMemberBtn').style.display = 'none';
        document.getElementById('memberInfoBtn').style.display = 'inline-block';

        // Make member field read-only in edit mode
        const memberSearch = document.getElementById('memberSearch');
        memberSearch.disabled = true;
        memberSearch.style.backgroundColor = '#f5f5f5';
        memberSearch.style.cursor = 'not-allowed';

        // Populate form fields
        document.getElementById('appointmentType').value = appt.appointment_type;
        document.getElementById('appointmentDate').value = appt.date;
        document.getElementById('appointmentTime').value = appt.time;
        document.getElementById('duration').value = appt.duration_minutes;

        // Set conductor
        selectConductor(appt.conductor);

        // Update button visibility based on state
        updateButtonsForState(appt.state);

        // Show "New Appointment" button in edit mode (except for completed)
        if (appt.state !== 'Completed') {
            document.getElementById('newApptBtn').style.display = 'inline-block';
        }

        // Make form read-only if completed
        if (appt.state === 'Completed') {
            makeFormReadOnly();
        }

        // Load appointments for this date
        await loadAppointmentsForDate(appt.date);

        // Update member ID
        memberId = appt.member_id;

    } catch (error) {
        console.error('Error loading appointment:', error);
        alert('Failed to load appointment');
    }
}

/**
 * Make form read-only (for completed appointments)
 */
function makeFormReadOnly() {
    // Disable member search
    document.getElementById('memberSearch').disabled = true;
    document.getElementById('clearMemberBtn').style.display = 'none';

    // Disable all form inputs
    document.getElementById('appointmentType').disabled = true;
    document.getElementById('appointmentDate').disabled = true;
    document.getElementById('appointmentTime').disabled = true;
    document.getElementById('duration').disabled = true;

    // Disable conductor buttons
    document.getElementById('conductorBishop').disabled = true;
    document.getElementById('conductorCounselor').disabled = true;

    // Disable suggest time button
    document.getElementById('suggestTimeBtn').disabled = true;

    // Add visual indication that form is read-only
    document.getElementById('pageTitle').textContent = 'View Completed Appointment';
}

/**
 * Load appointment types from API
 */
async function loadAppointmentTypes() {
    try {
        const response = await fetch('/api/appointment-types');
        if (!response.ok) {
            throw new Error('Failed to load appointment types');
        }

        const data = await response.json();
        appointmentTypes = data.appointment_types;

        // Populate dropdown
        const select = document.getElementById('appointmentType');
        appointmentTypes.forEach(type => {
            const option = document.createElement('option');
            option.value = type.name;
            option.textContent = type.name;
            option.dataset.duration = type.default_duration;
            option.dataset.conductor = type.default_conductor;
            select.appendChild(option);
        });

    } catch (error) {
        console.error('Error loading appointment types:', error);
        alert('Failed to load appointment types');
    }
}

/**
 * Update button visibility based on appointment state
 */
function updateButtonsForState(state) {
    const saveBtn = document.getElementById('saveBtn');
    const sendInviteBtn = document.getElementById('sendInviteBtn');
    const acceptedBtn = document.getElementById('acceptedBtn');
    const reminderBtn = document.getElementById('reminderBtn');
    const completeBtn = document.getElementById('completeBtn');
    const deleteBtn = document.getElementById('deleteBtn');

    // Hide all state-specific buttons first
    saveBtn.style.display = 'none';
    sendInviteBtn.style.display = 'none';
    acceptedBtn.style.display = 'none';
    reminderBtn.style.display = 'none';
    completeBtn.style.display = 'none';

    // Show delete button for existing appointments
    deleteBtn.style.display = 'inline-block';

    // Show appropriate buttons based on state
    switch (state) {
        case 'Draft':
            saveBtn.style.display = 'inline-block';
            sendInviteBtn.style.display = 'inline-block';
            acceptedBtn.style.display = 'inline-block';
            break;
        case 'Invited':
            acceptedBtn.style.display = 'inline-block';
            reminderBtn.style.display = 'inline-block';
            break;
        case 'Accepted':
            reminderBtn.style.display = 'inline-block';
            completeBtn.style.display = 'inline-block';
            break;
        case 'Reminded':
            reminderBtn.style.display = 'inline-block';
            completeBtn.style.display = 'inline-block';
            break;
        case 'Completed':
        case 'Cancelled':
            // No action buttons for completed/cancelled
            break;
    }
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Appointment type change - auto-fill duration and conductor
    const typeSelect = document.getElementById('appointmentType');
    typeSelect.addEventListener('change', onAppointmentTypeChange);

    // Date change - reload appointments for that date
    const dateInput = document.getElementById('appointmentDate');
    dateInput.addEventListener('change', onDateChange);

    // Conductor buttons
    document.getElementById('conductorBishop').addEventListener('click', () => selectConductor('Bishop'));
    document.getElementById('conductorCounselor').addEventListener('click', () => selectConductor('Counselor'));

    // Suggest time button
    document.getElementById('suggestTimeBtn').addEventListener('click', suggestTime);

    // Member info button
    document.getElementById('memberInfoBtn').addEventListener('click', function() {
        const selectedMemberId = document.getElementById('selectedMemberId').value;
        if (selectedMemberId) {
            openMemberModal(selectedMemberId);
        }
    });

    // Navigation buttons
    document.getElementById('backToEventsBtn').addEventListener('click', () => {
        window.location.href = '/events';
    });

    // Action buttons
    document.getElementById('saveBtn').addEventListener('click', saveDraft);
    document.getElementById('sendInviteBtn').addEventListener('click', sendInvite);
    document.getElementById('acceptedBtn').addEventListener('click', markAccepted);
    document.getElementById('reminderBtn').addEventListener('click', sendReminder);
    document.getElementById('completeBtn').addEventListener('click', markComplete);
    document.getElementById('newApptBtn').addEventListener('click', resetToNewAppointment);
    document.getElementById('deleteBtn').addEventListener('click', deleteAppointment);

    // Form validation - enable/disable save and invite buttons
    document.getElementById('memberSearch').addEventListener('input', validateForm);
    document.getElementById('appointmentType').addEventListener('change', validateForm);
    document.getElementById('appointmentDate').addEventListener('change', validateForm);
    document.getElementById('appointmentTime').addEventListener('change', validateForm);
    document.getElementById('duration').addEventListener('input', validateForm);

    // Toggle appointments list
    document.getElementById('toggleAppointmentsBtn').addEventListener('click', toggleAppointmentsList);

    // Initial validation
    validateForm();
}

/**
 * Validate form and enable/disable save and invite buttons
 */
function validateForm() {
    const selectedMemberId = document.getElementById('selectedMemberId').value;
    const appointmentType = document.getElementById('appointmentType').value;
    const date = document.getElementById('appointmentDate').value;
    const time = document.getElementById('appointmentTime').value;
    const duration = document.getElementById('duration').value;

    // Check if all required fields are filled
    const isValid = selectedMemberId &&
                    appointmentType &&
                    date &&
                    time &&
                    duration &&
                    parseInt(duration) >= 5 &&
                    selectedConductor;

    // Enable/disable buttons
    const saveBtn = document.getElementById('saveBtn');
    const sendInviteBtn = document.getElementById('sendInviteBtn');

    if (saveBtn) {
        saveBtn.disabled = !isValid;
    }
    if (sendInviteBtn) {
        sendInviteBtn.disabled = !isValid;
    }
}

/**
 * Toggle appointments list visibility
 */
function toggleAppointmentsList() {
    const appointmentsList = document.getElementById('appointmentsList');
    const toggleBtn = document.getElementById('toggleAppointmentsBtn');

    appointmentsList.classList.toggle('collapsed');
    toggleBtn.classList.toggle('collapsed');
}

/**
 * Handle date change - load appointments for selected date
 */
async function onDateChange() {
    const date = document.getElementById('appointmentDate').value;
    if (!date) return;

    await loadAppointmentsForDate(date);
}

/**
 * Load appointments for a specific date
 */
async function loadAppointmentsForDate(date) {
    try {
        const response = await fetch(`/api/appointments?date=${date}`);
        if (!response.ok) {
            throw new Error('Failed to load appointments');
        }

        const data = await response.json();
        displayAppointments(data.appointments, date);

    } catch (error) {
        console.error('Error loading appointments:', error);
    }
}

/**
 * Display appointments in the sidebar
 */
function displayAppointments(appointments, date) {
    const displayDate = new Date(date + 'T00:00:00');
    const formattedDate = displayDate.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    });

    document.getElementById('selectedDateDisplay').textContent = formattedDate;

    const listContainer = document.getElementById('appointmentsList');

    if (appointments.length === 0) {
        listContainer.innerHTML = '<p class="text-muted">No appointments scheduled</p>';
        return;
    }

    // Group by conductor
    const bishopAppts = appointments.filter(a => a.conductor === 'Bishop');
    const counselorAppts = appointments.filter(a => a.conductor === 'Counselor');

    let html = '';

    if (bishopAppts.length > 0) {
        html += '<div class="conductor-group"><h4>Bishop</h4>';
        bishopAppts.sort((a, b) => a.time.localeCompare(b.time));
        bishopAppts.forEach(appt => {
            html += `
                <div class="appt-item">
                    <span class="appt-time">${appt.time}</span>
                    <span class="appt-details">${appt.member_name} - ${appt.appointment_type}</span>
                    <span class="appt-duration">${appt.duration_minutes}m</span>
                </div>
            `;
        });
        html += '</div>';
    }

    if (counselorAppts.length > 0) {
        html += '<div class="conductor-group"><h4>Counselor</h4>';
        counselorAppts.sort((a, b) => a.time.localeCompare(b.time));
        counselorAppts.forEach(appt => {
            html += `
                <div class="appt-item">
                    <span class="appt-time">${appt.time}</span>
                    <span class="appt-details">${appt.member_name} - ${appt.appointment_type}</span>
                    <span class="appt-duration">${appt.duration_minutes}m</span>
                </div>
            `;
        });
        html += '</div>';
    }

    listContainer.innerHTML = html;
}

/**
 * Suggest next available time
 */
async function suggestTime() {
    const date = document.getElementById('appointmentDate').value;
    const duration = document.getElementById('duration').value;

    if (!date) {
        alert('Please select a date first');
        return;
    }

    if (!duration || duration < 5) {
        alert('Please select appointment type and duration first');
        return;
    }

    if (!selectedConductor) {
        alert('Please select a conductor first');
        return;
    }

    try {
        const response = await fetch(
            `/api/appointments/suggest-time?date=${date}&conductor=${selectedConductor}&duration=${duration}`
        );

        if (!response.ok) {
            throw new Error('Failed to get time suggestion');
        }

        const data = await response.json();

        if (data.available) {
            document.getElementById('appointmentTime').value = data.suggested_time;
        } else {
            alert(data.message || 'No available time slots found');
        }

    } catch (error) {
        console.error('Error suggesting time:', error);
        alert('Failed to suggest time');
    }
}

/**
 * Handle appointment type change
 */
function onAppointmentTypeChange(event) {
    // Get the select element - either from event or directly
    const selectElement = event ? event.target : document.getElementById('appointmentType');
    const selectedOption = selectElement.selectedOptions[0];

    if (!selectedOption || !selectedOption.value) {
        return;
    }

    const defaultDuration = selectedOption.dataset.duration;
    const defaultConductor = selectedOption.dataset.conductor;

    // Set duration
    document.getElementById('duration').value = defaultDuration;

    // Pre-select conductor (but allow override)
    selectConductor(defaultConductor);
}

/**
 * Select conductor
 */
function selectConductor(conductor) {
    selectedConductor = conductor;

    // Update button states
    const bishopBtn = document.getElementById('conductorBishop');
    const counselorBtn = document.getElementById('conductorCounselor');

    if (conductor === 'Bishop') {
        bishopBtn.classList.add('active');
        counselorBtn.classList.remove('active');
    } else {
        bishopBtn.classList.remove('active');
        counselorBtn.classList.add('active');
    }

    // Validate form to update button states
    validateForm();
}

/**
 * Save as draft (create tentative appointment)
 */
async function saveDraft() {
    await saveAppointment('Draft');
}

/**
 * Send invitation (create or update appointment)
 */
async function sendInvite() {
    await saveAppointment('Invited');
}

/**
 * Mark appointment as accepted
 */
async function markAccepted() {
    if (!appointmentId) return;

    try {
        const response = await fetch(`/api/appointments/${appointmentId}/state`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'Accepted'
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update appointment');
        }

        window.location.reload();

    } catch (error) {
        console.error('Error updating appointment:', error);
        alert('Failed to update appointment: ' + error.message);
    }
}

/**
 * Send reminder
 */
async function sendReminder() {
    if (!appointmentId) return;

    try {
        const response = await fetch(`/api/appointments/${appointmentId}/remind`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to send reminder');
        }

        window.location.reload();

    } catch (error) {
        console.error('Error sending reminder:', error);
        alert('Failed to send reminder: ' + error.message);
    }
}

/**
 * Mark appointment as complete
 */
async function markComplete() {
    if (!appointmentId) return;

    try {
        const response = await fetch(`/api/appointments/${appointmentId}/state`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: 'Completed'
            })
        });

        if (!response.ok) {
            throw new Error('Failed to complete appointment');
        }

        window.location.reload();

    } catch (error) {
        console.error('Error completing appointment:', error);
        alert('Failed to complete appointment: ' + error.message);
    }
}

/**
 * Save appointment (helper function for create/update)
 */
async function saveAppointment(initialState) {
    // Get selected member ID from hidden input
    const selectedMemberId = document.getElementById('selectedMemberId').value;

    // Validate form
    if (!selectedMemberId) {
        alert('Please select a member');
        return;
    }

    const appointmentType = document.getElementById('appointmentType').value;
    const date = document.getElementById('appointmentDate').value;
    const time = document.getElementById('appointmentTime').value;
    const duration = document.getElementById('duration').value;

    if (!appointmentType) {
        alert('Please select an appointment type');
        return;
    }

    if (!date) {
        alert('Please select a date');
        return;
    }

    if (!time) {
        alert('Please select a time');
        return;
    }

    if (!duration || duration < 5) {
        alert('Please enter a valid duration (at least 5 minutes)');
        return;
    }

    if (!selectedConductor) {
        alert('Please select a conductor');
        return;
    }

    try {
        if (isEditMode) {
            // Update existing appointment
            const response = await fetch(`/api/appointments/${appointmentId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    appointment_type: appointmentType,
                    date: date,
                    time: time,
                    duration_minutes: parseInt(duration),
                    conductor: selectedConductor,
                    timezone: getBrowserTimezone()
                })
            });

            if (!response.ok) {
                throw new Error('Failed to update appointment');
            }

            // Handle state-specific actions
            if (initialState === 'Invited') {
                const inviteResponse = await fetch(`/api/appointments/${appointmentId}/invite`, {
                    method: 'POST'
                });

                if (!inviteResponse.ok) {
                    const errorData = await inviteResponse.json();
                    alert(errorData.error || 'Failed to send invite');
                }
            }

            // For updates, just reload the current page
            window.location.reload();

        } else {
            // Create new appointment
            const response = await fetch('/api/appointments/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    member_id: parseInt(selectedMemberId),
                    appointment_type: appointmentType,
                    date: date,
                    time: time,
                    duration_minutes: parseInt(duration),
                    conductor: selectedConductor,
                    timezone: getBrowserTimezone()
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create appointment');
            }

            const result = await response.json();
            const newAppointmentId = result.appointment_id;

            // If sending invite, call the invite endpoint
            if (initialState === 'Invited') {
                const inviteResponse = await fetch(`/api/appointments/${newAppointmentId}/invite`, {
                    method: 'POST'
                });

                if (!inviteResponse.ok) {
                    const errorData = await inviteResponse.json();
                    alert(errorData.error || 'Failed to send invite');
                }
            }

            // Redirect to edit mode for the new appointment
            window.location.href = `/appointment-scheduler?appointment_id=${newAppointmentId}`;
        }

    } catch (error) {
        console.error('Error saving appointment:', error);
        alert('Failed to save appointment: ' + error.message);
    }
}

/**
 * Delete appointment
 */
async function deleteAppointment() {
    if (!confirm('Are you sure you want to delete this appointment? This cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/api/appointments/${appointmentId}/delete`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to delete appointment');
        }

        window.location.href = '/';

    } catch (error) {
        console.error('Error deleting appointment:', error);
        alert('Failed to delete appointment: ' + error.message);
    }
}

/**
 * Reset form to create a new appointment
 * Keeps the current member and appointment type, but resets other fields to defaults
 */
function resetToNewAppointment() {
    // Get current member and appointment type
    const currentMemberId = document.getElementById('selectedMemberId').value;
    const currentMemberName = document.getElementById('memberSearch').value;
    const currentAppointmentType = document.getElementById('appointmentType').value;

    // Switch to create mode
    isEditMode = false;
    appointmentId = null;

    // Update page title
    document.getElementById('pageTitle').textContent = 'Schedule Appointment';

    // Re-enable member field
    const memberSearch = document.getElementById('memberSearch');
    memberSearch.disabled = false;
    memberSearch.style.backgroundColor = '';
    memberSearch.style.cursor = '';

    // Keep member and appointment type
    document.getElementById('selectedMemberId').value = currentMemberId;
    document.getElementById('memberSearch').value = currentMemberName;
    document.getElementById('appointmentType').value = currentAppointmentType;

    // Show clear button for member
    if (currentMemberId) {
        document.getElementById('clearMemberBtn').style.display = 'block';
    }

    // Reset date to next Sunday
    const nextSunday = getNextSunday();
    document.getElementById('appointmentDate').value = nextSunday;

    // Reset time to 11:00 AM
    document.getElementById('appointmentTime').value = '11:00';

    // Reset duration and conductor to defaults (will be auto-filled by appointment type if applicable)
    if (currentAppointmentType) {
        // Trigger appointment type change to auto-fill duration and conductor
        onAppointmentTypeChange();
    } else {
        document.getElementById('duration').value = '';
        selectedConductor = null;
        document.getElementById('conductorBishop').classList.remove('active');
        document.getElementById('conductorCounselor').classList.remove('active');
    }

    // Reset button visibility
    document.getElementById('saveBtn').style.display = 'inline-block';
    document.getElementById('sendInviteBtn').style.display = 'inline-block';
    document.getElementById('acceptedBtn').style.display = 'none';
    document.getElementById('reminderBtn').style.display = 'none';
    document.getElementById('completeBtn').style.display = 'none';
    document.getElementById('newApptBtn').style.display = 'none';
    document.getElementById('deleteBtn').style.display = 'none';

    // Load appointments for the new date
    loadAppointmentsForDate(nextSunday);

    // Validate form
    validateForm();

    // Remove URL parameters
    const newUrl = window.location.pathname;
    window.history.pushState({}, '', newUrl);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initAppointmentScheduler);
