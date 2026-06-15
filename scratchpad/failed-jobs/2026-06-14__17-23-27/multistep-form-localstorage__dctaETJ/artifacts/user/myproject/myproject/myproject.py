"""Multi-step registration wizard with localStorage persistence."""

import reflex as rx


class State(rx.State):
    """The app state for the registration wizard."""

    step: int = 1
    submitted: bool = False

    name: str = rx.LocalStorage("", name="name")
    email: str = rx.LocalStorage("", name="email")
    address: str = rx.LocalStorage("", name="address")
    city: str = rx.LocalStorage("", name="city")
    password: str = rx.LocalStorage("", name="password")
    confirm_password: str = rx.LocalStorage("", name="confirm_password")

    def next_step(self) -> None:
        """Advance to the next step after validating current step fields."""
        if self.step == 1:
            if not self.name.strip() or not self.email.strip():
                return
            if "@" not in self.email:
                return
            self.step = 2
        elif self.step == 2:
            if not self.address.strip() or not self.city.strip():
                return
            self.step = 3
        elif self.step == 3:
            if not self.password.strip() or not self.confirm_password.strip():
                return
            if self.password != self.confirm_password:
                return
            self.submitted = True
            self.name = ""
            self.email = ""
            self.address = ""
            self.city = ""
            self.password = ""
            self.confirm_password = ""

    def prev_step(self) -> None:
        """Go back to the previous step, but never below 1."""
        if self.step > 1:
            self.step -= 1


def step1_form() -> rx.Component:
    """Render step 1: name and email."""
    return rx.vstack(
        rx.heading("Step 1: Personal Info", size="5"),
        rx.text("Enter your name and email address."),
        rx.input(
            value=State.name,
            on_change=State.set_name,
            placeholder="Full Name",
            name="name",
            width="100%",
        ),
        rx.input(
            value=State.email,
            on_change=State.set_email,
            placeholder="Email Address",
            name="email",
            width="100%",
        ),
        rx.hstack(
            rx.button("Next", on_click=State.next_step, type="button"),
            spacing="3",
        ),
        spacing="4",
        width="100%",
        max_width="400px",
    )


def step2_form() -> rx.Component:
    """Render step 2: address and city."""
    return rx.vstack(
        rx.heading("Step 2: Address", size="5"),
        rx.text("Enter your address and city."),
        rx.input(
            value=State.address,
            on_change=State.set_address,
            placeholder="Street Address",
            name="address",
            width="100%",
        ),
        rx.input(
            value=State.city,
            on_change=State.set_city,
            placeholder="City",
            name="city",
            width="100%",
        ),
        rx.hstack(
            rx.button("Back", on_click=State.prev_step, type="button"),
            rx.button("Next", on_click=State.next_step, type="button"),
            spacing="3",
        ),
        spacing="4",
        width="100%",
        max_width="400px",
    )


def step3_form() -> rx.Component:
    """Render step 3: password and confirm password."""
    return rx.vstack(
        rx.heading("Step 3: Set Password", size="5"),
        rx.text("Choose a password for your account."),
        rx.input(
            value=State.password,
            on_change=State.set_password,
            placeholder="Password",
            name="password",
            type="password",
            width="100%",
        ),
        rx.input(
            value=State.confirm_password,
            on_change=State.set_confirm_password,
            placeholder="Confirm Password",
            name="confirm_password",
            type="password",
            width="100%",
        ),
        rx.hstack(
            rx.button("Back", on_click=State.prev_step, type="button"),
            rx.button("Submit", on_click=State.next_step, type="button"),
            spacing="3",
        ),
        spacing="4",
        width="100%",
        max_width="400px",
    )


def success_view() -> rx.Component:
    """Render the confirmation message after successful submission."""
    return rx.vstack(
        rx.heading("Registration complete", size="7", color="green"),
        rx.text("Your account has been created successfully."),
        spacing="4",
        align="center",
    )


def index() -> rx.Component:
    """Render the registration wizard."""
    return rx.container(
        rx.vstack(
            rx.heading("Registration Wizard", size="8"),
            rx.cond(
                State.submitted,
                success_view(),
                rx.cond(
                    State.step == 1,
                    step1_form(),
                    rx.cond(
                        State.step == 2,
                        step2_form(),
                        step3_form(),
                    ),
                ),
            ),
            spacing="6",
            align="center",
            min_height="85vh",
            justify="center",
        ),
    )


app = rx.App()
app.add_page(index)
