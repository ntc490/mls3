"""
Smart Template Expander for MLS3
Handles conditional flag-based expansions, smart dates, and random pleasantries
"""
import re
import random
from datetime import date
from typing import Optional, Dict, Any, List


def _join(items: List[str], last_sep: str = ' and ') -> str:
    """'A', 'A and B', 'A, B and C'"""
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + last_sep + items[-1]


def _by_last_name(people) -> List[tuple]:
    """
    [(last_name, [people...])] in order of first appearance, men first within
    the whole list so a couple reads "David and Lisa", "Brother and Sister".
    """
    groups = {}
    for p in sorted(people, key=lambda p: p.gender != 'M'):
        groups.setdefault(p.last_name, []).append(p)
    return list(groups.items())


def formal_names(people) -> str:
    """'Brother Smith', 'Brother and Sister Smith', 'Brother Smith and Sister Jones'"""
    return _join([
        f"{_join(['Brother' if p.gender == 'M' else 'Sister' for p in group])} {last}"
        for last, group in _by_last_name(people)
    ])


def casual_names(people) -> str:
    """'David', 'David & Lisa'"""
    ordered = [p for _, group in _by_last_name(people) for p in group]
    return _join([p.display_name for p in ordered], ' & ')


def full_names(people) -> str:
    """'David Smith', 'David and Lisa Smith', 'David Smith and Lisa Jones'"""
    if len(people) == 1:
        return people[0].full_name
    return _join([
        f"{_join([p.aka or p.first_name for p in group])} {last}"
        for last, group in _by_last_name(people)
    ])


def greeting(people, flag: str = 'blue') -> str:
    """How a message opens to these people - formal if any has the flag"""
    if any(p.has_flag(flag) for p in people):
        return formal_names(people)
    return casual_names(people)


class SmartTemplateExpander:
    """
    Expands message templates with smart variables.

    Supported syntax:
    - {variable|flag?transform:transform} - Conditional based on member flag
      (true if any of the people addressed has the flag)
    - {smart_date} - Today/tomorrow/formatted date
    - {random:list_name} - Random selection from list
    - {simple_variable} - Standard variable substitution
    - {he} {him} {his} - Pronouns for the member, from their recorded gender.
      In a _parent template the member is the child being talked about.

    Names ({name}, {first_name}, {full_name}...) cover everyone addressed,
    which is just the member unless a list of people is given - the heads of a
    household, say - in which case they read "David and Lisa Smith".
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

    def expand(self, template_str: str, member, appointment=None,
               addressees=None, **kwargs) -> str:
        """
        Expand template with all smart variables.

        Args:
            template_str: Raw template string
            member: Member object
            appointment: Optional appointment/assignment object (for dates)
            addressees: Optional list of Members the message names; defaults
                to [member]
            **kwargs: Additional simple variables (e.g., conductor="Bishop")

        Returns:
            Fully expanded message string
        """
        result = template_str
        people = list(addressees) if addressees else [member]

        # 1. Expand {random:list_name}
        result = self._expand_random_variables(result)

        # 2. Expand {smart_date|flag?transform:transform} or {smart_date}
        if appointment:
            result = self._expand_smart_date_variables(result, people, appointment)

        # 3. Expand {variable|flag?transform:transform}
        result = self._expand_conditional_variables(result, people, appointment, kwargs)

        # 4. Expand remaining {simple_variable}
        result = self._expand_simple_variables(result, member, people, appointment, kwargs)

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

    def _expand_smart_date_variables(self, text: str, people, appointment) -> str:
        """Expand {smart_date} and {smart_date|flag?transform:transform}"""
        def replace_smart_date(match):
            flag = match.group(1)
            true_transform = match.group(2)
            false_transform = match.group(3)

            # Get base smart date value
            smart_date_value = self._calculate_smart_date(appointment)

            # If conditional, apply transform
            if flag and true_transform and false_transform:
                has_flag = any(p.has_flag(flag) for p in people)
                transform = true_transform if has_flag else false_transform
                return self._apply_date_transform(smart_date_value, appointment, transform)

            return smart_date_value

        return self.SMART_DATE_PATTERN.sub(replace_smart_date, text)

    def _appointment_date(self, appointment) -> date:
        """
        Date to display for an appointment/assignment.

        Appointments are stored in UTC, so an evening appointment has already
        rolled over to the next UTC day. Convert to HOME_TIMEZONE so the date
        matches the time shown alongside it. Prayer assignments store a plain
        date and are used as-is.
        """
        import config

        if hasattr(appointment, 'datetime_local'):
            return appointment.datetime_local(config.HOME_TIMEZONE).date()
        return appointment.date_obj

    def _calculate_smart_date(self, appointment) -> str:
        """Calculate smart date string based on appointment date vs today"""
        if not appointment:
            return ""

        appt_date = self._appointment_date(appointment)
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

        appt_date = self._appointment_date(appointment)

        if transform == "short":
            return appt_date.strftime("%b %d")  # "Feb 9"
        elif transform == "long":
            return appt_date.strftime("%A, %B %d, %Y")  # "Sunday, February 9, 2026"
        else:
            # Unknown transform, return base value
            return base_value

    def _expand_conditional_variables(self, text: str, people, appointment, extra_vars: Dict) -> str:
        """Expand {variable|flag?transform:transform}"""
        def replace_conditional(match):
            var_name = match.group(1)
            flag = match.group(2)
            true_transform = match.group(3)
            false_transform = match.group(4)

            has_flag = any(p.has_flag(flag) for p in people)
            transform = true_transform if has_flag else false_transform

            return self._apply_transform(var_name, transform, people, appointment, extra_vars)

        return self.CONDITIONAL_PATTERN.sub(replace_conditional, text)

    def _apply_transform(self, var_name: str, transform: str, people, appointment, extra_vars: Dict) -> str:
        """Apply named transform to variable"""
        import config

        # Name transforms
        if var_name == "name":
            if transform == "formal":
                # "Brother/Sister LastName"
                return formal_names(people)
            elif transform == "casual":
                # First name only (uses display_name: AKA or first word)
                return casual_names(people)
            elif transform == "full":
                # "FirstName LastName"
                return full_names(people)
            else:
                # Unknown transform, default to casual
                return casual_names(people)

        # Date transforms (for variables other than smart_date)
        elif var_name == "date" and appointment:
            appt_date = self._appointment_date(appointment)
            if transform == "short":
                return appt_date.strftime("%b %d")
            elif transform == "long":
                return appt_date.strftime("%A, %B %d, %Y")
            else:
                # Default date format from config
                return appt_date.strftime(config.DISPLAY_DATE_FORMAT)

        # Unknown variable/transform
        return f"{{{var_name}}}"  # Return unchanged

    PRONOUNS = {
        'M': {'he': 'he', 'him': 'him', 'his': 'his'},
        'F': {'he': 'she', 'him': 'her', 'his': 'her'},
    }
    UNKNOWN_PRONOUNS = {'he': 'he/she', 'him': 'him/her', 'his': 'his/her'}

    def _pronouns(self, member) -> Dict[str, str]:
        """{he}, {him} and {his} for the member's recorded gender"""
        return self.PRONOUNS.get(member.gender, self.UNKNOWN_PRONOUNS)

    def _expand_simple_variables(self, text: str, member, people, appointment, extra_vars: Dict) -> str:
        """Expand {simple_variable} using standard substitution"""
        import config

        # Build context dictionary
        context = {
            'first_name': casual_names(people),
            'last_name': _join([last for last, _ in _by_last_name(people)]),
            'member_name': casual_names(people),  # For backward compatibility
            'full_name': full_names(people),
        }
        context.update(self._pronouns(member))

        # Add appointment/assignment variables if present
        if appointment:
            context['date'] = self._appointment_date(appointment).strftime(config.DISPLAY_DATE_FORMAT)

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
