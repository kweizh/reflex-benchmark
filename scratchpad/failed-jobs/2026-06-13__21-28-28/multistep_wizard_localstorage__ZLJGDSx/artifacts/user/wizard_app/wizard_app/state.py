"""Reflex state for the wizard with LocalStorage persistence."""

import json

import reflex as rx

from .validation import validate_step, validate_wizard_data

STEPS = ["profile", "address", "preferences", "review"]

DEFAULT_DRAFT = json.dumps(
    {
        "full_name": "",
        "email": "",
        "street": "",
        "city": "",
        "postal_code": "",
        "newsletter": False,
        "theme": "",
        "language": "",
        "current_step": "profile",
    }
)


class WizardState(rx.State):
    """State for the multi-step registration wizard."""

    # LocalStorage var - stored under the key "wizard_draft" in the browser
    wizard_draft: rx.LocalStorage = rx.LocalStorage(DEFAULT_DRAFT, name="wizard_draft")

    # Parsed fields (hydrated from wizard_draft)
    full_name: str = ""
    email: str = ""
    street: str = ""
    city: str = ""
    postal_code: str = ""
    newsletter: bool = False
    theme: str = ""
    language: str = ""
    current_step: str = "profile"

    # Validation errors for the current step
    errors: dict[str, str] = {}

    # Whether submission succeeded
    submitted: bool = False

    # -- Explicit setters for form fields --

    @rx.event
    def set_full_name(self, value: str):
        self.full_name = value

    @rx.event
    def set_email(self, value: str):
        self.email = value

    @rx.event
    def set_street(self, value: str):
        self.street = value

    @rx.event
    def set_city(self, value: str):
        self.city = value

    @rx.event
    def set_postal_code(self, value: str):
        self.postal_code = value

    @rx.event
    def set_newsletter(self, checked: bool):
        self.newsletter = checked

    @rx.event
    def set_theme(self, value: str):
        self.theme = value

    @rx.event
    def set_language(self, value: str):
        self.language = value

    # -- Core logic --

    @rx.event
    def hydrate_from_draft(self):
        """Load field values from the LocalStorage JSON string."""
        try:
            data = json.loads(self.wizard_draft)
        except (json.JSONDecodeError, TypeError):
            data = {}
        self.full_name = data.get("full_name", "")
        self.email = data.get("email", "")
        self.street = data.get("street", "")
        self.city = data.get("city", "")
        self.postal_code = data.get("postal_code", "")
        self.newsletter = data.get("newsletter", False)
        self.theme = data.get("theme", "")
        self.language = data.get("language", "")
        self.current_step = data.get("current_step", "profile")

    def _save_to_draft(self):
        """Persist current field values into the LocalStorage JSON string."""
        data = {
            "full_name": self.full_name,
            "email": self.email,
            "street": self.street,
            "city": self.city,
            "postal_code": self.postal_code,
            "newsletter": self.newsletter,
            "theme": self.theme,
            "language": self.language,
            "current_step": self.current_step,
        }
        self.wizard_draft = json.dumps(data)

    @rx.event
    def set_step(self, step: str):
        """Navigate to a specific step (used on page load to restore position)."""
        if step in STEPS:
            self.current_step = step
            self._save_to_draft()

    @rx.event
    def next_step(self):
        """Validate current step fields and advance to the next step."""
        step_errors = validate_step(self.current_step, self._current_data())
        if step_errors:
            self.errors = step_errors
            return
        self.errors = {}
        idx = STEPS.index(self.current_step)
        if idx < len(STEPS) - 1:
            self.current_step = STEPS[idx + 1]
        self._save_to_draft()

    @rx.event
    def prev_step(self):
        """Go back to the previous step."""
        self.errors = {}
        idx = STEPS.index(self.current_step)
        if idx > 0:
            self.current_step = STEPS[idx - 1]
        self._save_to_draft()

    @rx.event
    def submit(self):
        """Validate all fields and insert into the database."""
        all_errors = validate_wizard_data(self._current_data())
        if all_errors:
            self.errors = all_errors
            return
        self.errors = {}

        from datetime import datetime, timezone

        from .model import Submission

        with rx.session() as session:
            submission = Submission(
                full_name=self.full_name.strip(),
                email=self.email.strip(),
                street=self.street.strip(),
                city=self.city.strip(),
                postal_code=self.postal_code.strip(),
                newsletter=self.newsletter,
                theme=self.theme,
                language=self.language,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            session.add(submission)
            session.commit()
            session.refresh(submission)

        self.submitted = True

    def _current_data(self) -> dict:
        """Return a dict of the current form data."""
        return {
            "full_name": self.full_name,
            "email": self.email,
            "street": self.street,
            "city": self.city,
            "postal_code": self.postal_code,
            "newsletter": self.newsletter,
            "theme": self.theme,
            "language": self.language,
        }

    @rx.event
    def goto_step(self, step: str):
        """Navigate to a specific step (used by the review page)."""
        if step in STEPS:
            self.current_step = step
            self._save_to_draft()