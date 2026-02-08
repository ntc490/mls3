"""
SMS Handler for MLS3

Generates SMS messages from templates and sends them via Tasker.
"""
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
        first_name=member.display_name,  # Use display_name (AKA or first word of first_name)
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
