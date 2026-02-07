/**
 * Member Info Modal JavaScript
 * Handles opening/closing modal and managing member data
 */

let currentMemberId = null;
let currentMemberPhone = null;

/**
 * Open the member info modal and load member data
 */
async function openMemberModal(memberId) {
    currentMemberId = memberId;

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
        document.getElementById('modalRecommend').textContent = member.recommend_expiration || 'Not specified';

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
                <span class="prayer-type">${prayer.prayer_type}</span>
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

        // Show feedback
        showToast(result.dont_ask_prayer ? 'Member marked as "don\'t ask"' : 'Member can be asked for prayers');

    } catch (error) {
        console.error('Error toggling dont ask:', error);
        alert('Failed to update dont ask flag');
        // Revert checkbox
        document.getElementById('toggleDontAsk').checked = !document.getElementById('toggleDontAsk').checked;
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

    // Close modal on outside click
    const modal = document.getElementById('memberInfoModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeMemberModal();
            }
        });
    }
});
