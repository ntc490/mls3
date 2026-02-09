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

    // Toggle date filters
    document.getElementById('toggleDateFiltersBtn').addEventListener('click', toggleDateFilters);

    // Search input (live filtering)
    document.getElementById('searchText').addEventListener('input', applySearchAndSort);

    // Sort order dropdown
    document.getElementById('sortOrder').addEventListener('change', applySearchAndSort);
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
        case 'active':
            // Active week: same calculation as homepage
            // Determine target Sunday
            let targetSunday;
            if (today.getDay() === 0) {
                // On Sunday (getDay() returns 0 for Sunday), show this Sunday
                targetSunday = today;
            } else {
                // Monday-Saturday, show next Sunday
                targetSunday = getNextSunday(today);
            }

            // Calculate Monday of the target week (6 days before Sunday)
            const weekStart = addDays(targetSunday, -6);

            // Only show events from today onwards (don't show past events from earlier in the week)
            const actualStart = today > weekStart ? today : weekStart;

            fromDate = formatDate(actualStart);
            toDate = formatDate(targetSunday);
            break;
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

/**
 * Get next Sunday from a given date
 */
function getNextSunday(fromDate) {
    const result = new Date(fromDate);
    const dayOfWeek = result.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday
    const daysUntilSunday = dayOfWeek === 0 ? 7 : 7 - dayOfWeek;
    result.setDate(result.getDate() + daysUntilSunday);
    return result;
}

// Force reload when navigating back to this page (prevents stale cached data)
window.addEventListener('pageshow', function(event) {
    if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
        // Page was loaded from cache (back/forward button)
        window.location.reload();
    }
});

/**
 * Toggle date filters section
 */
function toggleDateFilters() {
    const section = document.getElementById('dateFiltersSection');
    const icon = document.getElementById('toggleIcon');

    if (section.style.display === 'none') {
        section.style.display = 'block';
        icon.textContent = '▲';
    } else {
        section.style.display = 'none';
        icon.textContent = '▼';
    }
}

/**
 * Fuzzy match function - checks if all query terms appear in the text in any order
 */
function fuzzyMatch(text, query) {
    if (!query.trim()) return true;

    const textLower = text.toLowerCase();
    const queryTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0);

    // All query terms must appear in the text (in any order)
    return queryTerms.every(term => textLower.includes(term));
}

/**
 * Apply search and sort to events
 */
function applySearchAndSort() {
    const searchText = document.getElementById('searchText').value;
    const sortOrder = document.getElementById('sortOrder').value;

    // Get all date groups
    const dateGroups = Array.from(document.querySelectorAll('.calendar-date-group'));

    // Filter and show/hide items based on search
    dateGroups.forEach(group => {
        const items = Array.from(group.querySelectorAll('.calendar-item'));
        let visibleCount = 0;

        items.forEach(item => {
            // Get item text content (name and type)
            const itemText = item.querySelector('.calendar-item-text, .calendar-item-info')?.textContent || '';

            if (fuzzyMatch(itemText, searchText)) {
                item.style.display = '';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });

        // Hide date group if no visible items
        if (visibleCount === 0) {
            group.style.display = 'none';
        } else {
            group.style.display = '';
        }
    });

    // Sort date groups
    const container = document.getElementById('eventsContainer');
    const sortedGroups = dateGroups.sort((a, b) => {
        const dateA = a.querySelector('.calendar-date-header')?.dataset.date || a.querySelector('.calendar-date-header')?.textContent;
        const dateB = b.querySelector('.calendar-date-header')?.dataset.date || b.querySelector('.calendar-date-header')?.textContent;

        if (sortOrder === 'asc') {
            return dateA < dateB ? -1 : 1;
        } else {
            return dateA > dateB ? -1 : 1;
        }
    });

    // Re-append in sorted order
    sortedGroups.forEach(group => {
        container.appendChild(group);
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initEventsPage);
