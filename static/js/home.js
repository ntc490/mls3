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

// Restore scroll position on page load
document.addEventListener('DOMContentLoaded', restoreScrollPosition);
