"""
SMS Handler for MLS3

Generates SMS messages from templates and sends them via Tasker.
Automatically routes messages to parents for minors.
"""
from datetime import date
from typing import Optional, List

from models import Member, MessageTemplates, MemberDatabase
import config


def expand_and_send(activity: str, template_name: str, member: Member,
                    templates: MessageTemplates, members_db: MemberDatabase = None,
                    appointment=None, **kwargs) -> bool:
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
        True if SMS was successfully queued, False otherwise
    """
    # Check if member is a minor and we should route to parents
    if member.is_minor and members_db:
        return send_to_parents(activity, template_name, member, templates, members_db, appointment, **kwargs)

    # Normal member flow - send directly
    # Check for phone number
    if not member.phone or member.phone.strip() == '':
        print(f"ERROR: Cannot send SMS - {member.full_name} has no phone number")
        return False

    # Expand template with smart variables
    message = templates.expand_smart(activity, template_name, member, appointment, **kwargs)

    # Send via Tasker
    return send_sms_intent(member.phone, message)


def send_to_parents(activity: str, template_name: str, child: Member,
                   templates: MessageTemplates, members_db: MemberDatabase,
                   appointment=None, **kwargs) -> bool:
    """
    Send message to parents instead of minor child.
    Uses _parent template variant with {child_name} variable.
    Sends group SMS to all parents.

    Args:
        activity: Template category (prayer, appointments, adhoc)
        template_name: Template name within category (invite, reminder, etc.)
        child: Minor member object
        templates: MessageTemplates instance
        members_db: MemberDatabase instance
        appointment: Optional appointment/assignment object
        **kwargs: Additional variables

    Returns:
        True if SMS was successfully queued, False otherwise
    """
    # Get parents from household
    parents = members_db.get_parents(child.member_id)

    if not parents:
        print(f"WARNING: {child.full_name} is a minor but no parents found in household")
        print(f"Cannot send SMS - no parent contact available")
        return False

    # Collect parent phone numbers
    parent_phones = []
    parent_names = []
    for parent in parents:
        if parent.phone and parent.phone.strip():
            parent_phones.append(parent.phone.strip())
            parent_names.append(parent.full_name)

    if not parent_phones:
        print(f"ERROR: Cannot send SMS - no parent has phone number")
        print(f"Parents: {', '.join(p.full_name for p in parents)}")
        return False

    # Use first parent for template expansion (name variables)
    primary_parent = parents[0]

    # Try parent-specific template first (e.g., "invite_parent")
    parent_template_name = f"{template_name}_parent"

    # Add child_name to kwargs for parent template
    kwargs['child_name'] = child.preferred_name

    # Attempt to expand parent template
    try:
        message = templates.expand_smart(activity, parent_template_name, primary_parent, appointment, **kwargs)
    except KeyError:
        # Parent template doesn't exist, fall back to regular template
        print(f"WARNING: Parent template '{parent_template_name}' not found, using '{template_name}'")
        message = templates.expand_smart(activity, template_name, primary_parent, appointment, **kwargs)

    # Join phone numbers with semicolon for group SMS
    group_phone = ';'.join(parent_phones)

    print(f"Routing SMS for minor {child.full_name} to parents: {', '.join(parent_names)}")

    # Send via Tasker
    return send_sms_intent(group_phone, message)


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
