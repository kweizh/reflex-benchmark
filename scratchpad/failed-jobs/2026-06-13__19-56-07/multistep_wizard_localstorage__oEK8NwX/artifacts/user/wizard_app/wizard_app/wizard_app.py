import datetime
import re
from typing import Dict, Any, List, Optional

import reflex as rx
from rxconfig import config

from fastapi import FastAPI, APIRouter, Response, status
from pydantic import BaseModel

# --- Database Model ---

class Submission(rx.Model, table=True):
    full_name: str
    email: str
    street: str
    city: str
    postal_code: str
    newsletter: bool
    theme: str
    language: str
    created_at: str

# --- Validation Logic ---

def get_validation_errors(data: Dict[str, Any]) -> Dict[str, str]:
    errors = {}
    
    full_name = str(data.get("full_name", "")).strip()
    if not (1 <= len(full_name) <= 100):
        errors["full_name"] = "Full name must be 1-100 characters."
    
    email = str(data.get("email", ""))
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors["email"] = "Invalid email address."
        
    street = str(data.get("street", "").strip())
    if not (1 <= len(street) <= 200):
        errors["street"] = "Street must be 1-200 characters."
        
    city = str(data.get("city", "").strip())
    if not (1 <= len(city) <= 100):
        errors["city"] = "City must be 1-100 characters."
        
    postal_code = str(data.get("postal_code", ""))
    if not (len(postal_code) == 5 and postal_code.isdigit()):
        errors["postal_code"] = "Postal code must be exactly 5 digits."
        
    newsletter = data.get("newsletter")
    if not isinstance(newsletter, bool):
        errors["newsletter"] = "Newsletter must be a boolean."
        
    theme = data.get("theme")
    if theme not in ["light", "dark"]:
        errors["theme"] = "Theme must be light or dark."
        
    language = str(data.get("language", ""))
    if not (len(language) == 2 and language.islower() and language.isalpha()):
        errors["language"] = "Language must be 2 lowercase letters."
        
    return errors

# --- API Router ---

api_router = APIRouter()

class SubmissionRequest(BaseModel):
    full_name: Any
    email: Any
    street: Any
    city: Any
    postal_code: Any
    newsletter: Any
    theme: Any
    language: Any

@api_router.post("/api/wizard/submit")
async def api_submit(req: SubmissionRequest, response: Response):
    data = req.dict()
    errors = get_validation_errors(data)
    
    if errors:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"errors": errors}

    with rx.session() as session:
        submission = Submission(
            full_name=data["full_name"],
            email=data["email"],
            street=data["street"],
            city=data["city"],
            postal_code=data["postal_code"],
            newsletter=data["newsletter"],
            theme=data["theme"],
            language=data["language"],
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        return {"id": submission.id}

# --- State ---

class State(rx.State):
    wizard_draft: Dict[str, Any] = rx.LocalStorage(
        {
            "full_name": "",
            "email": "",
            "street": "",
            "city": "",
            "postal_code": "",
            "newsletter": False,
            "theme": "light",
            "language": "en",
            "current_step": "profile",
        },
        name="wizard_draft",
    )
    
    error_messages: Dict[str, str] = {}

    @rx.var
    def step_num(self) -> str:
        step = self.router.params.get("step", "profile")
        return {"profile": "1", "address": "2", "preferences": "3", "review": "4"}.get(step, "1")

    def set_val(self, key: str, val: Any):
        self.wizard_draft[key] = val

    def set_newsletter(self, val: bool):
        self.wizard_draft["newsletter"] = val

    def validate_step(self, step: str) -> bool:
        self.error_messages = {}
        data = self.wizard_draft
        all_errors = get_validation_errors(data)
        
        if step == "profile":
            if "full_name" in all_errors: self.error_messages["full_name"] = all_errors["full_name"]
            if "email" in all_errors: self.error_messages["email"] = all_errors["email"]
        elif step == "address":
            if "street" in all_errors: self.error_messages["street"] = all_errors["street"]
            if "city" in all_errors: self.error_messages["city"] = all_errors["city"]
            if "postal_code" in all_errors: self.error_messages["postal_code"] = all_errors["postal_code"]
        elif step == "preferences":
            if "newsletter" in all_errors: self.error_messages["newsletter"] = all_errors["newsletter"]
            if "theme" in all_errors: self.error_messages["theme"] = all_errors["theme"]
            if "language" in all_errors: self.error_messages["language"] = all_errors["language"]
            
        return len(self.error_messages) == 0

    def next_step(self):
        current_step = self.router.params.get("step", "profile")
        if self.validate_step(current_step):
            if current_step == "profile":
                new_step = "address"
            elif current_step == "address":
                new_step = "preferences"
            elif current_step == "preferences":
                new_step = "review"
            else:
                return
            self.wizard_draft["current_step"] = new_step
            return rx.redirect(f"/wizard/{new_step}")

    def prev_step(self):
        current_step = self.router.params.get("step", "profile")
        if current_step == "address":
            new_step = "profile"
        elif current_step == "preferences":
            new_step = "address"
        elif current_step == "review":
            new_step = "preferences"
        else:
            return
        self.wizard_draft["current_step"] = new_step
        return rx.redirect(f"/wizard/{new_step}")

    def submit_form(self):
        # Validate all steps
        all_errors = get_validation_errors(self.wizard_draft)
        if all_errors:
            self.error_messages = all_errors
            return rx.window_alert("Please fix errors before submitting.")
        
        with rx.session() as session:
            submission = Submission(
                full_name=self.wizard_draft["full_name"],
                email=self.wizard_draft["email"],
                street=self.wizard_draft["street"],
                city=self.wizard_draft["city"],
                postal_code=self.wizard_draft["postal_code"],
                newsletter=self.wizard_draft["newsletter"],
                theme=self.wizard_draft["theme"],
                language=self.wizard_draft["language"],
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            session.add(submission)
            session.commit()
            session.refresh(submission)
            return rx.window_alert(f"Submitted successfully! ID: {submission.id}")

    def on_load_index(self):
        return rx.redirect(f"/wizard/{self.wizard_draft['current_step']}")

# --- UI Components ---

def input_field(label, key, placeholder="", type="text"):
    return rx.vstack(
        rx.text(label),
        rx.input(
            placeholder=placeholder,
            value=State.wizard_draft[key].to(str),
            on_change=lambda v: State.set_val(key, v),
            width="100%"
        ),
        rx.cond(
            State.error_messages.contains(key),
            rx.text(State.error_messages[key], color="red", size="2"),
        ),
        align_items="start",
        width="100%"
    )

def profile_step():
    return rx.vstack(
        input_field("Full Name", "full_name", "John Doe"),
        input_field("Email", "email", "john@example.com"),
        rx.button("Next", on_click=State.next_step),
        width="100%"
    )

def address_step():
    return rx.vstack(
        input_field("Street", "street", "123 Main St"),
        input_field("City", "city", "New York"),
        input_field("Postal Code", "postal_code", "12345"),
        rx.hstack(
            rx.button("Previous", on_click=State.prev_step),
            rx.button("Next", on_click=State.next_step),
            spacing="2"
        ),
        width="100%"
    )

def preferences_step():
    return rx.vstack(
        rx.hstack(
            rx.text("Newsletter"),
            rx.checkbox(
                checked=State.wizard_draft["newsletter"],
                on_change=State.set_newsletter
            ),
            spacing="2"
        ),
        rx.text("Theme"),
        rx.select(
            ["light", "dark"],
            value=State.wizard_draft["theme"],
            on_change=lambda v: State.set_val("theme", v),
            width="100%"
        ),
        input_field("Language (ISO 639-1)", "language", "en"),
        rx.hstack(
            rx.button("Previous", on_click=State.prev_step),
            rx.button("Next", on_click=State.next_step),
            spacing="2"
        ),
        width="100%"
    )

def review_step():
    return rx.vstack(
        rx.heading("Review your data", size="4"),
        rx.text("Full Name: ", State.wizard_draft["full_name"]),
        rx.text("Email: ", State.wizard_draft["email"]),
        rx.text("Street: ", State.wizard_draft["street"]),
        rx.text("City: ", State.wizard_draft["city"]),
        rx.text("Postal Code: ", State.wizard_draft["postal_code"]),
        rx.text("Newsletter: ", State.wizard_draft["newsletter"].to(str)),
        rx.text("Theme: ", State.wizard_draft["theme"]),
        rx.text("Language: ", State.wizard_draft["language"]),
        rx.hstack(
            rx.button("Previous", on_click=State.prev_step),
            rx.button("Submit", on_click=State.submit_form),
            spacing="2"
        ),
        width="100%"
    )

@rx.page(route="/wizard/[step]")
def wizard_page():
    step = State.router.params.get("step", "profile")
    
    indicator = rx.text("Step ", State.step_num, " of 4")
    
    return rx.center(
        rx.vstack(
            indicator,
            rx.cond(
                step == "profile",
                profile_step(),
                rx.cond(
                    step == "address",
                    address_step(),
                    rx.cond(
                        step == "preferences",
                        preferences_step(),
                        review_step()
                    )
                )
            ),
            spacing="4",
            padding="4",
            border="1px solid #ccc",
            border_radius="md",
            width="400px"
        ),
        min_height="100vh"
    )

@rx.page(route="/", on_load=State.on_load_index)
def index():
    return rx.center(rx.text("Redirecting..."))

api_app = FastAPI()
api_app.include_router(api_router)

app = rx.App(api_transformer=api_app)
