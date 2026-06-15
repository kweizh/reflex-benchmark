"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    name: str = ""
    email: str = ""
    message: str = ""
    last_submission: dict = {}
    submissions: list[dict] = []

    @rx.var(cache=True)
    def submission_count(self) -> int:
        return len(self.submissions)

    @rx.event
    def handle_submit(self, form_data: dict):
        submission = {
            "name": form_data.get("name", ""),
            "email": form_data.get("email", ""),
            "message": form_data.get("message", ""),
        }
        self.last_submission = submission
        self.submissions.append(submission)

    @rx.event
    def reset_form(self):
        self.name = ""
        self.email = ""
        self.message = ""


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Contact Form", size="7"),
            rx.form.root(
                rx.vstack(
                    rx.input(
                        placeholder="Name",
                        name="name",
                        id="name",
                    ),
                    rx.input(
                        placeholder="Email",
                        name="email",
                        id="email",
                        type="email",
                    ),
                    rx.text_area(
                        placeholder="Message",
                        name="message",
                        id="message",
                    ),
                    rx.hstack(
                        rx.button("Submit", type="submit"),
                        rx.button("Reset", type="reset", on_click=State.reset_form),
                    ),
                    spacing="3",
                ),
                on_submit=State.handle_submit,
            ),
            rx.text(f"Submissions: {State.submission_count}"),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)