/**
 * MLS3 Appointment Completion Tracking
 * Handles completion link clicks from calendar events
 */

function doGet(e) {
  try {
    // Check if we have parameters (this will be undefined when running directly)
    if (!e || !e.parameter) {
      return HtmlService.createHtmlOutput(`
        <html>
          <body>
            <h2>Error: Script must be called via Web App URL</h2>
            <p>This script is designed to be called from completion links in calendar events.</p>
            <p>To test, use the Web App URL with parameters like:</p>
            <code>?calendar_id=CALENDAR_ID&event_id=EVENT_ID&status=Completed</code>
            <p>Or run the <code>testDirectWrite()</code> function to test sheet writing.</p>
          </body>
        </html>
      `);
    }

    const params = e.parameter;
    const calendarId = params.calendar_id;
    const eventId = params.event_id;
    const status = params.status || 'Completed';

    // Validate required parameters
    if (!calendarId || !eventId) {
      return ContentService.createTextOutput('Error: Missing calendar_id or event_id')
        .setMimeType(ContentService.MimeType.TEXT);
    }

    // Record completion
    recordCompletion(calendarId, eventId, status);

    // Return success page
    return HtmlService.createHtmlOutput(`
      <!DOCTYPE html>
      <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            body {
              font-family: Arial, sans-serif;
              max-width: 600px;
              margin: 50px auto;
              padding: 20px;
              text-align: center;
            }
            .success {
              color: #28a745;
              font-size: 24px;
              margin-bottom: 20px;
            }
            .details {
              background: #f8f9fa;
              padding: 20px;
              border-radius: 8px;
              margin: 20px 0;
            }
          </style>
        </head>
        <body>
          <div class="success">✓ Recorded Successfully</div>
          <div class="details">
            <p><strong>Calendar ID:</strong> ${calendarId}</p>
            <p><strong>Event ID:</strong> ${eventId}</p>
            <p><strong>Status:</strong> ${status}</p>
            <p><strong>Time:</strong> ${new Date().toLocaleString()}</p>
          </div>
          <p>You can close this window now.</p>
          <p style="margin-top: 40px; color: #666; font-size: 12px;">
            Sheet: ${SpreadsheetApp.getActiveSpreadsheet().getName()}
          </p>
        </body>
      </html>
    `);
  } catch (error) {
    // Return error page
    return HtmlService.createHtmlOutput(`
      <!DOCTYPE html>
      <html>
        <body style="font-family: Arial; padding: 20px; max-width: 600px; margin: 0 auto;">
          <h2 style="color: #dc3545;">Error Recording Completion</h2>
          <p><strong>Error:</strong> ${error.message}</p>
          <p>Please check:</p>
          <ul>
            <li>Sheet "Completions" exists in this spreadsheet</li>
            <li>Script has permission to write to sheet</li>
          </ul>
        </body>
      </html>
    `);
  }
}

function recordCompletion(calendarId, eventId, status) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Completions');

  if (!sheet) {
    throw new Error('Sheet "Completions" not found. Please create a sheet tab named "Completions".');
  }

  // Append new row - minimal data only
  // Clerk can generate detailed reports later by fetching calendar events
  sheet.appendRow([
    new Date(),
    calendarId,
    eventId,
    status
  ]);

  Logger.log(`Recorded completion: ${calendarId} / ${eventId} - ${status}`);
}

/**
 * Test function - Run this to verify script can write to sheet
 * This bypasses the web app and directly writes to the sheet
 */
function testDirectWrite() {
  try {
    Logger.log('Testing direct sheet write...');

    // Check if sheet exists
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    Logger.log(`Spreadsheet: ${ss.getName()}`);

    const sheet = ss.getSheetByName('Completions');
    if (!sheet) {
      Logger.log('ERROR: Sheet "Completions" not found!');
      Logger.log('Available sheets: ' + ss.getSheets().map(s => s.getName()).join(', '));
      return;
    }

    Logger.log(`Sheet "Completions" found`);

    // Write test row with fake calendar/event IDs
    recordCompletion('test-calendar-id@example.com', 'test-event-' + Date.now(), 'Test-Completed');

    Logger.log('✓ Test completed successfully - check the Completions sheet!');

  } catch (error) {
    Logger.log('ERROR: ' + error.message);
    Logger.log('Stack: ' + error.stack);
  }
}

/**
 * Initialize sheet with headers if needed
 * Run this once to set up the Completions sheet
 */
function initializeSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Completions');

  if (!sheet) {
    Logger.log('Creating Completions sheet...');
    sheet = ss.insertSheet('Completions');
  }

  // Check if headers exist
  const headers = sheet.getRange(1, 1, 1, 4).getValues()[0];
  if (headers[0] !== 'Timestamp') {
    Logger.log('Adding headers...');
    sheet.getRange(1, 1, 1, 4).setValues([
      ['Timestamp', 'Calendar ID', 'Event ID', 'Status']
    ]);
    sheet.getRange(1, 1, 1, 4).setFontWeight('bold');
    Logger.log('✓ Headers added');
  } else {
    Logger.log('✓ Headers already exist');
  }

  Logger.log('✓ Sheet initialized successfully');
}
