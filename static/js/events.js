/**
 * Events Page JavaScript
 * Handles date filtering and quick filter buttons
 */

/**
 * Initialize the events page
 */
function initEventsPage() {
    // Get URL params
    const urlParams = new URLSearchParams(window.location.search);
    const fromDate = urlParams.get('from');
    const toDate = urlParams.get('to');

    // Set date inputs if present in URL
    if (fromDate) {
        document.getElementById('dateFrom').value = fromDate;
    } else {
        // Default to today
        document.getElementById('dateFrom').value = formatDate(new Date());
    }

    if (toDate) {
        document.getElementById('dateTo').value = toDate;
    } else {
        // Default to 30 days from now
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(thirtyDaysLater.getDate() + 30);
        document.getElementById('dateTo').value = formatDate(thirtyDaysLater);
    }

    // Restore scroll position if returning from another page
    const savedScrollPos = sessionStorage.getItem('eventsScrollPos');
    if (savedScrollPos) {
        window.scrollTo(0, parseInt(savedScrollPos));
        sessionStorage.removeItem('eventsScrollPos');
    }

    setupEventListeners();
}

/**
 * Save scroll position before navigating away
 */
function saveScrollPosition() {
    sessionStorage.setItem('eventsScrollPos', window.scrollY.toString());
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Apply filter button
    document.getElementById('applyFilterBtn').addEventListener('click', applyDateFilter);

    // Quick filter buttons
    document.querySelectorAll('.quick-filters button').forEach(button => {
        button.addEventListener('click', function() {
            const range = this.dataset.range;
            applyQuickFilter(range);
        });
    });

    // Allow Enter key on date inputs
    document.getElementById('dateFrom').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') applyDateFilter();
    });
    document.getElementById('dateTo').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') applyDateFilter();
    });
}

/**
 * Apply custom date filter
 */
function applyDateFilter() {
    const fromDate = document.getElementById('dateFrom').value;
    const toDate = document.getElementById('dateTo').value;

    if (!fromDate || !toDate) {
        alert('Please select both from and to dates');
        return;
    }

    // Redirect with query params
    window.location.href = `/events?from=${fromDate}&to=${toDate}`;
}

/**
 * Apply quick filter preset
 */
function applyQuickFilter(range) {
    const today = new Date();
    let fromDate, toDate;

    switch (range) {
        case 'today':
            fromDate = formatDate(today);
            toDate = formatDate(today);
            break;
        case 'upcoming':
            fromDate = formatDate(today);
            toDate = formatDate(addDays(today, 30));
            break;
        case 'past7':
            fromDate = formatDate(addDays(today, -7));
            toDate = formatDate(today);
            break;
        case 'past30':
            fromDate = formatDate(addDays(today, -30));
            toDate = formatDate(today);
            break;
        case 'all':
            // Set a very wide range (1 year ago to 1 year from now)
            fromDate = formatDate(addDays(today, -365));
            toDate = formatDate(addDays(today, 365));
            break;
        default:
            return;
    }

    // Redirect with query params
    window.location.href = `/events?from=${fromDate}&to=${toDate}`;
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
 * Add days to a date
 */
function addDays(date, days) {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
}

// Force reload when navigating back to this page (prevents stale cached data)
window.addEventListener('pageshow', function(event) {
    if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
        // Page was loaded from cache (back/forward button)
        window.location.reload();
    }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initEventsPage);
