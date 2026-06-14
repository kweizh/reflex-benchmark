"""Wizard application - dynamic route page and FastAPI endpoint."""

import json
from datetime import datetime, timezone

import reflex as rx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .model import Submission
from .state import STEPS, WizardState
from .validation import validate_wizard_data

# -- FastAPI sub-app for the /api/wizard/submit endpoint -------------------

api_app = FastAPI()


@api_app.post("/wizard/submit")
async def wizard_submit(body: dict):
    """Validate and persist a submission via HTTP POST."""
    errors = validate_wizard_data(body)
    if errors:
        return JSONResponse(status_code=400, content={"errors": errors})

    with rx.session() as session:
        submission = Submission(
            full_name=body["full_name"].strip(),
            email=body["email"].strip(),
            street=body["street"].strip(),
            city=body["city"].strip(),
            postal_code=body["postal_code"].strip(),
            newsletter=body["newsletter"],
            theme=body["theme"],
            language=body["language"],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        new_id = submission.id

    return {"id": new_id}


# -- UI helpers -------------------------------------------------------------

STEP_NUMBERS = {s: i + 1 for i, s in enumerate(STEPS)}


def step_indicator(current_step: str) -> rx.Component:
    """Render the 'Step N of 4' indicator."""
    return rx.text(f"Step {STEP_NUMBERS[current_step]} of 4", font_size="lg", font_weight="bold")


# -- Step pages -------------------------------------------------------------


def profile_step() -> rx.Component:
    """Step 1 - collect full_name and email."""
    return rx.vstack(
        step_indicator("profile"),
        rx.heading("Profile", size="3"),
        rx.input(
            placeholder="Full Name",
            value=WizardState.full_name,
            on_change=WizardState.set_full_name,
        ),
        rx.cond(
            WizardState.errors.get("full_name", "") != "",
            rx.text(WizardState.errors.get("full_name", ""), color="red"),
        ),
        rx.input(
            placeholder="Email",
            value=WizardState.email,
            on_change=WizardState.set_email,
        ),
        rx.cond(
            WizardState.errors.get("email", "") != "",
            rx.text(WizardState.errors.get("email", ""), color="red"),
        ),
        rx.hstack(
            rx.button("Next", on_click=WizardState.next_step),
        ),
        spacing="4",
        align="stretch",
        padding="4",
    )


def address_step() -> rx.Component:
    """Step 2 - collect street, city, postal_code."""
    return rx.vstack(
        step_indicator("address"),
        rx.heading("Address", size="3"),
        rx.input(
            placeholder="Street",
            value=WizardState.street,
            on_change=WizardState.set_street,
        ),
        rx.cond(
            WizardState.errors.get("street", "") != "",
            rx.text(WizardState.errors.get("street", ""), color="red"),
        ),
        rx.input(
            placeholder="City",
            value=WizardState.city,
            on_change=WizardState.set_city,
        ),
        rx.cond(
            WizardState.errors.get("city", "") != "",
            rx.text(WizardState.errors.get("city", ""), color="red"),
        ),
        rx.input(
            placeholder="Postal Code",
            value=WizardState.postal_code,
            on_change=WizardState.set_postal_code,
        ),
        rx.cond(
            WizardState.errors.get("postal_code", "") != "",
            rx.text(WizardState.errors.get("postal_code", ""), color="red"),
        ),
        rx.hstack(
            rx.button("Back", on_click=WizardState.prev_step),
            rx.button("Next", on_click=WizardState.next_step),
        ),
        spacing="4",
        align="stretch",
        padding="4",
    )


def preferences_step() -> rx.Component:
    """Step 3 - collect newsletter, theme, language."""
    return rx.vstack(
        step_indicator("preferences"),
        rx.heading("Preferences", size="3"),
        rx.hstack(
            rx.text("Newsletter"),
            rx.switch(
                checked=WizardState.newsletter,
                on_change=WizardState.set_newsletter,
            ),
        ),
        rx.cond(
            WizardState.errors.get("newsletter", "") != "",
            rx.text(WizardState.errors.get("newsletter", ""), color="red"),
        ),
        rx.select(
            ["light", "dark"],
            value=WizardState.theme,
            on_change=WizardState.set_theme,
            placeholder="Theme",
        ),
        rx.cond(
            WizardState.errors.get("theme", "") != "",
            rx.text(WizardState.errors.get("theme", ""), color="red"),
        ),
        rx.input(
            placeholder="Language (e.g. en)",
            value=WizardState.language,
            on_change=WizardState.set_language,
        ),
        rx.cond(
            WizardState.errors.get("language", "") != "",
            rx.text(WizardState.errors.get("language", ""), color="red"),
        ),
        rx.hstack(
            rx.button("Back", on_click=WizardState.prev_step),
            rx.button("Next", on_click=WizardState.next_step),
        ),
        spacing="4",
        align="stretch",
        padding="4",
    )


def review_step() -> rx.Component:
    """Step 4 - summary and submit."""
    return rx.vstack(
        step_indicator("review"),
        rx.heading("Review", size="3"),
        rx.text(f"Full Name: {WizardState.full_name}"),
        rx.text(f"Email: {WizardState.email}"),
        rx.text(f"Street: {WizardState.street}"),
        rx.text(f"City: {WizardState.city}"),
        rx.text(f"Postal Code: {WizardState.postal_code}"),
        rx.text(f"Newsletter: {WizardState.newsletter}"),
        rx.text(f"Theme: {WizardState.theme}"),
        rx.text(f"Language: {WizardState.language}"),
        rx.hstack(
            rx.button("Back", on_click=WizardState.prev_step),
            rx.button("Submit", on_click=WizardState.submit),
        ),
        rx.cond(
            WizardState.submitted,
            rx.text("Submission successful!", color="green"),
        ),
        spacing="4",
        align="stretch",
        padding="4",
    )


# -- Dynamic route page -----------------------------------------------------


def wizard_page() -> rx.Component:
    """Render the appropriate step based on the URL segment."""
    return rx.box(
        rx.cond(WizardState.submitted, rx.text("Submission successful!", font_size="xl")),
        rx.cond(
            WizardState.current_step == "profile",
            profile_step(),
        ),
        rx.cond(
            WizardState.current_step == "address",
            address_step(),
        ),
        rx.cond(
            WizardState.current_step == "preferences",
            preferences_step(),
        ),
        rx.cond(
            WizardState.current_step == "review",
            review_step(),
        ),
        max_width="600px",
        margin="0 auto",
        padding="4",
    )


def on_load_wizard() -> list:
    """On page load, hydrate state from LocalStorage and set step from URL."""
    return [WizardState.hydrate_from_draft, WizardState.set_step(WizardState.step)]


# -- App setup --------------------------------------------------------------

app = rx.App(api_transformer=api_app)
app.add_page(
    wizard_page,
    route="/wizard/[step]",
    title="Wizard",
    on_load=on_load_wizard,
)