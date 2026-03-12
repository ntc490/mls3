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
 * Note: memberId parameter is passed via data-member-id attribute from the button
 * Handles parent routing for minors
 */
async function openSMS(phone, memberId) {
    if (!memberId) {
        // Fallback to direct phone if no member ID (shouldn't happen)
        if (!phone) {
            alert('No phone number on file for this member');
            return;
        }
        const smsUrl = `sms:${phone}`;
        window.location.href = smsUrl;
        return;
    }

    try {
        // Get phone number(s) via API (handles parent routing for minors)
        const response = await fetch(`/api/members/${memberId}/sms-direct`, {
            method: 'POST'
        });

        const result = await response.json();

        if (!response.ok) {
            alert(result.error || 'Failed to send SMS');
            return;
        }

        // Open SMS app with blank message
        const smsUrl = `sms:${result.phone}`;
        window.location.href = smsUrl;

    } catch (error) {
        console.error('Error opening SMS:', error);
        alert('Failed to open SMS');
    }
}

/**
 * Send reminder SMS for prayer assignment
 * Note: Backend handles routing to parents if member is a minor
 */
async function openReminderSMS(assignmentId, phone, date, prayerType) {
    try {
        // Send reminder via API (which handles SMS and parent routing)
        const response = await fetch(`/api/assignments/${assignmentId}/remind`, {
            method: 'POST'
        });

        const result = await response.json();

        if (!response.ok) {
            // Show specific error message from backend
            alert(result.error || 'Failed to send reminder');
            return;
        }

    } catch (error) {
        console.error('Error sending reminder:', error);
        alert('Failed to send reminder');
    }
}

/**
 * Send reminder SMS for appointment
 * Note: Backend handles routing to parents if member is a minor
 */
async function openAppointmentReminderSMS(appointmentId, phone) {
    try {
        // Send reminder via API (which handles SMS and parent routing)
        const response = await fetch(`/api/appointments/${appointmentId}/remind`, {
            method: 'POST'
        });

        const result = await response.json();

        if (!response.ok) {
            // Show specific error message from backend
            alert(result.error || 'Failed to send reminder');
            return;
        }

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
 * Setup long-press detection for Reminder buttons
 */
function setupLongPressReminder() {
    const reminderButtons = document.querySelectorAll('.reminder-btn');

    reminderButtons.forEach(button => {
        let pressTimer;
        let isLongPress = false;

        // Mouse events (desktop)
        button.addEventListener('mousedown', (e) => {
            isLongPress = false;
            pressTimer = setTimeout(() => {
                isLongPress = true;
                button.style.opacity = '0.7';
                // Long press: open SMS app with blank message
                const memberId = button.dataset.memberId;
                const phone = button.dataset.phone;
                openSMS(phone, memberId);
            }, 500);
        });

        button.addEventListener('mouseup', (e) => {
            clearTimeout(pressTimer);
            button.style.opacity = '';
            if (!isLongPress) {
                // Normal click: send reminder
                if (button.dataset.assignmentId) {
                    // Prayer reminder
                    openReminderSMS(
                        button.dataset.assignmentId,
                        button.dataset.phone,
                        button.dataset.date,
                        button.dataset.prayerType
                    );
                } else if (button.dataset.appointmentId) {
                    // Appointment reminder
                    openAppointmentReminderSMS(
                        button.dataset.appointmentId,
                        button.dataset.phone
                    );
                }
            }
        });

        button.addEventListener('mouseleave', (e) => {
            clearTimeout(pressTimer);
            button.style.opacity = '';
        });

        // Touch events (mobile)
        button.addEventListener('touchstart', (e) => {
            e.preventDefault();
            isLongPress = false;
            pressTimer = setTimeout(() => {
                isLongPress = true;
                button.style.opacity = '0.7';
                const memberId = button.dataset.memberId;
                const phone = button.dataset.phone;
                openSMS(phone, memberId);
            }, 500);
        });

        button.addEventListener('touchend', (e) => {
            e.preventDefault();
            clearTimeout(pressTimer);
            button.style.opacity = '';
            if (!isLongPress) {
                // Normal click: send reminder
                if (button.dataset.assignmentId) {
                    openReminderSMS(
                        button.dataset.assignmentId,
                        button.dataset.phone,
                        button.dataset.date,
                        button.dataset.prayerType
                    );
                } else if (button.dataset.appointmentId) {
                    openAppointmentReminderSMS(
                        button.dataset.appointmentId,
                        button.dataset.phone
                    );
                }
            }
        });

        button.addEventListener('touchcancel', (e) => {
            clearTimeout(pressTimer);
            button.style.opacity = '';
        });
    });
}

/**
 * Setup Complete button click handlers
 */
function setupCompleteButtons() {
    const completeButtons = document.querySelectorAll('.complete-btn');

    completeButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            const type = button.dataset.type;

            // Show confirmation dialog
            const confirmed = confirm('Mark this event as complete?');
            if (!confirmed) {
                return;
            }

            try {
                let response;
                if (type === 'prayer') {
                    const assignmentId = button.dataset.assignmentId;
                    response = await fetch(`/api/assignments/${assignmentId}/state`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ state: 'Completed' })
                    });
                } else if (type === 'appointment') {
                    const appointmentId = button.dataset.appointmentId;
                    response = await fetch(`/api/appointments/${appointmentId}/state`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ state: 'Completed' })
                    });
                }

                if (!response.ok) {
                    const result = await response.json();
                    alert(result.error || 'Failed to mark as complete');
                    return;
                }

                // Reload page to show updated state
                window.location.reload();

            } catch (error) {
                console.error('Error marking complete:', error);
                alert('Failed to mark as complete');
            }
        });
    });
}

// Restore scroll position on page load
document.addEventListener('DOMContentLoaded', () => {
    restoreScrollPosition();
    setupLongPressReminder();
    setupCompleteButtons();
});
