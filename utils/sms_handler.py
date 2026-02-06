"""
SMS Handler for MLS3

Generates SMS messages from templates and opens them via Android intents.
"""
import subprocess
from urllib.parse import quote_plus
from datetime import date
from typing import Optional

from models import Member, PrayerAssignment, MessageTemplates
import config


def expand_prayer_template(
    template_name: str,
    member: Member,
    assignment: PrayerAssignment,
    templates: MessageTemplates
) -> str:
    """
    Expand an SMS template with member and assignment data.

    Args:
        template_name: Name of template (e.g., 'invite', 'reminder')
        member: Member object
        assignment: PrayerAssignment object
        templates: MessageTemplates object

    Returns:
        Expanded message text
    """
    # Parse assignment date
    assignment_date = assignment.date_obj

    # Format date for display
    date_str = assignment_date.strftime(config.DISPLAY_DATE_FORMAT)

    # Prayer type in lowercase for natural reading
    prayer_type_lower = assignment.prayer_type.lower()

    # Expand template
    message = templates.expand_template(
        'prayer',
        template_name,
        first_name=member.first_name,
        last_name=member.last_name,
        date=date_str,
        prayer_type=prayer_type_lower,
        day_of_week='Sunday'  # For prayers, always Sunday
    )

    return message


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
    # Debug mode - skip actual SMS sending
    if config.DEBUG_SMS:
        print("\n" + "="*60)
        print("DEBUG SMS MODE - SMS not actually sent")
        print("="*60)
        print(f"To: {phone_number}")
        print(f"Message: {message}")
        print(f"Length: {len(message)} characters")
        print("="*60 + "\n")
        return True

    try:
        # URL encode the message
        encoded_message = quote_plus(message)

        # Create SMS intent URL
        intent_url = f"sms:{phone_number}?body={encoded_message}"

        # Launch via termux-open-url
        result = subprocess.run(
            ['termux-open-url', intent_url],
            capture_output=True,
            timeout=5
        )

        return result.returncode == 0

    except FileNotFoundError:
        # termux-open-url not found (probably not on Termux)
        print("Error: termux-open-url not found")
        print(f"Would send SMS to {phone_number}:")
        print(f"Message: {message}")
        return False

    except subprocess.TimeoutExpired:
        print("Error: termux-open-url timed out")
        return False

    except Exception as e:
        print(f"Error launching SMS intent: {e}")
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


def send_prayer_invitation(
    member: Member,
    assignment: PrayerAssignment,
    templates: MessageTemplates
) -> bool:
    """
    Send prayer invitation SMS.

    Args:
        member: Member to invite
        assignment: Prayer assignment
        templates: Message templates

    Returns:
        True if SMS intent launched successfully
    """
    message = expand_prayer_template('invite', member, assignment, templates)
    return send_sms_intent(member.phone, message)


def send_prayer_reminder(
    member: Member,
    assignment: PrayerAssignment,
    templates: MessageTemplates
) -> bool:
    """
    Send prayer reminder SMS.

    Args:
        member: Member to remind
        assignment: Prayer assignment
        templates: Message templates

    Returns:
        True if SMS intent launched successfully
    """
    message = expand_prayer_template('reminder', member, assignment, templates)
    return send_sms_intent(member.phone, message)


def send_thank_you(
    member: Member,
    assignment: PrayerAssignment,
    templates: MessageTemplates
) -> bool:
    """
    Send thank you SMS after acceptance.

    Args:
        member: Member who accepted
        assignment: Prayer assignment
        templates: Message templates

    Returns:
        True if SMS intent launched successfully
    """
    message = expand_prayer_template('thank_you', member, assignment, templates)
    return send_sms_intent(member.phone, message)
