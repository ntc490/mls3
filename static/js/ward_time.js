/**
 * The ward's clock, for pages that may be open on a phone in another timezone.
 *
 * The UI always works in ward time (WARD_TIMEZONE, set by base.html from
 * config.HOME_TIMEZONE). These helpers return plain Date objects whose local
 * fields - getFullYear(), getDate(), getDay(), getHours() - read as ward wall
 * time, so the usual date arithmetic and formatting on them stays in the ward.
 */

/**
 * Now, in ward wall time
 */
function wardNow() {
    const parts = {};
    new Intl.DateTimeFormat('en-US', {
        timeZone: window.WARD_TIMEZONE,
        year: 'numeric', month: 'numeric', day: 'numeric',
        hour: 'numeric', minute: 'numeric', second: 'numeric',
        hourCycle: 'h23'
    }).formatToParts(new Date()).forEach(p => { parts[p.type] = Number(p.value); });
    return new Date(parts.year, parts.month - 1, parts.day,
                    parts.hour, parts.minute, parts.second);
}

/**
 * Today in the ward, at midnight
 */
function wardToday() {
    const now = wardNow();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/**
 * A 'YYYY-MM-DD' date as midnight on that day. new Date('YYYY-MM-DD') would
 * be midnight UTC - the evening before, anywhere west of Greenwich.
 */
function parseDate(dateStr) {
    const [year, month, day] = dateStr.split('-').map(Number);
    return new Date(year, month - 1, day);
}

/**
 * A Date as 'YYYY-MM-DD', from its local fields
 */
function toDateString(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
