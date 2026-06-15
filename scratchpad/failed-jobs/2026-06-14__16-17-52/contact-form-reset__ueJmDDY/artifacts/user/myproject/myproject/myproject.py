"""Contact form Reflex application."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    submissions: list[dict] = []
    last_submission: dict = {}

    @rx.var(cache=True)
    def submission_count(self) -> int:
        """Return the total number of submissions."""
        return len(self.submissions)

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle form submission."""
        entry = {
            "name": form_data.get("name", ""),
            "email": form_data.get("email", ""),
            "message": form_data.get("message", ""),
        }
        self.last_submission = entry
        self.submissions.append(entry)

    @rx.event
    def handle_reset(self):
        """Reset form-related state vars to their defaults."""
        self.last_submission = {}


def index() -> rx.Component:
    """The index page with the contact form."""
    return rx.container(
        rx.vstack(
            rx.heading("Contact Us", size="7"),
            rx.form.root(
                rx.vstack(
                    rx.text("Name", as_="label", html_for="name"),
                    rx.input(
                        placeholder="Your name",
                        name="name",
                        id="name",
                    ),
                    rx.text("Email", as_="label", html_for="email"),
                    rx.input(
                        placeholder="Your email",
                        name="email",
                        id="email",
                        type="email",
                    ),
                    rx.text("Message", as_="label", html_for="message"),
                    rx.text_area(
                        placeholder="Your message",
                        name="message",
                        id="message",
                    ),
                    rx.hstack(
                        rx.button(
                            "Submit",
                            type="submit",
                        ),
                        rx.button(
                            "Reset",
                            type="button",
                            on_click=State.handle_reset,
                            color_scheme="gray",
                        ),
                        spacing="3",
                    ),
                    spacing="3",
                    width="100%",
                ),
                on_submit=State.handle_submit,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.text(
                "Total submissions: ",
                rx.text(
                    State.submission_count,
                    as_="span",
                    weight="bold",
                ),
            ),
            rx.cond(
                State.last_submission != {},
                rx.vstack(
                    rx.text("Last submitted:"),
                    rx.text("Name: ", State.last_submission.get("name", "")),
                    rx.text("Email: ", State.last_submission.get("email", "")),
                    rx.text("Message: ", State.last_submission.get("message", "")),
                    spacing="2",
                ),
            ),
            spacing="5",
            width="100%",
            max_width="500px",
            padding="4",
        ),
        padding="8",
    )


app = rx.App()
app.add_page(index, route="/")
