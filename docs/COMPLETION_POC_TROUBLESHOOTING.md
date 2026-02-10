# Completion Tracking POC - Troubleshooting

## Error: "Cannot read properties of undefined (reading 'parameter')"

**Cause**: You clicked "Run" in the Apps Script editor, which runs the function directly without parameters.

**Solution**: Don't run `doGet()` directly. Instead:

1. Run the **`testDirectWrite()`** function to test sheet writing:
   - In Apps Script editor, select `testDirectWrite` from dropdown
   - Click "Run"
   - Check "Completions" sheet for new test row
   - Check "View → Logs" for success message

2. Or test the web app URL in browser:
   ```
   YOUR_WEB_APP_URL?id=TEST-123&status=Completed
   ```

## Error: "Document doesn't exist" when clicking link

**Possible causes:**
1. Wrong URL format
2. Deployment not completed
3. Script needs re-deployment

**Solutions to try:**

### Solution 1: Verify Web App URL format
Your URL should look like:
```
https://script.google.com/macros/s/AKfycbw.../exec
```

NOT like:
```
https://script.google.com/.../dev    ❌ (dev mode)
https://docs.google.com/...          ❌ (doc link)
```

### Solution 2: Create NEW deployment

1. In Apps Script: **Deploy → Manage deployments**
2. Click **Archive** on old deployment
3. Click **+ Create deployment** (not "New deployment")
4. Select type: **Web app**
5. **New description**: "POC v2"
6. Execute as: **Me**
7. Who has access: **Anyone**
8. Click **Deploy**
9. Copy the NEW Web App URL
10. Test new URL in browser

### Solution 3: Test web app directly in browser

Open this URL in browser (replace with your actual URL):
```
https://script.google.com/macros/s/AKfycbwsSJmf57Ef32wdlIo825duaxrRFvjgLb1H7eP9KWAmn7rlzTCKwBB5uU6D5uzNn1k/exec?id=TEST-123&status=Completed
```

You should see:
- ✓ Green success message
- Appointment ID: TEST-123
- Status: Completed

If you see "Document doesn't exist", the deployment isn't working.

### Solution 4: Check authorization

1. In Apps Script, run **`testDirectWrite()`** function
2. It will ask for authorization
3. Click "Review Permissions"
4. Choose your Google account
5. Click "Advanced" → "Go to [script name] (unsafe)"
6. Click "Allow"
7. Now try deploying again

## Error: Sheet "Completions" not found

**Solution**:
1. Go to your Google Sheet
2. Check sheet tab is named exactly: **Completions** (capital C, plural)
3. Or run `initializeSheet()` function in Apps Script to create it

## Testing Steps

Follow these in order:

### Step 1: Test sheet writing directly
```javascript
// In Apps Script editor
// Select: initializeSheet
// Click: Run
// Check: Logs say "✓ Sheet initialized successfully"
```

### Step 2: Test completion writing
```javascript
// Select: testDirectWrite
// Click: Run
// Check: New row appears in Completions sheet
```

### Step 3: Test web app in browser
```
Open: YOUR_WEB_APP_URL?id=TEST-BROWSER&status=Completed
Should see: Green success message
Check: New row in sheet with TEST-BROWSER
```

### Step 4: Test from calendar link
```
1. Create test calendar event
2. Click completion link
3. Should see success message
4. Check sheet for new row
```

## Common Issues

### Issue: Link opens but shows error page

**Check:**
- Does error mention "Completions" sheet? → Create the sheet
- Does error mention permissions? → Re-authorize script
- Does error show different error? → Check Apps Script logs

### Issue: Success message shows but no row in sheet

**Check:**
- Refresh the sheet (Ctrl+R or Cmd+R)
- Check you're looking at the right sheet ("Completions" tab)
- Check Apps Script logs: View → Logs

### Issue: Calendar event link doesn't work on phone

**Check:**
- Link should be plaintext URL, not formatted link
- Try copying link and pasting in browser
- Check if link ends with `/exec` not `/dev`

## Getting More Info

### Check Apps Script Logs
1. Open Apps Script editor
2. **View → Logs** (after running a function)
3. or **View → Executions** (shows all recent runs)

### Check Sheet Activity
1. Open Google Sheet
2. **File → Version history → See version history**
3. Check if script is making changes

## Still Not Working?

### Nuclear Option: Start Fresh

1. **Archive current deployment**: Deploy → Manage deployments → Archive
2. **Delete Code.gs**: Delete all code
3. **Copy updated code**: From `docs/COMPLETION_TRACKING_SCRIPT_UPDATED.gs`
4. **Paste** into editor
5. **Save** (Ctrl+S)
6. **Run** `initializeSheet()` function
7. **Authorize** when prompted
8. **Run** `testDirectWrite()` function
9. **Verify** row appears in sheet
10. **Create NEW deployment**: Deploy → New deployment → Web app
11. **Copy** new Web App URL
12. **Test** in browser: `URL?id=FRESH&status=Completed`

## Quick Test Commands

### Test 1: Verify sheet exists
```javascript
function checkSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Logger.log('Spreadsheet: ' + ss.getName());
  Logger.log('Sheets: ' + ss.getSheets().map(s => s.getName()).join(', '));
}
```

### Test 2: Test web app response
Browser URL:
```
YOUR_URL?id=DEBUG&status=TestStatus
```

Should show success page with:
- Appointment ID: DEBUG
- Status: TestStatus
- Timestamp

---

## Success Checklist

When everything works:
- ✓ `testDirectWrite()` creates row in sheet
- ✓ Web app URL in browser shows success page
- ✓ New row appears in Completions sheet
- ✓ Calendar link opens browser with success
- ✓ Sheet updates with correct data

If all checked ✓ → POC is working!
If any ✗ → See solutions above for that specific issue.
