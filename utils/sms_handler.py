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
    # Check if member is a minor and we should route to parents
    if member.is_minor:
        if not members_db:
            error_msg = f"{member.display_name} is a minor but cannot route to parents (system error)"
            print(f"WARNING: {member.full_name} is a minor but members_db not provided - cannot route to parents")
            return (False, error_msg)
        print(f"Member {member.full_name} is a minor - routing to parents")
        return send_to_parents(activity, template_name, member, templates, members_db, appointment, **kwargs)

    # Normal member flow - send directly
    # Check for phone number
    if not member.phone or member.phone.strip() == '':
        error_msg = f"{member.display_name} has no phone number on file"
        print(f"ERROR: Cannot send SMS - {member.full_name} has no phone number")
        return (False, error_msg)

    # Expand template with smart variables
    message = templates.expand_smart(activity, template_name, member, appointment, **kwargs)

    # Send via Tasker
    success = send_sms_intent(member.phone, message)
    return (success, None) if success else (False, "Failed to queue SMS")


def send_to_parents(activity: str, template_name: str, child: Member,
                   templates: MessageTemplates, members_db: MemberDatabase,
                   appointment=None, **kwargs):
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
        Tuple of (success: bool, error_message: str or None)
    """
    # Get parents from household
    parents = members_db.get_parents(child.member_id)

    if not parents:
        error_msg = f"{child.display_name} is a minor with no parents found in household"
        print(f"WARNING: {child.full_name} is a minor but no parents found in household")
        print(f"Cannot send SMS - no parent contact available")
        return (False, error_msg)

    # Collect parent phone numbers
    parent_phones = []
    parent_names = []
    for parent in parents:
        if parent.phone and parent.phone.strip():
            parent_phones.append(parent.phone.strip())
            parent_names.append(parent.full_name)

    if not parent_phones:
        error_msg = f"{child.display_name}'s parents have no phone numbers on file"
        print(f"ERROR: Cannot send SMS - no parent has phone number")
        print(f"Parents: {', '.join(p.full_name for p in parents)}")
        return (False, error_msg)

    # Use first parent for template expansion (for has_flag checks)
    primary_parent = parents[0]

    # Build parent greeting based on formality
    # Check if any parent has blue flag (formal)
    any_formal = any(p.has_flag('blue') for p in parents)

    if len(parents) == 1:
        # Single parent - check if formal or casual
        parent = parents[0]
        if parent.has_flag('blue'):
            # Formal - use Brother/Sister LastName
            title = 'Brother' if parent.gender == 'M' else 'Sister'
            parent_greeting = f"{title} {parent.last_name}"
        else:
            # Casual - just use their first name
            parent_greeting = parent.display_name
    elif any_formal:
        # At least one parent is formal - use "Brother and Sister LastName"
        # This works for opposite-gender couples
        # For same-gender couples, we'll still use this format as it's respectful
        last_name = parents[0].last_name
        parent_greeting = f"Brother and Sister {last_name}"
    else:
        # Both informal - use "FirstName & FirstName"
        parent_names_casual = [p.display_name for p in parents]
        parent_greeting = ' & '.join(parent_names_casual)

    # Try parent-specific template first (e.g., "invite_parent")
    parent_template_name = f"{template_name}_parent"

    # Add child_name and parent_greeting to kwargs for parent template
    kwargs['child_name'] = child.display_name
    kwargs['parent_greeting'] = parent_greeting

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
    success = send_sms_intent(group_phone, message)
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
