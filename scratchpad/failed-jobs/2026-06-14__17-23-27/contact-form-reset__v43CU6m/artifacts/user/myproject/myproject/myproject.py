"""Reflex Contact Form with Reset and Cached Submission Count."""

import reflex as rx


class State(rx.State):
    """The app state."""

    submissions: list[dict] = []
    last_submission: dict = {}

    @rx.var(cache=True)
    def submission_count(self) -> int:
        """Return the number of submissions."""
        return len(self.submissions)

    @rx.event
    async def handle_submit(self, form_data: dict):
        """Handle form submission."""
        self.last_submission = form_data
        self.submissions.append(form_data)

    @rx.event
    async def handle_reset(self):
        """Reset the form by clearing state vars."""
        self.last_submission = {}
        self.submissions = []


def index() -> rx.Component:
    """Render the contact form page."""
    return rx.container(
        rx.vstack(
            rx.heading("Contact Form", size="9"),
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
                    ),
                    rx.input(
                        placeholder="Message",
                        name="message",
                        id="message",
                    ),
                    rx.hstack(
                        rx.button("Submit", type="submit"),
                        rx.button("Reset", type="button", on_click=State.handle_reset),
                    ),
                ),
                on_submit=State.handle_submit,
                reset_on_submit=False,
            ),
            rx.text(f"Submissions: {State.submission_count}"),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index, route="/")
