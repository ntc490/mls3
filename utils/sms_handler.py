"""
SMS Handler for MLS3

Generates SMS messages from templates and opens them in the default SMS app,
via termux-am (default) or Tasker (MLS3_TASKER_SMS=true).
Automatically routes messages to parents for minors.
"""
import os
import subprocess
from datetime import date
from typing import Optional, List, Dict, Tuple

from models import Member, MessageTemplates, MemberDatabase, HouseholdDatabase
import config

# Termux's own bin directory. The server may run inside proot-distro, where it
# isn't on PATH - and termux-am calls termux-am-socket by bare name, so the
# directory has to be on PATH for the child process too.
TERMUX_BIN = '/data/data/com.termux/files/usr/bin'

# The file Tasker watches. This path has to match the Tasker profile exactly or
# nothing is sent and nothing reports an error - MLS3 writes the file happily
# either way.
TASKER_QUEUE_FILE = '/sdcard/tasker_sms.txt'


def get_sms_info(activity: str, template_name: str, member: Member,
                 templates: MessageTemplates, members_db: MemberDatabase = None,
                 households_db: HouseholdDatabase = None,
                 appointment=None, **kwargs) -> Dict:
    """
    Get SMS message and phone number(s) for a member.
    Handles parent routing for minors automatically.

    This is the shared logic used by all SMS functions - it just returns
    the message and phone without actually sending.

    Args:
        activity: Template category (prayer, appointments, adhoc)
        template_name: Template name within category (invite, reminder, etc.)
        member: Member object
        templates: MessageTemplates instance
        members_db: MemberDatabase instance (required for parent routing)
        appointment: Optional appointment/assignment object
        **kwargs: Additional variables

    Returns:
        Dict with:
            success: bool
            message: str (if success)
            phone: str (if success)
            error: str (if not success)
    """
    # Check if member is a minor and we should route to parents
    if member.is_minor:
        if not members_db:
            return {
                'success': False,
                'error': f"{member.display_name} is a minor but cannot route to parents (system error)"
            }

        # Get parents (using household data if available)
        parents = members_db.get_parents(member.member_id, households_db)
        if not parents:
            return {
                'success': False,
                'error': f"{member.display_name} is a minor with no parents found in household"
            }

        # Collect parent phone numbers
        parent_phones = []
        for parent in parents:
            if parent.phone and parent.phone.strip():
                parent_phones.append(parent.phone.strip())

        if not parent_phones:
            return {
                'success': False,
                'error': f"{member.display_name}'s parents have no phone numbers on file"
            }

        # Build parent greeting
        any_formal = any(p.has_flag('blue') for p in parents)
        if len(parents) == 1:
            parent = parents[0]
            if parent.has_flag('blue'):
                title = 'Brother' if parent.gender == 'M' else 'Sister'
                parent_greeting = f"{title} {parent.last_name}"
            else:
                parent_greeting = parent.display_name
        elif any_formal:
            parent_greeting = f"Brother and Sister {parents[0].last_name}"
        else:
            parent_names_casual = [p.display_name for p in parents]
            parent_greeting = ' & '.join(parent_names_casual)

        # Use parent template
        parent_template_name = f"{template_name}_parent"
        kwargs['child_name'] = member.display_name
        kwargs['parent_greeting'] = parent_greeting

        # Try parent template, fall back to base. A missing template comes back
        # as an empty string (not a KeyError), so check before expanding -
        # otherwise the parent gets an empty SMS.
        if templates.get_template(activity, parent_template_name):
            message = templates.expand_smart(activity, parent_template_name, member, appointment, **kwargs)
        else:
            message = templates.expand_smart(activity, template_name, member, appointment, **kwargs)

        # Return group SMS phone
        return {
            'success': True,
            'message': message,
            'phone': ';'.join(parent_phones)
        }

    # Normal member flow
    if not member.phone or member.phone.strip() == '':
        return {
            'success': False,
            'error': f"{member.display_name} has no phone number on file"
        }

    # Expand template
    message = templates.expand_smart(activity, template_name, member, appointment, **kwargs)

    return {
        'success': True,
        'message': message,
        'phone': member.phone
    }


def expand_and_send(activity: str, template_name: str, member: Member,
                    templates: MessageTemplates, members_db: MemberDatabase = None,
                    households_db: HouseholdDatabase = None,
                    appointment=None, **kwargs):
    """
    Generic function to expand template with smart variables and send SMS.
    Automatically routes to parents if member is a minor.

    Args:
        activity: Template category (prayer, appointments, adhoc)
        template_name: Template name within category (invite, reminder, etc.)
        member: Member object
        templates: MessageTemplates instance
        members_db: MemberDatabase instance (required for parent routing)
        households_db: HouseholdDatabase instance (for accurate parent identification)
        appointment: Optional appointment/assignment object
        **kwargs: Additional variables (e.g., conductor="Bishop")

    Returns:
        Tuple of (success: bool, error_message: str or None)
        - (True, None) if SMS was successfully queued
        - (False, "error message") if failed
    """
    # Get message and phone using shared logic
    result = get_sms_info(activity, template_name, member, templates, members_db, households_db, appointment, **kwargs)

    if not result['success']:
        print(f"ERROR: {result['error']}")
        return (False, result['error'])

    if member.is_minor:
        print(f"Member {member.full_name} is a minor - routing to parents")

    success = send_sms_intent(result['phone'], result['message'])
    return (success, None) if success else (False, "Failed to queue SMS")


def send_sms_intent(phone_number: str, message: str) -> bool:
    """
    Open the default SMS app with a message pre-filled; the user still presses
    send.

    By default this fires android.intent.action.SENDTO itself through
    termux-am. With MLS3_TASKER_SMS=true it queues the message for Tasker,
    which fires the same intent. Either way the intent names no package, so
    Android picks the default SMS app.

    Args:
        phone_number: Phone number to send to
        message: Pre-filled message text

    Returns:
        True if the message was queued, False otherwise
    """
    # Print debug output if enabled
    if config.DEBUG_SMS:
        print("\n" + "="*60)
        print("SMS DEBUG OUTPUT")
        print("="*60)
        print(f"To: {phone_number}")
        print(f"Message: {message}")
        print(f"Length: {len(message)} characters")
        if config.DISABLE_SMS:
            print("Status: SMS DISABLED - not actually sent")
        else:
            print(f"Status: Sending via {'Tasker' if config.TASKER_SMS else 'termux-am'}...")
        print("="*60 + "\n")

    # Skip actual SMS sending if disabled (for desktop testing)
    if config.DISABLE_SMS:
        return True

    try:
        # Validate phone number is not empty
        if not phone_number or phone_number.strip() == '':
            print(f"ERROR: Cannot send SMS - phone number is empty")
            return False

        if config.TASKER_SMS:
            return _queue_for_tasker(phone_number, message)
        return _open_with_termux_am(phone_number, message)

    except Exception as e:
        print(f"ERROR: Unexpected error sending SMS: {e}")
        return False


def _open_with_termux_am(phone_number: str, message: str) -> bool:
    """
    Fire the SENDTO intent directly with termux-am, falling back to plain am.

    termux-am is fast but needs the Termux app's am socket server; when that
    can't be reached ("Could not connect to socket"), plain am still works - it
    starts its own app_process, which takes a second or two longer.

    Needs the Termux:API app, and Termux allowed to display over other apps -
    without that, Android silently refuses to open an activity while another
    app is in front.
    """
    env = dict(os.environ)
    env['PATH'] = f"{TERMUX_BIN}:{env.get('PATH', '')}"
    args = [
        'start',
        '-a', 'android.intent.action.SENDTO',
        '-d', f"smsto:{phone_number}",
        '--es', 'sms_body', message,
    ]

    for am in ('termux-am', 'am'):
        try:
            result = subprocess.run([f"{TERMUX_BIN}/{am}"] + args, env=env,
                                    capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"ERROR: Failed to run {am}: {e}")
            continue

        # am reports some failures ("Error: Activity not started ...") on
        # stdout with a zero exit status, so check the output as well.
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0 and 'Error' not in output:
            return True
        print(f"ERROR: {am} failed (exit {result.returncode}): {output}")

    return False


def _queue_for_tasker(phone_number: str, message: str) -> bool:
    """
    Write "<phone>\\n<message>" (literal backslash-n as delimiter) to the file
    Tasker watches; Tasker fires the SENDTO intent when the file changes.
    """
    try:
        with open(TASKER_QUEUE_FILE, 'w') as f:
            f.write(f"{phone_number}\\n{message}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to queue SMS to {TASKER_QUEUE_FILE}: {e}")
        return False


def preview_sms(phone_number: str, message: str) -> dict:
    """
    Preview SMS without sending (for testing/debugging).

    Args:
        phone_number: Phone number
        message: Message text

    Returns:
        Dictionary with preview information
    """
    return {
        'to': phone_number,
        'message': message,
        'message_length': len(message),
        'estimated_parts': (len(message) // 160) + 1
    }
