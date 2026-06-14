import reflex as rx
from sqlmodel import Field
from typing import Optional
from datetime import datetime, timezone
import json
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

class WizardState(rx.State):
    wizard_draft: str = rx.LocalStorage(
        json.dumps({
            "full_name": "",
            "email": "",
            "street": "",
            "city": "",
            "postal_code": "",
            "newsletter": False,
            "theme": "",
            "language": "",
            "current_step": "profile"
        }),
        name="wizard_draft"
    )

    def get_draft(self) -> dict:
        try:
            return json.loads(self.wizard_draft)
        except Exception:
            return {
                "full_name": "",
                "email": "",
                "street": "",
                "city": "",
                "postal_code": "",
                "newsletter": False,
                "theme": "",
                "language": "",
                "current_step": "profile"
            }

    def update_draft(self, key: str, value: any):
        draft = self.get_draft()
        draft[key] = value
        self.wizard_draft = json.dumps(draft)
        
    def set_full_name(self, value: str):
        self.update_draft("full_name", value)
        
    def set_email(self, value: str):
        self.update_draft("email", value)
        
    def set_street(self, value: str):
        self.update_draft("street", value)
        
    def set_city(self, value: str):
        self.update_draft("city", value)
        
    def set_postal_code(self, value: str):
        self.update_draft("postal_code", value)
        
    def set_newsletter(self, value: bool):
        self.update_draft("newsletter", value)
        
    def set_theme(self, value: str):
        self.update_draft("theme", value)
        
    def set_language(self, value: str):
        self.update_draft("language", value)
        
    @rx.var
    def draft_full_name(self) -> str:
        return self.get_draft().get("full_name", "")
        
    @rx.var
    def draft_email(self) -> str:
        return self.get_draft().get("email", "")
        
    @rx.var
    def draft_street(self) -> str:
        return self.get_draft().get("street", "")
        
    @rx.var
    def draft_city(self) -> str:
        return self.get_draft().get("city", "")
        
    @rx.var
    def draft_postal_code(self) -> str:
        return self.get_draft().get("postal_code", "")
        
    @rx.var
    def draft_newsletter(self) -> bool:
        return self.get_draft().get("newsletter", False)
        
    @rx.var
    def draft_theme(self) -> str:
        return self.get_draft().get("theme", "")
        
    @rx.var
    def draft_language(self) -> str:
        return self.get_draft().get("language", "")

    errors: dict[str, str] = {}
    
    def validate_profile(self):
        self.errors = {}
        draft = self.get_draft()
        full_name = draft.get("full_name", "").strip()
        email = draft.get("email", "")
        
        if not (1 <= len(full_name) <= 100):
            self.errors["full_name"] = "Full name must be between 1 and 100 characters."
            
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            self.errors["email"] = "Invalid email format."
            
        if not self.errors:
            self.update_draft("current_step", "address")
            return rx.redirect("/wizard/address")
            
    def validate_address(self):
        self.errors = {}
        draft = self.get_draft()
        street = draft.get("street", "").strip()
        city = draft.get("city", "").strip()
        postal_code = draft.get("postal_code", "")
        
        if not (1 <= len(street) <= 200):
            self.errors["street"] = "Street must be between 1 and 200 characters."
            
        if not (1 <= len(city) <= 100):
            self.errors["city"] = "City must be between 1 and 100 characters."
            
        if not (len(postal_code) == 5 and postal_code.isdigit()):
            self.errors["postal_code"] = "Postal code must be exactly 5 digits."
            
        if not self.errors:
            self.update_draft("current_step", "preferences")
            return rx.redirect("/wizard/preferences")
            
    def validate_preferences(self):
        self.errors = {}
        draft = self.get_draft()
        theme = draft.get("theme", "")
        language = draft.get("language", "")
        
        if theme not in ["light", "dark"]:
            self.errors["theme"] = "Theme must be light or dark."
            
        if not (len(language) == 2 and language.islower() and language.isalpha()):
            self.errors["language"] = "Language must be exactly two lowercase letters."
            
        if not self.errors:
            self.update_draft("current_step", "review")
            return rx.redirect("/wizard/review")

def perform_validation(data: dict) -> dict:
    errors = {}
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "")
    street = data.get("street", "").strip()
    city = data.get("city", "").strip()
    postal_code = data.get("postal_code", "")
    newsletter = data.get("newsletter", False)
    theme = data.get("theme", "")
    language = data.get("language", "")

    if not (1 <= len(full_name) <= 100):
        errors["full_name"] = "Full name must be between 1 and 100 characters."
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors["email"] = "Invalid email format."
    if not (1 <= len(street) <= 200):
        errors["street"] = "Street must be between 1 and 200 characters."
    if not (1 <= len(city) <= 100):
        errors["city"] = "City must be between 1 and 100 characters."
    if not (len(postal_code) == 5 and postal_code.isdigit()):
        errors["postal_code"] = "Postal code must be exactly 5 digits."
    if theme not in ["light", "dark"]:
        errors["theme"] = "Theme must be light or dark."
    if not (len(language) == 2 and language.islower() and language.isalpha()):
        errors["language"] = "Language must be exactly two lowercase letters."
        
    return errors

api = FastAPI()

@api.post("/submit")
async def submit_endpoint(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"errors": {"body": "Invalid JSON"}}, status_code=400)
        
    errors = perform_validation(data)
    if errors:
        return JSONResponse({"errors": errors}, status_code=400)
        
    with rx.session() as session:
        sub = Submission(
            full_name=data.get("full_name", "").strip(),
            email=data.get("email", ""),
            street=data.get("street", "").strip(),
            city=data.get("city", "").strip(),
            postal_code=data.get("postal_code", ""),
            newsletter=bool(data.get("newsletter", False)),
            theme=data.get("theme", ""),
            language=data.get("language", ""),
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return {"id": sub.id}

def api_transformer(app):
    app.mount("/api/wizard", api)
    return app

def profile_step():
    return rx.vstack(
        rx.heading("Step 1 of 4"),
        rx.input(placeholder="Full Name", value=WizardState.draft_full_name, on_change=WizardState.set_full_name),
        rx.cond(WizardState.errors.contains("full_name"), rx.text(WizardState.errors["full_name"], color="red")),
        rx.input(placeholder="Email", value=WizardState.draft_email, on_change=WizardState.set_email),
        rx.cond(WizardState.errors.contains("email"), rx.text(WizardState.errors["email"], color="red")),
        rx.button("Next", on_click=WizardState.validate_profile)
    )

def address_step():
    return rx.vstack(
        rx.heading("Step 2 of 4"),
        rx.input(placeholder="Street", value=WizardState.draft_street, on_change=WizardState.set_street),
        rx.cond(WizardState.errors.contains("street"), rx.text(WizardState.errors["street"], color="red")),
        rx.input(placeholder="City", value=WizardState.draft_city, on_change=WizardState.set_city),
        rx.cond(WizardState.errors.contains("city"), rx.text(WizardState.errors["city"], color="red")),
        rx.input(placeholder="Postal Code", value=WizardState.draft_postal_code, on_change=WizardState.set_postal_code),
        rx.cond(WizardState.errors.contains("postal_code"), rx.text(WizardState.errors["postal_code"], color="red")),
        rx.button("Next", on_click=WizardState.validate_address)
    )

def preferences_step():
    return rx.vstack(
        rx.heading("Step 3 of 4"),
        rx.checkbox("Newsletter", checked=WizardState.draft_newsletter, on_change=WizardState.set_newsletter),
        rx.select(["light", "dark"], placeholder="Theme", value=WizardState.draft_theme, on_change=WizardState.set_theme),
        rx.cond(WizardState.errors.contains("theme"), rx.text(WizardState.errors["theme"], color="red")),
        rx.input(placeholder="Language", value=WizardState.draft_language, on_change=WizardState.set_language),
        rx.cond(WizardState.errors.contains("language"), rx.text(WizardState.errors["language"], color="red")),
        rx.button("Next", on_click=WizardState.validate_preferences)
    )

class SubmissionState(rx.State):
    submission_id: str = ""
    error_message: str = ""
    
    async def submit(self):
        draft_str = await self.get_state(WizardState)
        draft = json.loads(draft_str.wizard_draft)
        
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post("http://localhost:8000/api/wizard/submit", json=draft)
            if resp.status_code == 200:
                self.submission_id = str(resp.json().get("id"))
                self.error_message = ""
            else:
                self.error_message = str(resp.json().get("errors"))

def review_step():
    return rx.vstack(
        rx.heading("Step 4 of 4"),
        rx.text("Full Name: ", WizardState.draft_full_name),
        rx.text("Email: ", WizardState.draft_email),
        rx.text("Street: ", WizardState.draft_street),
        rx.text("City: ", WizardState.draft_city),
        rx.text("Postal Code: ", WizardState.draft_postal_code),
        rx.text("Newsletter: ", WizardState.draft_newsletter.to_string()),
        rx.text("Theme: ", WizardState.draft_theme),
        rx.text("Language: ", WizardState.draft_language),
        rx.button("Submit", on_click=SubmissionState.submit),
        rx.cond(SubmissionState.submission_id != "", rx.text("Submitted with ID: ", SubmissionState.submission_id)),
        rx.cond(SubmissionState.error_message != "", rx.text("Errors: ", SubmissionState.error_message, color="red"))
    )

@rx.page(route="/wizard/[step]")
def wizard_page():
    step = rx.State.router.page.params.get("step", "profile")
    return rx.vstack(
        rx.match(
            step,
            ("profile", profile_step()),
            ("address", address_step()),
            ("preferences", preferences_step()),
            ("review", review_step()),
            profile_step()
        )
    )

app = rx.App(api_transformer=api_transformer)
app.add_page(wizard_page)
