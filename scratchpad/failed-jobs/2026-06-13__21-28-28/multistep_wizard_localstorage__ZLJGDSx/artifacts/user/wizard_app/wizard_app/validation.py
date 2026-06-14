"""Shared validation logic for the wizard form."""

import re

# Validation rules
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
POSTAL_CODE_REGEX = re.compile(r"^\d{5}$")
LANGUAGE_REGEX = re.compile(r"^[a-z]{2}$")


def validate_wizard_data(data: dict) -> dict[str, str]:
    """Validate all wizard form fields.

    Args:
        data: A dict with keys full_name, email, street, city, postal_code,
              newsletter, theme, language.

    Returns:
        A dict of {field_name: error_message} for every invalid field.
        Empty dict means all fields are valid.
    """
    errors: dict[str, str] = {}

    # full_name: 1 to 100 characters after stripping whitespace
    full_name = data.get("full_name", "")
    if not isinstance(full_name, str) or not (1 <= len(full_name.strip()) <= 100):
        errors["full_name"] = "Must be 1-100 characters after stripping whitespace."

    # email: must match regex
    email = data.get("email", "")
    if not isinstance(email, str) or not EMAIL_REGEX.match(email):
        errors["email"] = "Must be a valid email address."

    # street: 1 to 200 characters after stripping whitespace
    street = data.get("street", "")
    if not isinstance(street, str) or not (1 <= len(street.strip()) <= 200):
        errors["street"] = "Must be 1-200 characters after stripping whitespace."

    # city: 1 to 100 characters after stripping whitespace
    city = data.get("city", "")
    if not isinstance(city, str) or not (1 <= len(city.strip()) <= 100):
        errors["city"] = "Must be 1-100 characters after stripping whitespace."

    # postal_code: exactly 5 ASCII digits
    postal_code = data.get("postal_code", "")
    if not isinstance(postal_code, str) or not POSTAL_CODE_REGEX.match(postal_code):
        errors["postal_code"] = "Must be exactly 5 digits."

    # newsletter: must be boolean
    newsletter = data.get("newsletter")
    if not isinstance(newsletter, bool):
        errors["newsletter"] = "Must be a boolean."

    # theme: one of light or dark
    theme = data.get("theme", "")
    if not isinstance(theme, str) or theme not in ("light", "dark"):
        errors["theme"] = "Must be 'light' or 'dark'."

    # language: exactly two lowercase ASCII letters
    language = data.get("language", "")
    if not isinstance(language, str) or not LANGUAGE_REGEX.match(language):
        errors["language"] = "Must be exactly two lowercase letters."

    return errors


def validate_step(step: str, data: dict) -> dict[str, str]:
    """Validate only the fields relevant to a given wizard step.

    Args:
        step: One of 'profile', 'address', 'preferences'.
        data: The full data dict.

    Returns:
        A dict of {field_name: error_message} for invalid fields in this step.
    """
    step_fields = {
        "profile": ["full_name", "email"],
        "address": ["street", "city", "postal_code"],
        "preferences": ["newsletter", "theme", "language"],
    }
    all_errors = validate_wizard_data(data)
    relevant = step_fields.get(step, [])
    return {k: v for k, v in all_errors.items() if k in relevant}