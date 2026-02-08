"""
Smart Template Expander for MLS3
Handles conditional flag-based expansions, smart dates, and random pleasantries
"""
import re
import random
from datetime import date
from typing import Optional, Dict, Any


class SmartTemplateExpander:
    """
    Expands message templates with smart variables.

    Supported syntax:
    - {variable|flag?transform:transform} - Conditional based on member flag
    - {smart_date} - Today/tomorrow/formatted date
    - {random:list_name} - Random selection from list
    - {simple_variable} - Standard variable substitution
    """

    # Regex patterns
    CONDITIONAL_PATTERN = re.compile(r'\{(\w+)\|(\w+)\?(\w+):(\w+)\}')
    RANDOM_PATTERN = re.compile(r'\{random:(\w+)\}')
    SMART_DATE_PATTERN = re.compile(r'\{smart_date(?:\|(\w+)\?(\w+):(\w+))?\}')
    SIMPLE_VAR_PATTERN = re.compile(r'\{(\w+)\}')

    def __init__(self, templates_obj):
        """
        Args:
            templates_obj: MessageTemplates instance with pleasantries loaded
        """
        self.templates = templates_obj

    def expand(self, template_str: str, member, appointment=None, **kwargs) -> str:
        """
        Expand template with all smart variables.

        Args:
            template_str: Raw template string
            member: Member object
            appointment: Optional appointment/assignment object (for dates)
            **kwargs: Additional simple variables (e.g., conductor="Bishop")

        Returns:
            Fully expanded message string
        """
        result = template_str

        # 1. Expand {random:list_name}
        result = self._expand_random_variables(result)

        # 2. Expand {smart_date|flag?transform:transform} or {smart_date}
        if appointment:
            result = self._expand_smart_date_variables(result, member, appointment)

        # 3. Expand {variable|flag?transform:transform}
        result = self._expand_conditional_variables(result, member, appointment, kwargs)

        # 4. Expand remaining {simple_variable}
        result = self._expand_simple_variables(result, member, appointment, kwargs)

        return result

    def _expand_random_variables(self, text: str) -> str:
        """Expand {random:list_name} with random selection from pleasantries"""
        def replace_random(match):
            list_name = match.group(1)
            pleasantries_list = self.templates.pleasantries.get(list_name, [])
            if not pleasantries_list:
                return ""  # Empty if list not found
            return random.choice(pleasantries_list)

        return self.RANDOM_PATTERN.sub(replace_random, text)

    def _expand_smart_date_variables(self, text: str, member, appointment) -> str:
        """Expand {smart_date} and {smart_date|flag?transform:transform}"""
        def replace_smart_date(match):
            flag = match.group(1)
            true_transform = match.group(2)
            false_transform = match.group(3)

            # Get base smart date value
            smart_date_value = self._calculate_smart_date(appointment)

            # If conditional, apply transform
            if flag and true_transform and false_transform:
                has_flag = member.has_flag(flag)
                transform = true_transform if has_flag else false_transform
                return self._apply_date_transform(smart_date_value, appointment, transform)

            return smart_date_value

        return self.SMART_DATE_PATTERN.sub(replace_smart_date, text)

    def _calculate_smart_date(self, appointment) -> str:
        """Calculate smart date string based on appointment date vs today"""
        if not appointment:
            return ""

        appt_date = appointment.date_obj
        today = date.today()
        delta = (appt_date - today).days

        if delta == 0:
            return "today"
        elif delta == 1:
            return "tomorrow"
        else:
            # Default format: "Sunday, February 9"
            return appt_date.strftime("%A, %B %d")

    def _apply_date_transform(self, base_value: str, appointment, transform: str) -> str:
        """Apply transform to date (for future: short, long, etc.)"""
        if not appointment:
            return base_value

        appt_date = appointment.date_obj

        if transform == "short":
            return appt_date.strftime("%b %d")  # "Feb 9"
        elif transform == "long":
            return appt_date.strftime("%A, %B %d, %Y")  # "Sunday, February 9, 2026"
        else:
            # Unknown transform, return base value
            return base_value

    def _expand_conditional_variables(self, text: str, member, appointment, extra_vars: Dict) -> str:
        """Expand {variable|flag?transform:transform}"""
        def replace_conditional(match):
            var_name = match.group(1)
            flag = match.group(2)
            true_transform = match.group(3)
            false_transform = match.group(4)

            has_flag = member.has_flag(flag)
            transform = true_transform if has_flag else false_transform

            return self._apply_transform(var_name, transform, member, appointment, extra_vars)

        return self.CONDITIONAL_PATTERN.sub(replace_conditional, text)

    def _apply_transform(self, var_name: str, transform: str, member, appointment, extra_vars: Dict) -> str:
        """Apply named transform to variable"""
        import config

        # Name transforms
        if var_name == "name":
            if transform == "formal":
                # "Brother/Sister LastName"
                prefix = "Brother" if member.gender == "M" else "Sister"
                return f"{prefix} {member.last_name}"
            elif transform == "casual":
                # First name only (uses display_name: AKA or first word)
                return member.display_name
            elif transform == "full":
                # "FirstName LastName"
                return member.full_name
            else:
                # Unknown transform, default to casual
                return member.display_name

        # Date transforms (for variables other than smart_date)
        elif var_name == "date" and appointment:
            if transform == "short":
                return appointment.date_obj.strftime("%b %d")
            elif transform == "long":
                return appointment.date_obj.strftime("%A, %B %d, %Y")
            else:
                # Default date format from config
                return appointment.date_obj.strftime(config.DISPLAY_DATE_FORMAT)

        # Unknown variable/transform
        return f"{{{var_name}}}"  # Return unchanged

    def _expand_simple_variables(self, text: str, member, appointment, extra_vars: Dict) -> str:
        """Expand {simple_variable} using standard substitution"""
        import config

        # Build context dictionary
        context = {
            'first_name': member.display_name,
            'last_name': member.last_name,
            'member_name': member.display_name,  # For backward compatibility
            'full_name': member.full_name,
        }

        # Add appointment/assignment variables if present
        if appointment:
            context['date'] = appointment.date_obj.strftime(config.DISPLAY_DATE_FORMAT)

            # Check if it's a prayer assignment or appointment
            if hasattr(appointment, 'prayer_type'):
                context['prayer_type'] = appointment.prayer_type.lower()
            elif hasattr(appointment, 'appointment_type'):
                context['appointment_type'] = appointment.appointment_type
                # Use local timezone for time display (HOME_TIMEZONE for SMS messages)
                context['time'] = appointment.time_local(config.HOME_TIMEZONE)
                context['conductor'] = appointment.conductor

        # Add extra variables
        context.update(extra_vars)

        # Use Python's format method
        try:
            return text.format(**context)
        except KeyError as e:
            # Variable not found, return text as-is
            return text
