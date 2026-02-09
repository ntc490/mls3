/**
 * Home Page JavaScript
 * Handles SMS functions and page state management
 */

/**
 * Save scroll position before navigating away
 */
function saveScrollPosition() {
    sessionStorage.setItem('homeScrollPos', window.scrollY.toString());
}

/**
 * Restore scroll position when returning to homepage
 */
function restoreScrollPosition() {
    const savedScrollPos = sessionStorage.getItem('homeScrollPos');
    if (savedScrollPos) {
        window.scrollTo(0, parseInt(savedScrollPos));
        sessionStorage.removeItem('homeScrollPos');
    }
}

/**
 * Open SMS app with phone number
 */
function openSMS(phone) {
    if (!phone) {
        alert('No phone number on file for this member');
        return;
    }
    // Open SMS app using Android intent
    const smsUrl = `sms:${phone}`;
    window.location.href = smsUrl;
}

/**
 * Open SMS app with pre-filled reminder message for prayer assignment
 */
async function openReminderSMS(assignmentId, phone, date, prayerType) {
    if (!phone) {
        alert('No phone number on file for this member');
        return;
    }

    try {
        // Fetch the reminder message
        const response = await fetch(`/api/assignments/${assignmentId}/reminder-message`);

        if (!response.ok) {
            throw new Error('Failed to get reminder message');
        }

        const result = await response.json();

        // Open SMS app with pre-filled message
        const smsUrl = `sms:${phone}?body=${encodeURIComponent(result.message)}`;
        window.location.href = smsUrl;

    } catch (error) {
        console.error('Error opening reminder SMS:', error);
        alert('Failed to open reminder SMS');
    }
}

/**
 * Send reminder SMS for appointment
 */
async function openAppointmentReminderSMS(appointmentId, phone) {
    if (!phone) {
        alert('No phone number on file for this member');
        return;
    }

    try {
        // Send reminder via API (which handles SMS)
        const response = await fetch(`/api/appointments/${appointmentId}/remind`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to send reminder');
        }

        const result = await response.json();

    } catch (error) {
        console.error('Error sending reminder:', error);
        alert('Failed to send reminder');
    }
}

// Force reload when navigating back to this page (prevents stale cached data)
window.addEventListener('pageshow', function(event) {
    if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
        // Page was loaded from cache (back/forward button)
        window.location.reload();
    }
});

/**
 * Setup long-press detection for SMS buttons
 */
function setupLongPressSMS() {
    const smsButtons = document.querySelectorAll('.sms-btn');

    smsButtons.forEach(button => {
        let pressTimer;
        let isLongPress = false;

        // Mouse events (desktop)
        button.addEventListener('mousedown', (e) => {
            const phone = button.dataset.phone;
            const memberId = button.dataset.memberId;
            isLongPress = false;
            pressTimer = setTimeout(() => {
                isLongPress = true;
                button.style.opacity = '0.7';
                // Long press: open SMS composer
                window.location.href = `/sms-composer?member_id=${encodeURIComponent(memberId)}`;
            }, 500);
        });

        button.addEventListener('mouseup', (e) => {
            const phone = button.dataset.phone;
            clearTimeout(pressTimer);
            button.style.opacity = '';
            if (!isLongPress) {
                // Normal click: direct SMS
                openSMS(phone);
            }
        });

        button.addEventListener('mouseleave', (e) => {
            clearTimeout(pressTimer);
            button.style.opacity = '';
        });

        // Touch events (mobile)
        button.addEventListener('touchstart', (e) => {
            const phone = button.dataset.phone;
            const memberId = button.dataset.memberId;
            e.preventDefault();
            isLongPress = false;
            pressTimer = setTimeout(() => {
                isLongPress = true;
                button.style.opacity = '0.7';
                window.location.href = `/sms-composer?member_id=${encodeURIComponent(memberId)}`;
            }, 500);
        });

        button.addEventListener('touchend', (e) => {
            const phone = button.dataset.phone;
            e.preventDefault();
            clearTimeout(pressTimer);
            button.style.opacity = '';
            if (!isLongPress) {
                openSMS(phone);
            }
        });

        button.addEventListener('touchcancel', (e) => {
            clearTimeout(pressTimer);
            button.style.opacity = '';
        });
    });
}

// Restore scroll position on page load
document.addEventListener('DOMContentLoaded', () => {
    restoreScrollPosition();
    setupLongPressSMS();
});
