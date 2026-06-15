"""Multi-step registration wizard with LocalStorage persistence."""

import reflex as rx

from rxconfig import config


class WizardState(rx.State):
    """State for the multi-step registration wizard."""

    step: int = 1
    submitted: bool = False

    # LocalStorage-backed draft fields
    name: str = rx.LocalStorage("", name="name")
    email: str = rx.LocalStorage("", name="email")
    address: str = rx.LocalStorage("", name="address")
    city: str = rx.LocalStorage("", name="city")
    password: str = rx.LocalStorage("", name="password")
    confirm_password: str = rx.LocalStorage("", name="confirm_password")

    def set_name(self, value: str):
        """Set the name field."""
        self.name = value

    def set_email(self, value: str):
        """Set the email field."""
        self.email = value

    def set_address(self, value: str):
        """Set the address field."""
        self.address = value

    def set_city(self, value: str):
        """Set the city field."""
        self.city = value

    def set_password(self, value: str):
        """Set the password field."""
        self.password = value

    def set_confirm_password(self, value: str):
        """Set the confirm_password field."""
        self.confirm_password = value

    def next_step(self):
        """Advance to the next step with validation."""
        if self.step == 1:
            if self.name.strip() and self.email.strip() and "@" in self.email:
                self.step = 2
        elif self.step == 2:
            if self.address.strip() and self.city.strip():
                self.step = 3

    def prev_step(self):
        """Go back to the previous step."""
        if self.step > 1:
            self.step -= 1

    def submit(self):
        """Final submission: validate passwords and clear draft data."""
        if (
            self.password.strip()
            and self.confirm_password.strip()
            and self.password == self.confirm_password
        ):
            self.submitted = True
            self.name = ""
            self.email = ""
            self.address = ""
            self.city = ""
            self.password = ""
            self.confirm_password = ""


def step1() -> rx.Component:
    """Render Step 1: Name and Email."""
    return rx.vstack(
        rx.heading("Step 1: Personal Info", size="5"),
        rx.text("Name"),
        rx.input(
            value=WizardState.name,
            on_change=WizardState.set_name,
            name="name",
        ),
        rx.text("Email"),
        rx.input(
            value=WizardState.email,
            on_change=WizardState.set_email,
            name="email",
        ),
        rx.hstack(
            rx.button("Next", on_click=WizardState.next_step),
            spacing="4",
        ),
        spacing="3",
        width="100%",
    )


def step2() -> rx.Component:
    """Render Step 2: Address and City."""
    return rx.vstack(
        rx.heading("Step 2: Address Info", size="5"),
        rx.text("Address"),
        rx.input(
            value=WizardState.address,
            on_change=WizardState.set_address,
            name="address",
        ),
        rx.text("City"),
        rx.input(
            value=WizardState.city,
            on_change=WizardState.set_city,
            name="city",
        ),
        rx.hstack(
            rx.button("Previous", on_click=WizardState.prev_step),
            rx.button("Next", on_click=WizardState.next_step),
            spacing="4",
        ),
        spacing="3",
        width="100%",
    )


def step3() -> rx.Component:
    """Render Step 3: Password and Confirmation."""
    return rx.vstack(
        rx.heading("Step 3: Set Password", size="5"),
        rx.text("Password"),
        rx.input(
            value=WizardState.password,
            on_change=WizardState.set_password,
            name="password",
            type="password",
        ),
        rx.text("Confirm Password"),
        rx.input(
            value=WizardState.confirm_password,
            on_change=WizardState.set_confirm_password,
            name="confirm_password",
            type="password",
        ),
        rx.hstack(
            rx.button("Previous", on_click=WizardState.prev_step),
            rx.button("Submit", on_click=WizardState.submit),
            spacing="4",
        ),
        spacing="3",
        width="100%",
    )


def index() -> rx.Component:
    """Main page: shows wizard or confirmation."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.cond(
            WizardState.submitted,
            rx.vstack(
                rx.heading("Registration complete", size="5"),
                rx.text("Thank you for registering!"),
                spacing="3",
                justify="center",
                min_height="85vh",
            ),
            rx.vstack(
                rx.cond(
                    WizardState.step == 1,
                    step1(),
                    rx.cond(
                        WizardState.step == 2,
                        step2(),
                        step3(),
                    ),
                ),
                spacing="5",
                justify="center",
                min_height="85vh",
            ),
        ),
    )


app = rx.App()
app.add_page(index)