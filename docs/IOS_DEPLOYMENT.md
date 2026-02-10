# iOS Deployment Guide

**Status**: MLS3 is already iOS-compatible via Safari - no code changes needed!

## TL;DR

MLS3 works on iOS **right now** via Safari. SMS opens the Messages app with pre-filled text - same behavior as Android/Termux.

## SMS on iOS - How It Works

### The Code (Already Cross-Platform)

MLS3 uses the standard `sms:` URI scheme, which works identically on iOS and Android:

```javascript
// static/js/home.js (existing code)
async function openSMS(phone, memberId) {
    // Get phone number via API (handles parent routing for minors)
    const response = await fetch(`/api/members/${memberId}/sms-direct`, {
        method: 'POST'
    });

    const result = await response.json();

    if (!response.ok) {
        alert(result.error || 'Failed to send SMS');
        return;
    }

    // Open SMS app with pre-filled message
    const smsUrl = `sms:${result.phone}`;
    window.location.href = smsUrl;  // ← Works on iOS Safari!
}
```

For messages with pre-filled text (like prayer reminders):

```javascript
// With message body
const smsUrl = `sms:${phone}?body=${encodeURIComponent(message)}`;
window.location.href = smsUrl;
```

### What Happens on iOS

1. User clicks "SMS" or "Invite" button in MLS3
2. Safari opens iOS Messages app
3. Message is pre-filled with recipient and text
4. User reviews and taps **Send**

**This is exactly how it works on Android too** - MLS3 doesn't auto-send SMS on either platform.

## Deployment Options for iOS

### Option 1: iSH (Run Locally on iPhone) - FREE

**iSH** is a Linux shell for iOS that can run Python apps.

#### Setup (15 minutes):

1. **Install iSH** from App Store (free)
   - https://apps.apple.com/us/app/ish-shell/id1436902243

2. **Install Python and dependencies**:
   ```bash
   # In iSH terminal
   apk add python3 py3-pip git
   ```

3. **Get MLS3**:
   ```bash
   cd ~
   git clone YOUR_REPO_URL mls3
   cd mls3
   pip3 install -r requirements.txt
   ```

4. **Configure**:
   ```bash
   # Disable SMS for testing (prints to console instead)
   export MLS3_DEBUG_SMS=true
   export MLS3_DISABLE_SMS=true

   # Optional: Set data directory
   export MLS3_DATA_DIR=~/mls3-data
   ```

5. **Run**:
   ```bash
   python3 app.py
   ```

6. **Access in Safari**:
   - Open Safari on iPhone
   - Navigate to: `http://localhost:5000`
   - Add to Home Screen for app-like experience

#### Pros:
- ✓ Free
- ✓ Self-contained on device
- ✓ No internet required
- ✓ Works offline

#### Cons:
- ✗ iSH is slower than native (Alpine Linux in emulation)
- ✗ No background execution (app stops when you switch away)
- ✗ Need to start manually each time
- ✗ Limited storage

---

### Option 2: Remote Server (Best for Production)

Run MLS3 on a server, access from any device via Safari.

#### Setup (1 hour):

1. **Get a VPS** ($5-10/month):
   - DigitalOcean Droplet
   - Linode Nanode
   - AWS Lightsail
   - Or use your home computer with port forwarding

2. **Deploy MLS3**:
   ```bash
   ssh user@your-server

   # Install dependencies
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git

   # Clone repo
   git clone YOUR_REPO_URL mls3
   cd mls3

   # Setup virtualenv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   # Configure
   export MLS3_DATA_DIR=~/mls3-data
   mkdir -p ~/mls3-data

   # Run (use screen/tmux for persistence)
   screen -S mls3
   python app.py
   # Press Ctrl+A, D to detach
   ```

3. **Secure with HTTPS** (recommended):
   - Use nginx reverse proxy + Let's Encrypt
   - Or use Tailscale for private access (easier)

4. **Access from iPhone**:
   - Open Safari
   - Navigate to: `https://your-server.com`
   - Add to Home Screen

#### Pros:
- ✓ Access from anywhere
- ✓ Runs 24/7
- ✓ Fast performance
- ✓ Works on all devices (iPhone, iPad, computer)
- ✓ Automatic backups possible

#### Cons:
- ✗ Monthly cost ($5-10)
- ✗ Requires server setup knowledge
- ✗ Need internet connection

---

### Option 3: Local Computer + Safari (Quickest Test)

Run on your Mac/PC, access from iPhone on same WiFi.

#### Setup (5 minutes):

1. **On your computer**:
   ```bash
   cd /path/to/mls3
   source venv/bin/activate

   # Allow network access
   export FLASK_HOST=0.0.0.0
   python app.py
   ```

2. **Find your computer's IP**:
   - Mac: System Settings → Network → IP Address
   - Linux: `ip addr` or `hostname -I`
   - Usually something like: `192.168.1.100`

3. **On iPhone**:
   - Open Safari
   - Navigate to: `http://192.168.1.100:5000`
   - Add to Home Screen

#### Pros:
- ✓ Immediate testing
- ✓ Free
- ✓ Fast performance

#### Cons:
- ✗ Computer must be on
- ✗ Only works on same WiFi network
- ✗ Not portable

---

## Testing SMS on iOS

### Simple Test:

1. Deploy MLS3 using any option above
2. Open in Safari on iPhone
3. Navigate to a member profile
4. Click "SMS" button
5. **Expected**: iOS Messages app opens with member's phone number
6. Type message and tap Send

### Full Test (Prayer Reminder):

1. Schedule a prayer assignment to a member
2. Click "Remind" button
3. **Expected**: Messages app opens with:
   - Recipient: Member's phone (or parents if minor)
   - Message: Pre-filled reminder text
4. Review and tap Send

## iOS-Specific Considerations

### Add to Home Screen

For app-like experience:

1. Open MLS3 in Safari
2. Tap Share button (box with arrow)
3. Tap "Add to Home Screen"
4. Name it "MLS3"
5. Tap "Add"

Now MLS3 appears as an icon on your home screen!

### SMS Behavior Notes

- ✓ `sms:` scheme works in Safari (not in some other browsers)
- ✓ Multiple recipients: `sms:8015551234,8015555678` (semicolon on Android, comma on iOS)
- ✓ Pre-filled body: `sms:8015551234?body=Hello%20there`
- ✗ Cannot auto-send (iOS security restriction - this is by design)
- ✗ Cannot send without user interaction (must tap Send)

### Parent Routing for Minors

**Works identically on iOS**:
- Click SMS for a minor
- MLS3 routes to parent phone numbers
- Messages app opens with parent recipients
- Multiple parents: Uses comma-separated numbers on iOS

## Troubleshooting

### SMS Link Doesn't Open Messages App

**Possible causes**:
- Not using Safari (use Safari, not Chrome)
- Phone number format issue (MLS3 handles this)
- iOS privacy settings

**Fix**: Ensure you're using Safari, not another browser.

### Can't Access MLS3 from iPhone

**iSH**: Make sure iSH is running and app.py is started
**Remote**: Check firewall allows port 5000 (or use proper port 80/443 with nginx)
**Local network**: Ensure iPhone and computer on same WiFi

### SMS Opens But Message Not Pre-filled

**Check**: URL encoding
```javascript
// Bad
sms:123?body=Hello there  // Spaces break it

// Good
sms:123?body=Hello%20there  // Properly encoded
```

MLS3 already uses `encodeURIComponent()` so this should work.

## Performance Comparison

| Platform | Speed | Reliability | Background | Cost |
|----------|-------|-------------|------------|------|
| **iSH** | Slow | Good | No | Free |
| **Remote Server** | Fast | Excellent | Yes | $5-10/mo |
| **Local Computer** | Fast | Good (when on) | Yes | Free |

## Recommended Setup

**For Testing**: Option 3 (Local Computer)
**For Production**: Option 2 (Remote Server) or wait until you have a spare server

**For True Mobile-Only**: Option 1 (iSH) - but expect slower performance

## Code Changes Needed for iOS

**None!** The existing code already works on iOS via Safari.

The `sms:` URI scheme is a web standard supported by both iOS and Android.

## Next Steps

1. **Quick test**: Run on computer, access from iPhone Safari
2. **Verify SMS**: Click SMS button, ensure Messages app opens
3. **Test parent routing**: Try SMS to a minor, verify goes to parents
4. **Decide deployment**: Choose iSH (mobile) or server (best performance)

---

**Bottom Line**: MLS3 is already iOS-ready. Just run it somewhere and open Safari!

*Last Updated: February 9, 2026*
