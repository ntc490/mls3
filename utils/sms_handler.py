"""
SMS Handler for MLS3

Generates SMS messages from templates and sends them via Tasker.
Automatically routes messages to parents for minors.
"""
from datetime import date
from typing import Optional, List, Dict, Tuple

from models import Member, MessageTemplates, MemberDatabase
import config


def get_sms_info(activity: str, template_name: str, member: Member,
                 templates: MessageTemplates, members_db: MemberDatabase = None,
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

        # Get parents
        parents = members_db.get_parents(member.member_id)
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

        # Try parent template, fall back to base
        try:
            message = templates.expand_smart(activity, parent_template_name, member, appointment, **kwargs)
        except KeyError:
            # Parent template doesn't exist, use base template
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
        appointment: Optional appointment/assignment object
        **kwargs: Additional variables (e.g., conductor="Bishop")

    Returns:
        Tuple of (success: bool, error_message: str or None)
        - (True, None) if SMS was successfully queued
        - (False, "error message") if failed
    """
    # Get message and phone using shared logic
    result = get_sms_info(activity, template_name, member, templates, members_db, appointment, **kwargs)

    if not result['success']:
        print(f"ERROR: {result['error']}")
        return (False, result['error'])

    # Send via Tasker
    if member.is_minor:
        print(f"Member {member.full_name} is a minor - routing to parents")

    success = send_sms_intent(result['phone'], result['message'])
    return (success, None) if success else (False, "Failed to queue SMS")


def send_sms_intent(phone_number: str, message: str) -> bool:
    """
    Opens Android SMS app with pre-filled message using termux-open-url.
    User must manually press send.

    Args:
        phone_number: Phone number to send to
        message: Pre-filled message text

    Returns:
        True if intent was launched successfully, False otherwise
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
            print("Status: Sending via Tasker...")
        print("="*60 + "\n")

    # Skip actual SMS sending if disabled (for desktop testing)
    if config.DISABLE_SMS:
        return True

    try:
        # Validate phone number is not empty
        if not phone_number or phone_number.strip() == '':
            print(f"ERROR: Cannot send SMS - phone number is empty")
            return False

        # Write to Tasker file queue
        # Tasker monitors this file and sends SMS when modified
        # Format: phone_number\nmessage (literal backslash-n as delimiter)
        try:
            content = f"{phone_number}\\n{message}"

            with open('/sdcard/tasker_sms.txt', 'w') as f:
                f.write(content)

            return True

        except Exception as e:
            print(f"ERROR: Failed to queue SMS to Tasker: {e}")
            return False

    except Exception as e:
        print(f"ERROR: Unexpected error sending SMS: {e}")
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
