/**
 * Import page: choose the two church PDF reports, review what would change,
 * confirm, and restore a backup if needed.
 *
 * The review is deliberately compact - headline counts plus only the entries
 * that need a decision. Scrolling hundreds of unchanged people on a phone helps
 * nobody.
 */
(function () {
    'use strict';

    const fileInput = document.getElementById('reportFiles');
    const filePickerLabel = document.getElementById('filePickerLabel');
    const fileList = document.getElementById('fileList');
    const previewBtn = document.getElementById('previewBtn');
    const importBtn = document.getElementById('importBtn');
    const cancelBtn = document.getElementById('cancelBtn');

    const stepChoose = document.getElementById('step-choose');
    const stepPreview = document.getElementById('step-preview');
    const stepDone = document.getElementById('step-done');
    const previewBody = document.getElementById('previewBody');
    const doneBody = document.getElementById('doneBody');

    const ACTION_LABELS = {
        add: 'New',
        update: 'Updated',
        rename: 'Name corrected',
        deactivate: 'No longer listed',
    };

    const FIELD_LABELS = {
        first_name: 'first name',
        last_name: 'last name',
        gender: 'gender',
        birthday: 'birthday',
        phone: 'phone',
        household_id: 'household',
        household_role: 'role in household',
        active: 'active',
        name: 'name',
        address: 'address',
    };

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    }

    // Shared by the preview, the import result and the integrity check, so it
    // lives outside the upload-only wiring below.
    function problemList(messages, kind) {
        if (!messages || !messages.length) {
            return '';
        }
        const title = kind === 'error' ? 'Needs attention' : 'Worth a look';
        return `
            <div class="import-${kind}">
                <strong>${title}</strong>
                <ul>${messages.map(m => `<li>${escapeHtml(m)}</li>`).join('')}</ul>
            </div>
        `;
    }

    function tally(counts) {
        const rows = [
            ['add', 'new'],
            ['update', 'updated'],
            ['rename', 'name corrected'],
            ['deactivate', 'no longer listed'],
            ['unchanged', 'unchanged'],
        ].filter(([key]) => counts[key]);

        if (!rows.length) {
            return '';
        }
        return '<ul class="import-tally">' + rows.map(function ([key, label]) {
            const sign = key === 'deactivate' ? '−' : (key === 'add' ? '+' : '~');
            const cls = key === 'unchanged' ? 'text-muted' : '';
            return `<li class="${cls}"><span class="tally-count">${sign}${counts[key]}</span> ${label}</li>`;
        }).join('') + '</ul>';
    }

    /* ---------- confirmation dialog ---------- */

    function confirmAction(title, message, confirmLabel) {
        return new Promise(function (resolve) {
            const dialog = document.getElementById('confirmDialog');
            const yes = document.getElementById('confirmYes');
            const no = document.getElementById('confirmNo');

            document.getElementById('confirmTitle').textContent = title;
            document.getElementById('confirmMessage').textContent = message;
            yes.textContent = confirmLabel || 'Yes, do it';
            dialog.style.display = 'flex';

            function close(result) {
                dialog.style.display = 'none';
                yes.removeEventListener('click', onYes);
                no.removeEventListener('click', onNo);
                resolve(result);
            }
            function onYes() { close(true); }
            function onNo() { close(false); }

            yes.addEventListener('click', onYes);
            no.addEventListener('click', onNo);
        });
    }

    /* ---------- choosing files ---------- */

    // The recovery page reuses this file for the confirm dialog and the restore
    // buttons only, so the upload wiring is skipped when it is not on the page.
    const hasUploadUi = fileInput && previewBtn && importBtn && cancelBtn;

    if (hasUploadUi) {
    fileInput.addEventListener('change', function () {
        const files = Array.from(fileInput.files || []);
        fileList.innerHTML = files
            .map(f => `<li>${escapeHtml(f.name)}</li>`)
            .join('');

        if (files.length === 0) {
            filePickerLabel.textContent = 'Tap to choose PDFs';
        } else if (files.length === 1) {
            filePickerLabel.textContent = '1 file chosen - one more needed';
        } else {
            filePickerLabel.textContent = `${files.length} files chosen`;
        }

        previewBtn.disabled = files.length !== 2;
        stepPreview.hidden = true;
        stepDone.hidden = true;
    });

    function formData() {
        const data = new FormData();
        Array.from(fileInput.files || []).forEach(file => data.append('reports', file));
        return data;
    }

    /* ---------- preview ---------- */

    previewBtn.addEventListener('click', async function () {
        previewBtn.disabled = true;
        previewBtn.textContent = 'Reading reports...';
        try {
            const response = await fetch('/api/import/preview', {
                method: 'POST',
                body: formData(),
            });
            const data = await response.json();
            renderPreview(data);
        } catch (error) {
            renderPreview({ ok: false, errors: ['Could not read the reports: ' + error.message] });
        } finally {
            previewBtn.disabled = false;
            previewBtn.textContent = 'Check these reports';
        }
    });

    function renderPreview(data) {
        stepDone.hidden = true;
        stepPreview.hidden = false;

        if (!data.ok) {
            previewBody.innerHTML = problemList(data.errors, 'error');
            importBtn.hidden = true;
            stepPreview.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

        const counts = data.counts || {};
        const parts = [];

        parts.push(`
            <div class="import-summary">
                <strong>${counts.people || 0} people</strong> &middot;
                <strong>${counts.total_households || 0} households</strong>
                <div class="text-muted">
                    from a report printed ${escapeHtml(data.print_dates.member_list || 'unknown')}
                </div>
            </div>
        `);

        if (!data.changes_anything) {
            parts.push('<p class="import-nochange">Nothing would change &mdash; ' +
                'the database already matches these reports.</p>');
        }

        parts.push(tally(counts));

        ['add', 'rename', 'update', 'deactivate'].forEach(function (action) {
            const rows = (data.members || []).filter(m => m.action === action);
            if (rows.length) {
                parts.push(detailGroup(ACTION_LABELS[action], rows));
            }
        });

        if ((data.households || []).length) {
            parts.push(householdGroup(data.households));
        }

        if ((data.warnings || []).length) {
            parts.push(problemList(data.warnings, 'warning'));
        }

        previewBody.innerHTML = parts.join('');
        importBtn.hidden = !data.changes_anything;
        stepPreview.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function detailGroup(title, rows) {
        const items = rows.map(function (row) {
            const changes = Object.entries(row.fields || {})
                .filter(([field]) => field !== 'household_id')
                .map(function ([field, value]) {
                    const label = FIELD_LABELS[field] || field;
                    if (!value.old) {
                        return `${label} ${escapeHtml(value.new)}`;
                    }
                    return `${label} ${escapeHtml(value.old)} &rarr; ${escapeHtml(value.new)}`;
                });
            const detail = changes.length
                ? `<span class="text-muted">${changes.join(', ')}</span>`
                : '';
            const household = row.household
                ? `<span class="text-muted"> &middot; ${escapeHtml(row.household)}</span>`
                : '';
            return `<li><strong>${escapeHtml(row.name)}</strong>${household}<br>${detail}</li>`;
        }).join('');

        return `
            <details class="import-group">
                <summary>${escapeHtml(title)} (${rows.length})</summary>
                <ul class="import-detail">${items}</ul>
            </details>
        `;
    }

    function householdGroup(rows) {
        const items = rows.map(function (row) {
            const changes = Object.entries(row.fields || {}).map(function ([field, value]) {
                const label = FIELD_LABELS[field] || field;
                return `${label} changed`;
            });
            const detail = row.action === 'add'
                ? '<span class="text-muted">new household</span>'
                : `<span class="text-muted">${changes.join(', ')}</span>`;
            return `<li><strong>${escapeHtml(row.name)}</strong><br>${detail}</li>`;
        }).join('');

        return `
            <details class="import-group">
                <summary>Households changed (${rows.length})</summary>
                <ul class="import-detail">${items}</ul>
            </details>
        `;
    }

    /* ---------- commit ---------- */

    cancelBtn.addEventListener('click', function () {
        stepPreview.hidden = true;
        stepChoose.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    importBtn.addEventListener('click', async function () {
        const summary = previewBody.querySelector('.import-tally');
        const described = summary ? summary.textContent.replace(/\s+/g, ' ').trim() : '';

        const ok = await confirmAction(
            'Import these reports?',
            `This will change the database (${described}). A backup is saved first, ` +
            `so you can undo it.`,
            'Import'
        );
        if (!ok) {
            return;
        }

        importBtn.disabled = true;
        importBtn.textContent = 'Importing...';
        try {
            const response = await fetch('/api/import/commit', {
                method: 'POST',
                body: formData(),
            });
            const data = await response.json();
            renderDone(data);
        } catch (error) {
            renderDone({ ok: false, errors: ['The import failed: ' + error.message] });
        } finally {
            importBtn.disabled = false;
            importBtn.textContent = 'Import';
        }
    });

    function renderDone(data) {
        stepPreview.hidden = true;
        stepDone.hidden = false;

        if (!data.ok) {
            doneBody.innerHTML = problemList(data.errors, 'error');
            stepDone.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }

        const counts = data.counts || {};
        const parts = ['<p class="import-success">Imported.</p>', tally(counts)];

        if (data.backup) {
            parts.push(`
                <p>Backed up as <strong>${escapeHtml(data.backup.label)}</strong>
                before importing.</p>
                <button class="btn btn-secondary btn-restore"
                        data-timestamp="${escapeHtml(data.backup.timestamp)}"
                        data-label="${escapeHtml(data.backup.label)}">Undo this import</button>
            `);
        }
        if ((data.warnings || []).length) {
            parts.push(problemList(data.warnings, 'warning'));
        }

        // The integrity check runs automatically on what was just written, so
        // a problem shows up here rather than waiting to be stumbled over.
        const integrity = data.integrity || {};
        if ((integrity.errors || []).length) {
            parts.push(problemList(integrity.errors, 'error'));
        } else if ((integrity.warnings || []).length) {
            parts.push(problemList(integrity.warnings, 'warning'));
        } else {
            parts.push('<p class="text-muted">The data checks out.</p>');
        }

        parts.push('<p><a href="/members">See the members list</a></p>');

        doneBody.innerHTML = parts.join('');
        stepDone.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    }   /* end of upload wiring */

    /* ---------- integrity check ---------- */

    const checkBtn = document.getElementById('checkBtn');
    const checkBody = document.getElementById('checkBody');

    if (checkBtn && checkBody) {
        checkBtn.addEventListener('click', async function () {
            checkBtn.disabled = true;
            checkBtn.textContent = 'Checking...';
            try {
                const response = await fetch('/api/data/check');
                checkBody.innerHTML = renderCheck(await response.json());
            } catch (error) {
                checkBody.innerHTML = problemList(
                    ['Could not run the check: ' + error.message], 'error');
            } finally {
                checkBtn.disabled = false;
                checkBtn.textContent = 'Run a check';
            }
        });
    }

    function renderCheck(data) {
        const counts = data.counts || {};
        const rows = Object.entries(counts)
            .map(([key, value]) => `<li><span class="tally-count">${value}</span> ` +
                                   `${escapeHtml(key.replace(/_/g, ' '))}</li>`)
            .join('');
        const parts = rows ? [`<ul class="import-tally">${rows}</ul>`] : [];

        parts.push(problemList(data.errors, 'error'));
        parts.push(problemList(data.warnings, 'warning'));

        if (data.ok && !(data.warnings || []).length) {
            parts.push('<p class="import-success">Everything checks out.</p>');
        }
        return parts.join('');
    }

    /* ---------- restore ---------- */

    document.addEventListener('click', async function (event) {
        const button = event.target.closest('.btn-restore');
        if (!button) {
            return;
        }

        const label = button.dataset.label || 'this backup';
        const ok = await confirmAction(
            'Restore this backup?',
            `Members, households, prayer assignments and appointments will go back ` +
            `to how they were on ${label}. Anything changed since then will be lost. ` +
            `The current state is backed up first.`,
            'Restore'
        );
        if (!ok) {
            return;
        }

        button.disabled = true;
        button.textContent = 'Restoring...';
        try {
            const response = await fetch('/api/import/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timestamp: button.dataset.timestamp }),
            });
            const data = await response.json();
            if (data.ok) {
                window.location.reload();
            } else {
                alert(data.error || 'Could not restore that backup.');
                button.disabled = false;
                button.textContent = 'Restore';
            }
        } catch (error) {
            alert('Could not restore that backup: ' + error.message);
            button.disabled = false;
            button.textContent = 'Restore';
        }
    });
})();
