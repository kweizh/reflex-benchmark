"""Registration wizard with localStorage persistence."""

import reflex as rx


class State(rx.State):
    step: int = 1
    submitted: bool = False
    error_message: str = ""

    # Draft fields persisted in browser's localStorage
    name: str = rx.LocalStorage("", name="name")
    email: str = rx.LocalStorage("", name="email")
    address: str = rx.LocalStorage("", name="address")
    city: str = rx.LocalStorage("", name="city")
    password: str = rx.LocalStorage("", name="password")
    confirm_password: str = rx.LocalStorage("", name="confirm_password")

    def set_name(self, value: str):
        self.name = value
        self.error_message = ""

    def set_email(self, value: str):
        self.email = value
        self.error_message = ""

    def set_address(self, value: str):
        self.address = value
        self.error_message = ""

    def set_city(self, value: str):
        self.city = value
        self.error_message = ""

    def set_password(self, value: str):
        self.password = value
        self.error_message = ""

    def set_confirm_password(self, value: str):
        self.confirm_password = value
        self.error_message = ""

    @rx.var
    def progress_value(self) -> int:
        return int((self.step / 3.0) * 100)

    def next_step(self):
        self.error_message = ""
        if self.step == 1:
            if not self.name.strip():
                self.error_message = "Name cannot be empty."
                return
            if not self.email.strip():
                self.error_message = "Email cannot be empty."
                return
            if "@" not in self.email:
                self.error_message = "Email must contain @."
                return
            self.step = 2
        elif self.step == 2:
            if not self.address.strip():
                self.error_message = "Address cannot be empty."
                return
            if not self.city.strip():
                self.error_message = "City cannot be empty."
                return
            self.step = 3

    def prev_step(self):
        self.error_message = ""
        if self.step > 1:
            self.step -= 1

    def submit(self):
        self.error_message = ""
        if self.step == 3:
            if not self.password:
                self.error_message = "Password cannot be empty."
                return
            if not self.confirm_password:
                self.error_message = "Confirm password cannot be empty."
                return
            if self.password != self.confirm_password:
                self.error_message = "Passwords do not match."
                return
            self.submitted = True
            # Clear all six LocalStorage draft vars
            self.name = ""
            self.email = ""
            self.address = ""
            self.city = ""
            self.password = ""
            self.confirm_password = ""

    def reset_wizard(self):
        self.submitted = False
        self.step = 1
        self.error_message = ""


def index() -> rx.Component:
    return rx.center(
        rx.color_mode.button(position="top-right"),
        rx.cond(
            State.submitted,
            # Confirmation page
            rx.card(
                rx.vstack(
                    rx.heading("Registration complete 🎉", size="6", color_scheme="green"),
                    rx.text(
                        "Thank you for registering! Your registration is complete and details have been submitted successfully."
                    ),
                    rx.button("Register Another User", on_click=State.reset_wizard),
                    spacing="4",
                    align="center",
                ),
                width="100%",
                max_width="500px",
                padding="6",
            ),
            # Wizard page
            rx.card(
                rx.vstack(
                    rx.heading("Registration Wizard", size="6", align="center"),
                    rx.text(f"Step {State.step} of 3", size="2", color="gray", align="center"),
                    rx.progress(value=State.progress_value, width="100%"),
                    
                    # Form inputs based on active step
                    rx.cond(
                        State.step == 1,
                        rx.vstack(
                            rx.text("Step 1: Personal Info", size="4", weight="bold"),
                            rx.vstack(
                                rx.text("Full Name", size="2", weight="medium"),
                                rx.input(
                                    value=State.name,
                                    on_change=State.set_name,
                                    name="name",
                                    placeholder="John Doe",
                                    width="100%",
                                ),
                                width="100%",
                                spacing="1",
                            ),
                            rx.vstack(
                                rx.text("Email Address", size="2", weight="medium"),
                                rx.input(
                                    value=State.email,
                                    on_change=State.set_email,
                                    name="email",
                                    placeholder="john.doe@example.com",
                                    type="email",
                                    width="100%",
                                ),
                                width="100%",
                                spacing="1",
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        rx.cond(
                            State.step == 2,
                            rx.vstack(
                                rx.text("Step 2: Address Details", size="4", weight="bold"),
                                rx.vstack(
                                    rx.text("Street Address", size="2", weight="medium"),
                                    rx.input(
                                        value=State.address,
                                        on_change=State.set_address,
                                        name="address",
                                        placeholder="123 Main St",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="1",
                                ),
                                rx.vstack(
                                    rx.text("City", size="2", weight="medium"),
                                    rx.input(
                                        value=State.city,
                                        on_change=State.set_city,
                                        name="city",
                                        placeholder="New York",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="1",
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            # Step 3
                            rx.vstack(
                                rx.text("Step 3: Account Security", size="4", weight="bold"),
                                rx.vstack(
                                    rx.text("Password", size="2", weight="medium"),
                                    rx.input(
                                        value=State.password,
                                        on_change=State.set_password,
                                        name="password",
                                        placeholder="••••••••",
                                        type="password",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="1",
                                ),
                                rx.vstack(
                                    rx.text("Confirm Password", size="2", weight="medium"),
                                    rx.input(
                                        value=State.confirm_password,
                                        on_change=State.set_confirm_password,
                                        name="confirm_password",
                                        placeholder="••••••••",
                                        type="password",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="1",
                                ),
                                spacing="4",
                                width="100%",
                            )
                        )
                    ),
                    
                    # Error Message (if any)
                    rx.cond(
                        State.error_message != "",
                        rx.text(State.error_message, color="red", size="2", weight="medium"),
                    ),
                    
                    # Navigation Buttons
                    rx.hstack(
                        rx.cond(
                            State.step > 1,
                            rx.button(
                                "Back",
                                on_click=State.prev_step,
                                variant="soft",
                            ),
                            rx.box(),
                        ),
                        rx.cond(
                            State.step < 3,
                            rx.button(
                                "Next",
                                on_click=State.next_step,
                                variant="solid",
                            ),
                            rx.button(
                                "Submit",
                                on_click=State.submit,
                                color_scheme="green",
                                variant="solid",
                            )
                        ),
                        justify="between",
                        width="100%",
                        margin_top="4",
                    ),
                    spacing="5",
                    width="100%",
                ),
                width="100%",
                max_width="500px",
                padding="6",
            )
        ),
        min_height="100vh",
        background_color="var(--gray-2)",
    )


app = rx.App()
app.add_page(index)
