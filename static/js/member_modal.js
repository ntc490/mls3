/**
 * Member Info Modal JavaScript
 * Handles opening/closing modal and managing member data
 */

let currentMemberId = null;
let currentMemberPhone = null;
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
        document.getElementById('modalMemberName').textContent = member.name;

        // Display age with indicator for minors
        if (member.age !== null && member.age !== undefined) {
            const ageText = member.age < 18 ? `${member.age} (minor)` : member.age.toString();
            document.getElementById('modalAge').textContent = ageText;
        } else {
            document.getElementById('modalAge').textContent = 'Unknown';
        }

        document.getElementById('modalGender').textContent = member.gender === 'M' ? 'Male' : 'Female';
        document.getElementById('modalBirthday').textContent = member.birthday || 'Not specified';
        document.getElementById('modalPhone').textContent = member.phone || 'Not specified';

        // Update skip until display
        updateSkipUntilDisplay(member.skip_until);

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
 * Send text message to member
 */
function sendTextMessage() {
    if (!currentMemberPhone) {
        alert('No phone number on file for this member');
        return;
    }

    // Open SMS app using Android intent
    const smsUrl = `sms:${currentMemberPhone}`;
    window.location.href = smsUrl;
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

    // Send text button
    const sendTextBtn = document.getElementById('sendTextBtn');
    if (sendTextBtn) {
        sendTextBtn.addEventListener('click', sendTextMessage);
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

    // Close skip dialog on outside click
    const skipDialog = document.getElementById('skipDialogModal');
    if (skipDialog) {
        skipDialog.addEventListener('click', (e) => {
            if (e.target === skipDialog) {
                closeSkipDialog();
            }
        });
    }
});
