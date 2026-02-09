/**
 * Member Info Modal JavaScript
 * Handles opening/closing modal and managing member data
 */

let currentMemberId = null;
let currentMemberPhone = null;
let currentHouseholdId = null;
let targetDate = null; // Optional date for creating assignments
let memberDataDirty = false; // Track if member data has been modified

/**
 * Open the member info modal and load member data
 */
async function openMemberModal(memberId, date = null) {
    currentMemberId = memberId;
    memberDataDirty = false; // Reset dirty flag when opening modal

    // Use provided date, or check sessionStorage for prayer scheduler target date
    targetDate = date || sessionStorage.getItem('prayer_scheduler_target_date');

    // Close household modal if it's open
    const householdModal = document.getElementById('householdModal');
    if (householdModal && householdModal.style.display === 'flex') {
        householdModal.style.display = 'none';
    }

    // Show modal
    const modal = document.getElementById('memberInfoModal');
    modal.style.display = 'flex';

    // Load member data
    try {
        const response = await fetch(`/api/members/${memberId}`);
        if (!response.ok) {
            throw new Error('Failed to load member data');
        }

        const member = await response.json();

        // Populate modal with member data
        // Show AKA in header with actual first name in parentheses if AKA is set
        const headerText = member.aka && member.aka.trim()
            ? `${member.aka} ${member.last_name} (${member.first_name})`
            : member.name;
        document.getElementById('modalMemberName').textContent = headerText;

        document.getElementById('modalGender').textContent = member.gender === 'M' ? 'Male' : 'Female';

        // Combined birthday and age display
        let birthdayAgeText = member.birthday || 'Not specified';
        if (member.age !== null && member.age !== undefined && member.birthday) {
            const minorText = member.is_minor ? ', minor' : '';
            birthdayAgeText = `${member.birthday} (${member.age}${minorText})`;
        }
        document.getElementById('modalBirthdayAge').textContent = birthdayAgeText;

        // Show household link or single label under name
        const householdLink = document.getElementById('modalHouseholdLink');
        const singleLabel = document.getElementById('modalSingleLabel');
        if (member.household_id) {
            currentHouseholdId = member.household_id;
            householdLink.style.display = 'block';
            singleLabel.style.display = 'none';
        } else {
            currentHouseholdId = null;
            householdLink.style.display = 'none';
            singleLabel.style.display = 'block';
        }

        document.getElementById('modalPhone').textContent = member.phone || 'Not specified';

        // Update skip until display
        updateSkipUntilDisplay(member.skip_until);

        // Update AKA display
        updateAkaDisplay(member.aka);

        // Show notes only if they exist
        const notesRow = document.getElementById('modalNotesRow');
        if (member.notes && member.notes.trim()) {
            document.getElementById('modalNotes').textContent = member.notes;
            notesRow.style.display = 'flex';
        } else {
            notesRow.style.display = 'none';
        }

        // Set toggle states
        document.getElementById('toggleActive').checked = member.active;
        document.getElementById('toggleDontAsk').checked = member.dont_ask_prayer;

        // Store phone for SMS
        currentMemberPhone = member.phone;

        // Update flag selector
        updateFlagSelector(member.flag);

        // Load prayer history
        loadPrayerHistory(member.prayer_history);

        // Load event history
        loadEventHistory(member.event_history);

    } catch (error) {
        console.error('Error loading member:', error);
        alert('Failed to load member information');
        closeMemberModal();
    }
}

/**
 * Close the member info modal
 */
function closeMemberModal() {
    const modal = document.getElementById('memberInfoModal');
    modal.style.display = 'none';
    currentMemberId = null;
    currentMemberPhone = null;
    currentHouseholdId = null;

    // Reload the members list if data was modified and we're on the members page
    if (memberDataDirty && window.location.pathname === '/members') {
        window.location.reload();
    }
    memberDataDirty = false;
}

/**
 * Load and display prayer history
 */
function loadPrayerHistory(history) {
    const listDiv = document.getElementById('prayerHistoryList');

    if (!history || history.length === 0) {
        listDiv.innerHTML = '<p class="text-muted">No prayer history yet</p>';
        return;
    }

    // Build HTML for prayer history
    let html = '<ul class="prayer-history-items">';
    history.forEach(prayer => {
        html += `
            <li class="prayer-history-item">
                <span class="prayer-date">${prayer.formatted_date}</span>
            </li>
        `;
    });
    html += '</ul>';

    listDiv.innerHTML = html;
}

/**
 * Load and display event history (prayers and appointments)
 */
function loadEventHistory(history) {
    const listDiv = document.getElementById('eventHistoryList');

    if (!history || history.length === 0) {
        listDiv.innerHTML = '<p class="text-muted">No history yet</p>';
        return;
    }

    // Build HTML for event history
    let html = '<ul class="event-history-items">';
    history.forEach(event => {
        const stateClass = `state-${event.state.toLowerCase()}`;

        if (event.type === 'prayer') {
            html += `
                <li class="event-history-item event-prayer clickable" onclick="navigateToPrayer('${event.date}')">
                    <span class="event-icon">🙏</span>
                    <span class="event-details">
                        <span class="event-date">${event.formatted_date}</span>
                        <span class="event-desc">${event.prayer_type}</span>
                    </span>
                    <span class="event-state ${stateClass}">${event.state}</span>
                </li>
            `;
        } else if (event.type === 'appointment') {
            html += `
                <li class="event-history-item event-appointment clickable" onclick="navigateToAppointment(${event.appointment_id})">
                    <span class="event-icon">📅</span>
                    <span class="event-details">
                        <span class="event-date">${event.formatted_date} ${event.time}</span>
                        <span class="event-desc">${event.appointment_type} (${event.conductor})</span>
                    </span>
                    <span class="event-state ${stateClass}">${event.state}</span>
                </li>
            `;
        }
    });
    html += '</ul>';

    listDiv.innerHTML = html;
}

/**
 * Navigate to prayer scheduler with specific date
 */
function navigateToPrayer(date) {
    window.location.href = `/prayer-scheduler?date=${date}`;
}

/**
 * Navigate to appointment scheduler with specific appointment loaded
 */
function navigateToAppointment(appointmentId) {
    window.location.href = `/appointment-scheduler?appointment_id=${appointmentId}`;
}

/**
 * Toggle member active status
 */
async function toggleActiveStatus() {
    if (!currentMemberId) return;

    try {
        const response = await fetch(`/api/members/${currentMemberId}/toggle-active`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        if (!response.ok) {
            throw new Error('Failed to update active status');
        }

        const result = await response.json();

        // Update checkbox to match server state
        document.getElementById('toggleActive').checked = result.active;

        // Mark data as dirty
        memberDataDirty = true;

        // Show feedback
        showToast(result.active ? 'Member activated' : 'Member deactivated');

    } catch (error) {
        console.error('Error toggling active status:', error);
        alert('Failed to update active status');
        // Revert checkbox
        document.getElementById('toggleActive').checked = !document.getElementById('toggleActive').checked;
    }
}

/**
 * Toggle member dont_ask_prayer flag
 */
async function toggleDontAsk() {
    if (!currentMemberId) return;

    try {
        const response = await fetch(`/api/members/${currentMemberId}/toggle-dont-ask`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        if (!response.ok) {
            throw new Error('Failed to update dont ask flag');
        }

        const result = await response.json();

        // Update checkbox to match server state
        document.getElementById('toggleDontAsk').checked = result.dont_ask_prayer;

        // Mark data as dirty
        memberDataDirty = true;

        // Show feedback
        showToast(result.dont_ask_prayer ? 'Member marked as "don\'t ask"' : 'Member can be asked for prayers');

    } catch (error) {
        console.error('Error toggling dont ask:', error);
        alert('Failed to update dont ask flag');
        // Revert checkbox
        document.getElementById('toggleDontAsk').checked = !document.getElementById('toggleDontAsk').checked;
    }
}

// Track current flags state (array of colors)
let currentMemberFlags = [];

/**
 * Update flag selector to show current flags (can be multiple)
 */
function updateFlagSelector(flagString) {
    // Parse flags from comma-separated string
    currentMemberFlags = flagString ? flagString.split(',').map(f => f.trim()) : [];

    // Remove active class from all buttons
    const buttons = document.querySelectorAll('.flag-selector-btn');
    buttons.forEach(btn => btn.classList.remove('active'));

    // Add active class to each active flag button
    currentMemberFlags.forEach(flagColor => {
        const activeButton = document.querySelector(`.flag-selector-btn[data-flag="${flagColor}"]`);
        if (activeButton) {
            activeButton.classList.add('active');
        }
    });
}

/**
 * Toggle a flag on/off (can have multiple flags)
 */
async function setMemberFlag(flag) {
    if (!currentMemberId) return;

    try {
        const response = await fetch(`/api/members/${currentMemberId}/toggle-flag`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ flag: flag })
        });

        if (!response.ok) {
            throw new Error('Failed to toggle flag');
        }

        const result = await response.json();
        updateFlagSelector(result.flag);

        // Mark data as dirty
        memberDataDirty = true;

        // Show which flags are now active
        const flagsList = result.flags_list || [];
        if (flagsList.length === 0) {
            showToast('All flags removed');
        } else {
            const flagNames = flagsList.map(f => f.charAt(0).toUpperCase() + f.slice(1)).join(', ');
            showToast(`Flags: ${flagNames}`);
        }

    } catch (error) {
        console.error('Error toggling flag:', error);
        alert('Failed to toggle flag');
    }
}

/**
 * Update Skip Until display in the main member modal
 */
function updateSkipUntilDisplay(skip_until) {
    const skipUntilEl = document.getElementById('modalSkipUntil');
    if (skip_until) {
        const skipDate = new Date(skip_until);
        const today = new Date();
        today.setHours(0, 0, 0, 0); // Reset time for comparison

        if (skipDate > today) {
            skipUntilEl.textContent = skipDate.toLocaleDateString();
            skipUntilEl.classList.add('active');
        } else {
            // Skip date has passed
            skipUntilEl.textContent = 'Not set';
            skipUntilEl.classList.remove('active');
        }
    } else {
        skipUntilEl.textContent = 'Not set';
        skipUntilEl.classList.remove('active');
    }
}

/**
 * Update AKA display in the main member modal
 */
function updateAkaDisplay(aka) {
    const akaEl = document.getElementById('modalAka');
    if (aka && aka.trim()) {
        akaEl.textContent = aka;
        akaEl.classList.add('active');
    } else {
        akaEl.textContent = 'Not set';
        akaEl.classList.remove('active');
    }
}

/**
 * Open the AKA dialog
 */
function openAkaDialog() {
    if (!currentMemberId) return;

    const dialog = document.getElementById('akaDialogModal');
    dialog.style.display = 'flex';

    // Pre-populate the input with current AKA if set
    const currentAka = document.getElementById('modalAka').textContent;
    const akaInput = document.getElementById('akaInput');
    if (currentAka && currentAka !== 'Not set') {
        akaInput.value = currentAka;
    } else {
        akaInput.value = '';
    }
}

/**
 * Close the AKA dialog
 */
function closeAkaDialog() {
    const dialog = document.getElementById('akaDialogModal');
    dialog.style.display = 'none';

    // Clear the input
    const akaInput = document.getElementById('akaInput');
    if (akaInput) {
        akaInput.value = '';
    }
}

/**
 * Set AKA for the member
 */
async function setAka() {
    if (!currentMemberId) return;

    const akaInput = document.getElementById('akaInput');
    const akaValue = akaInput.value.trim();

    try {
        const response = await fetch(`/api/members/${currentMemberId}/aka`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ aka: akaValue })
        });

        if (!response.ok) {
            throw new Error('Failed to set AKA');
        }

        const result = await response.json();
        updateAkaDisplay(result.aka);
        memberDataDirty = true;
        showToast(akaValue ? `AKA set to "${akaValue}"` : 'AKA cleared');
        closeAkaDialog();

    } catch (error) {
        console.error('Error setting AKA:', error);
        alert('Failed to set AKA');
    }
}

/**
 * Clear AKA for the member
 */
async function clearAka() {
    if (!currentMemberId) return;

    try {
        const response = await fetch(`/api/members/${currentMemberId}/aka`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ aka: '' })
        });

        if (!response.ok) {
            throw new Error('Failed to clear AKA');
        }

        const result = await response.json();
        updateAkaDisplay(result.aka);
        memberDataDirty = true;
        showToast('AKA cleared');
        closeAkaDialog();

    } catch (error) {
        console.error('Error clearing AKA:', error);
        alert('Failed to clear AKA');
    }
}

/**
 * Open the skip dialog
 */
function openSkipDialog() {
    if (!currentMemberId) return;

    const dialog = document.getElementById('skipDialogModal');
    dialog.style.display = 'flex';
}

/**
 * Close the skip dialog
 */
function closeSkipDialog() {
    const dialog = document.getElementById('skipDialogModal');
    dialog.style.display = 'none';

    // Clear the date picker
    const dateInput = document.getElementById('skipDatePicker');
    if (dateInput) {
        dateInput.value = '';
    }
}

/**
 * Set skip_until date from skip dialog (months from now)
 */
async function setSkipUntilFromDialog(months) {
    if (!currentMemberId) return;

    const today = new Date();
    const skipDate = new Date(today.setMonth(today.getMonth() + months));
    const skipDateStr = skipDate.toISOString().split('T')[0]; // YYYY-MM-DD

    try {
        const response = await fetch(`/api/members/${currentMemberId}/skip-until`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ skip_until: skipDateStr })
        });

        if (!response.ok) {
            throw new Error('Failed to set skip date');
        }

        const result = await response.json();
        updateSkipUntilDisplay(result.skip_until);
        memberDataDirty = true;
        showToast(`Member skipped until ${skipDate.toLocaleDateString()}`);
        closeSkipDialog();

    } catch (error) {
        console.error('Error setting skip date:', error);
        alert('Failed to set skip date');
    }
}

/**
 * Set custom skip date from date picker
 */
async function setCustomSkipDate() {
    if (!currentMemberId) return;

    const dateInput = document.getElementById('skipDatePicker');
    const skipDateStr = dateInput.value;

    if (!skipDateStr) {
        alert('Please select a date');
        return;
    }

    try {
        const response = await fetch(`/api/members/${currentMemberId}/skip-until`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ skip_until: skipDateStr })
        });

        if (!response.ok) {
            throw new Error('Failed to set skip date');
        }

        const result = await response.json();
        updateSkipUntilDisplay(result.skip_until);
        memberDataDirty = true;
        const skipDate = new Date(skipDateStr);
        showToast(`Member skipped until ${skipDate.toLocaleDateString()}`);
        closeSkipDialog();

    } catch (error) {
        console.error('Error setting skip date:', error);
        alert('Failed to set skip date');
    }
}

/**
 * Clear skip_until from skip dialog
 */
async function clearSkipFromDialog() {
    if (!currentMemberId) return;

    try {
        const response = await fetch(`/api/members/${currentMemberId}/skip-until`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ skip_until: null })
        });

        if (!response.ok) {
            throw new Error('Failed to clear skip date');
        }

        const result = await response.json();
        updateSkipUntilDisplay(result.skip_until);
        memberDataDirty = true;
        showToast('Skip cleared - member back in rotation');
        closeSkipDialog();

    } catch (error) {
        console.error('Error clearing skip date:', error);
        alert('Failed to clear skip date');
    }
}

/**
 * Create prayer assignment and go to scheduler
 */
async function createPrayerAssignment() {
    if (!currentMemberId) return;

    try {
        // Build request body with optional date
        const requestBody = {};
        if (targetDate) {
            requestBody.date = targetDate;
        }

        const response = await fetch(`/api/members/${currentMemberId}/create-assignment`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestBody)
        });

        const result = await response.json();

        if (!response.ok) {
            // Show specific error message from server
            alert(result.error || 'Failed to create prayer assignment');
            return;
        }

        // Success - redirect to prayer scheduler with the date if available
        if (targetDate) {
            window.location.href = `/prayer-scheduler?date=${targetDate}`;
        } else {
            window.location.href = '/prayer-scheduler';
        }

    } catch (error) {
        console.error('Error creating assignment:', error);
        alert('Failed to create prayer assignment');
    }
}

/**
 * Send text message to member (direct SMS)
 * Handles parent routing for minors
 */
async function sendTextMessage() {
    if (!currentMemberId) return;

    try {
        // Get phone number(s) via API (handles parent routing for minors)
        const response = await fetch(`/api/members/${currentMemberId}/sms-direct`, {
            method: 'POST'
        });

        const result = await response.json();

        if (!response.ok) {
            alert(result.error || 'Failed to send SMS');
            return;
        }

        // Open SMS app using Android intent
        const smsUrl = `sms:${result.phone}`;
        window.location.href = smsUrl;

    } catch (error) {
        console.error('Error opening SMS:', error);
        alert('Failed to open SMS');
    }
}

/**
 * Open SMS composer (template-based messaging)
 */
function openSmsComposer() {
    if (!currentMemberId) return;

    // Redirect to SMS composer
    window.location.href = `/sms-composer?member_id=${currentMemberId}`;
}

/**
 * Open appointment scheduler for the current member
 */
function openAppointmentScheduler() {
    if (!currentMemberId) {
        alert('No member selected');
        return;
    }

    // Navigate to appointment scheduler page with member ID
    window.location.href = `/appointment-scheduler?member_id=${currentMemberId}`;
}

/**
 * Show a toast notification (simple implementation)
 */
function showToast(message) {
    // For now, just use console.log
    // Could be enhanced with a proper toast UI later
    console.log('Toast:', message);

    // Simple visual feedback
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 2000);
}

/**
 * Open household modal
 */
async function openHouseholdModal() {
    if (!currentHouseholdId) {
        alert('No household information available');
        return;
    }

    try {
        // Fetch full household data
        const response = await fetch(`/api/households/${currentHouseholdId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch household data');
        }

        const household = await response.json();

        // Show household modal
        const modal = document.getElementById('householdModal');
        modal.style.display = 'flex';

        // Populate household details
        document.getElementById('householdModalTitle').textContent = household.name;
        document.getElementById('householdAddress').textContent = household.address || 'Not specified';
        document.getElementById('householdPhone').textContent = household.phone || 'Not specified';
        document.getElementById('householdEmail').textContent = household.email || 'Not specified';

        // Display household members
        displayHouseholdMembers(household.members);

    } catch (error) {
        console.error('Error opening household modal:', error);
        alert('Failed to load household information');
    }
}

/**
 * Close household modal
 */
function closeHouseholdModal() {
    const modal = document.getElementById('householdModal');
    modal.style.display = 'none';
}

/**
 * Display household members list
 */
function displayHouseholdMembers(members) {
    const listDiv = document.getElementById('householdMembersList');

    if (!members || members.length === 0) {
        listDiv.innerHTML = '<p class="text-muted">No members found</p>';
        return;
    }

    // Build HTML for members list
    let html = '<ul class="household-members-items">';
    members.forEach(member => {
        const ageText = member.age ? ` (${member.age})` : '';
        const minorBadge = member.is_minor ? ' <span class="minor-badge">minor</span>' : '';
        const phoneText = member.phone ? member.phone : '';

        html += `
            <li class="household-member-item" onclick="openMemberModal(${member.member_id}); event.stopPropagation();">
                <span class="member-name">${member.full_name}${ageText}${minorBadge}</span>
                <span class="member-phone">${phoneText}</span>
            </li>
        `;
    });
    html += '</ul>';

    listDiv.innerHTML = html;
}

// Set up event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Toggle listeners
    const toggleActive = document.getElementById('toggleActive');
    if (toggleActive) {
        toggleActive.addEventListener('change', toggleActiveStatus);
    }

    const toggleDontAskEl = document.getElementById('toggleDontAsk');
    if (toggleDontAskEl) {
        toggleDontAskEl.addEventListener('change', toggleDontAsk);
    }

    // Send text button with long-press detection
    // Tap: direct SMS | Long-press: SMS composer
    const sendTextBtn = document.getElementById('sendTextBtn');
    if (sendTextBtn) {
        let pressTimer;
        let isLongPress = false;

        sendTextBtn.addEventListener('mousedown', (e) => {
            isLongPress = false;
            pressTimer = setTimeout(() => {
                isLongPress = true;
                // Visual feedback for long press
                sendTextBtn.style.opacity = '0.7';
                // Trigger SMS composer on long press
                openSmsComposer();
            }, 500); // 500ms for long press
        });

        sendTextBtn.addEventListener('mouseup', (e) => {
            clearTimeout(pressTimer);
            sendTextBtn.style.opacity = '';
            if (!isLongPress) {
                // Normal click - direct SMS
                sendTextMessage();
            }
        });

        sendTextBtn.addEventListener('mouseleave', (e) => {
            clearTimeout(pressTimer);
            sendTextBtn.style.opacity = '';
        });

        // Touch events for mobile
        sendTextBtn.addEventListener('touchstart', (e) => {
            e.preventDefault(); // Prevent mouse events from firing
            isLongPress = false;
            pressTimer = setTimeout(() => {
                isLongPress = true;
                sendTextBtn.style.opacity = '0.7';
                openSmsComposer();
            }, 500);
        });

        sendTextBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            clearTimeout(pressTimer);
            sendTextBtn.style.opacity = '';
            if (!isLongPress) {
                sendTextMessage();
            }
        });

        sendTextBtn.addEventListener('touchcancel', (e) => {
            clearTimeout(pressTimer);
            sendTextBtn.style.opacity = '';
        });
    }

    // Appointment button
    const apptBtn = document.getElementById('apptBtn');
    if (apptBtn) {
        apptBtn.addEventListener('click', openAppointmentScheduler);
    }

    // Pray button - goes directly to prayer scheduler
    const prayBtn = document.getElementById('prayBtn');
    if (prayBtn) {
        prayBtn.addEventListener('click', createPrayerAssignment);
    }

    // Close member modal on outside click
    const modal = document.getElementById('memberInfoModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeMemberModal();
            }
        });
    }

    // Close AKA dialog on outside click
    const akaDialog = document.getElementById('akaDialogModal');
    if (akaDialog) {
        akaDialog.addEventListener('click', (e) => {
            if (e.target === akaDialog) {
                closeAkaDialog();
            }
        });
    }

    // Close skip dialog on outside click
    const skipDialog = document.getElementById('skipDialogModal');
    if (skipDialog) {
        skipDialog.addEventListener('click', (e) => {
            if (e.target === skipDialog) {
                closeSkipDialog();
            }
        });
    }

    // Close household modal on outside click
    const householdModal = document.getElementById('householdModal');
    if (householdModal) {
        householdModal.addEventListener('click', (e) => {
            if (e.target === householdModal) {
                closeHouseholdModal();
            }
        });
    }
});
