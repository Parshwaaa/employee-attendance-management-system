"""Input validation helpers shared by the managers and the GUI.

Every function either returns a cleaned value or raises ValidationError with
a message that is safe to show directly to the user.
"""

import re
from datetime import date, datetime

from config import DATE_FORMAT


class ValidationError(ValueError):
    """Raised when user input is missing or invalid."""


_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")


def clean_text(value):
    """Strip the text and collapse repeated spaces."""
    return " ".join(str(value).split())


def validate_name(value):
    name = clean_text(value)
    if not name:
        raise ValidationError("Name cannot be empty.")
    if not 2 <= len(name) <= 60:
        raise ValidationError("Name must be between 2 and 60 characters.")
    if not _NAME_PATTERN.match(name):
        raise ValidationError("Name may only contain letters, spaces, dots, "
                              "apostrophes and hyphens.")
    return name


def validate_required_text(value, label, max_length=40):
    text = clean_text(value)
    if not text:
        raise ValidationError(f"{label} cannot be empty.")
    if len(text) > max_length:
        raise ValidationError(f"{label} must be at most {max_length} characters.")
    return text


def validate_email(value):
    email = str(value).strip().lower()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationError("Please enter a valid email address "
                              "(for example name@company.com).")
    return email


def parse_date(value, label="Date", allow_future=True):
    """Return the date as a normalised YYYY-MM-DD string."""
    text = str(value).strip()
    try:
        parsed = datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise ValidationError(f"{label} must be a real date in YYYY-MM-DD "
                              f"format (for example 2026-04-15).") from None
    if not allow_future and parsed > date.today():
        raise ValidationError(f"{label} cannot be in the future.")
    return parsed.strftime(DATE_FORMAT)


def parse_optional_date(value, label="Date"):
    """Like parse_date, but a blank value means 'no date' (None)."""
    if value is None or not str(value).strip():
        return None
    return parse_date(value, label)


def validate_date_range(start, end, label="Date range"):
    """ISO date strings compare correctly as plain text."""
    if start and end and start > end:
        raise ValidationError(f"{label}: the start date must not be after the end date.")


def validate_choice(value, options, label):
    if value not in options:
        raise ValidationError(f"{label} must be one of: {', '.join(options)}.")
    return value


def parse_percentage(value, label="Percentage"):
    try:
        number = float(str(value).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a number.") from None
    if not 0 <= number <= 100:
        raise ValidationError(f"{label} must be between 0 and 100.")
    return number


def validate_thresholds(low, high):
    if low >= high:
        raise ValidationError("The low threshold must be smaller than the high threshold.")
