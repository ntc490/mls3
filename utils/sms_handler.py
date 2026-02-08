"""
SMS Handler for MLS3

Generates SMS messages from templates and sends them via Tasker.
"""
from datetime import date
from typing import Optional

from models import Member, MessageTemplates
import config


def expand_and_send(activity: str, template_name: str, member: Member,
                    templates: MessageTemplates, appointment=None, **kwargs) -> bool:
    """
    Generic function to expand template with smart variables and send SMS.

    Args:
        activity: Template category (prayer, appointments, adhoc)
        template_name: Template name within category (invite, reminder, etc.)
        member: Member object
        templates: MessageTemplates instance
        appointment: Optional appointment/assignment object
        **kwargs: Additional variables (e.g., conductor="Bishop")

    Returns:
        True if SMS was successfully queued, False otherwise
    """
    # Check for phone number
    if not member.phone or member.phone.strip() == '':
        print(f"ERROR: Cannot send SMS - {member.full_name} has no phone number")
        return False

    # Expand template with smart variables
    message = templates.expand_smart(activity, template_name, member, appointment, **kwargs)

    # Send via Tasker
    return send_sms_intent(member.phone, message)


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
