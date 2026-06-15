import reflex as rx


class State(rx.State):
    submissions: list[dict] = []
    last_submission: dict = {}

    @rx.var(cache=True)
    def submission_count(self) -> int:
        return len(self.submissions)

    @rx.event
    def handle_submit(self, form_data: dict):
        self.last_submission = form_data
        self.submissions.append(form_data)

    @rx.event
    def reset_form(self):
        self.last_submission = {}


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.form(
                rx.vstack(
                    rx.input(id="name", name="name", placeholder="Name"),
                    rx.input(id="email", name="email", placeholder="Email"),
                    rx.input(id="message", name="message", placeholder="Message"),
                    rx.hstack(
                        rx.button("Submit", type="submit"),
                        rx.button("Reset", type="reset", on_click=State.reset_form),
                    ),
                    spacing="3",
                ),
                on_submit=State.handle_submit,
            ),
            rx.text("Submission Count: ", State.submission_count),
            spacing="5",
            align="center",
            justify="center",
            min_height="50vh",
        )
    )


app = rx.App()
app.add_page(index)
