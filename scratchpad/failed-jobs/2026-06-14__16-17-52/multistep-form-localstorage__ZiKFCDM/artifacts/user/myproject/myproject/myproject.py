"""Multi-step registration wizard with LocalStorage persistence."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state with LocalStorage-persisted draft fields."""

    step: int = 1
    submitted: bool = False

    # Draft fields persisted to browser localStorage
    name: str = rx.LocalStorage("", name="name")
    email: str = rx.LocalStorage("", name="email")
    address: str = rx.LocalStorage("", name="address")
    city: str = rx.LocalStorage("", name="city")
    password: str = rx.LocalStorage("", name="password")
    confirm_password: str = rx.LocalStorage("", name="confirm_password")

    # Validation error message
    error: str = ""

    def set_name(self, value: str):
        self.name = value

    def set_email(self, value: str):
        self.email = value

    def set_address(self, value: str):
        self.address = value

    def set_city(self, value: str):
        self.city = value

    def set_password(self, value: str):
        self.password = value

    def set_confirm_password(self, value: str):
        self.confirm_password = value

    def next_step(self):
        """Advance to the next step with per-step validation."""
        self.error = ""
        if self.step == 1:
            if not self.name.strip() or not self.email.strip():
                self.error = "Name and email are required."
                return
            if "@" not in self.email:
                self.error = "Please enter a valid email address."
                return
            if self.step < 3:
                self.step += 1
        elif self.step == 2:
            if not self.address.strip() or not self.city.strip():
                self.error = "Address and city are required."
                return
            if self.step < 3:
                self.step += 1

    def prev_step(self):
        """Go back to the previous step."""
        self.error = ""
        if self.step > 1:
            self.step -= 1

    def submit(self):
        """Validate step 3 and complete registration."""
        self.error = ""
        if not self.password or not self.confirm_password:
            self.error = "Both password fields are required."
            return
        if self.password != self.confirm_password:
            self.error = "Passwords do not match."
            return
        # Clear all LocalStorage draft fields
        self.name = ""
        self.email = ""
        self.address = ""
        self.city = ""
        self.password = ""
        self.confirm_password = ""
        self.submitted = True

    def restart(self):
        """Reset wizard back to step 1."""
        self.submitted = False
        self.step = 1
        self.error = ""


def step1_form() -> rx.Component:
    return rx.vstack(
        rx.heading("Step 1: Personal Info", size="5"),
        rx.text("Please enter your name and email address."),
        rx.input(
            placeholder="Full Name",
            name="name",
            value=State.name,
            on_change=State.set_name,
            width="100%",
        ),
        rx.input(
            placeholder="Email Address",
            name="email",
            type="email",
            value=State.email,
            on_change=State.set_email,
            width="100%",
        ),
        rx.cond(
            State.error != "",
            rx.text(State.error, color="red"),
            rx.fragment(),
        ),
        rx.hstack(
            rx.button(
                "Next →",
                on_click=State.next_step,
                color_scheme="blue",
            ),
            justify="end",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def step2_form() -> rx.Component:
    return rx.vstack(
        rx.heading("Step 2: Address", size="5"),
        rx.text("Please enter your address details."),
        rx.input(
            placeholder="Street Address",
            name="address",
            value=State.address,
            on_change=State.set_address,
            width="100%",
        ),
        rx.input(
            placeholder="City",
            name="city",
            value=State.city,
            on_change=State.set_city,
            width="100%",
        ),
        rx.cond(
            State.error != "",
            rx.text(State.error, color="red"),
            rx.fragment(),
        ),
        rx.hstack(
            rx.button(
                "← Back",
                on_click=State.prev_step,
                variant="outline",
            ),
            rx.button(
                "Next →",
                on_click=State.next_step,
                color_scheme="blue",
            ),
            spacing="3",
            justify="end",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def step3_form() -> rx.Component:
    return rx.vstack(
        rx.heading("Step 3: Create Password", size="5"),
        rx.text("Choose a secure password."),
        rx.input(
            placeholder="Password",
            name="password",
            type="password",
            value=State.password,
            on_change=State.set_password,
            width="100%",
        ),
        rx.input(
            placeholder="Confirm Password",
            name="confirm_password",
            type="password",
            value=State.confirm_password,
            on_change=State.set_confirm_password,
            width="100%",
        ),
        rx.cond(
            State.error != "",
            rx.text(State.error, color="red"),
            rx.fragment(),
        ),
        rx.hstack(
            rx.button(
                "← Back",
                on_click=State.prev_step,
                variant="outline",
            ),
            rx.button(
                "Submit",
                on_click=State.submit,
                color_scheme="green",
            ),
            spacing="3",
            justify="end",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def success_view() -> rx.Component:
    return rx.vstack(
        rx.heading("Registration complete", size="7", color="green"),
        rx.text(
            "Thank you for registering! Your account has been created successfully.",
            size="4",
        ),
        rx.button(
            "Start Over",
            on_click=State.restart,
            variant="outline",
        ),
        spacing="4",
        align="center",
    )


def wizard_steps() -> rx.Component:
    return rx.vstack(
        # Progress indicator
        rx.hstack(
            rx.badge(
                "1",
                color_scheme=rx.cond(State.step >= 1, "blue", "gray"),
                variant=rx.cond(State.step == 1, "solid", "outline"),
            ),
            rx.separator(size="4"),
            rx.badge(
                "2",
                color_scheme=rx.cond(State.step >= 2, "blue", "gray"),
                variant=rx.cond(State.step == 2, "solid", "outline"),
            ),
            rx.separator(size="4"),
            rx.badge(
                "3",
                color_scheme=rx.cond(State.step >= 3, "blue", "gray"),
                variant=rx.cond(State.step == 3, "solid", "outline"),
            ),
            align="center",
            spacing="2",
            width="100%",
            justify="center",
        ),
        rx.match(
            State.step,
            (1, step1_form()),
            (2, step2_form()),
            (3, step3_form()),
            rx.text("Unknown step"),
        ),
        spacing="6",
        width="100%",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Registration Wizard", size="8"),
            rx.text(
                "Complete all three steps to create your account.",
                color="gray",
            ),
            rx.separator(),
            rx.cond(
                State.submitted,
                success_view(),
                wizard_steps(),
            ),
            spacing="5",
            align="center",
            min_height="85vh",
            padding_y="8",
        ),
        max_width="480px",
    )


app = rx.App()
app.add_page(index)
