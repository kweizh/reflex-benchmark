import reflex as rx

class State(rx.State):
    """The app state."""
    form_name: str = ""
    form_email: str = ""
    form_message: str = ""
    
    last_submission: dict = {}
    submissions: list[dict] = []

    @rx.var(cache=True)
    def submission_count(self) -> int:
        return len(self.submissions)

    @rx.event
    def handle_submit(self, form_data: dict):
        self.last_submission = form_data
        self.submissions.append(form_data)

    @rx.event
    def reset_form(self):
        self.form_name = ""
        self.form_email = ""
        self.form_message = ""

    @rx.event
    def set_form_name(self, value: str):
        self.form_name = value

    @rx.event
    def set_form_email(self, value: str):
        self.form_email = value

    @rx.event
    def set_form_message(self, value: str):
        self.form_message = value

def index() -> rx.Component:
    return rx.container(
        rx.form.root(
            rx.vstack(
                rx.input(
                    placeholder="Name",
                    id="name",
                    name="name",
                    value=State.form_name,
                    on_change=State.set_form_name,
                ),
                rx.input(
                    placeholder="Email",
                    id="email",
                    name="email",
                    value=State.form_email,
                    on_change=State.set_form_email,
                ),
                rx.input(
                    placeholder="Message",
                    id="message",
                    name="message",
                    value=State.form_message,
                    on_change=State.set_form_message,
                ),
                rx.hstack(
                    rx.button("Submit", type="submit"),
                    rx.button("Reset", type="button", on_click=State.reset_form),
                ),
            ),
            on_submit=State.handle_submit,
            reset_on_submit=False,
        ),
        rx.text(State.submission_count, id="submission-count"),
    )

app = rx.App()
app.add_page(index, route="/")
