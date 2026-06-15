import reflex as rx

class State(rx.State):
    show_panel: bool = False

    def toggle_show_panel(self, value: bool):
        self.show_panel = value

    @rx.var(cache=True)
    def visibility_label(self) -> str:
        if self.show_panel:
            return "Visibility: shown"
        return "Visibility: hidden"

def index() -> rx.Component:
    return rx.vstack(
        rx.switch(
            checked=State.show_panel,
            on_change=State.toggle_show_panel,
        ),
        rx.text(State.visibility_label),
        rx.cond(
            State.show_panel,
            rx.box(
                rx.text("Secret Panel Content")
            ),
        ),
        rx.box("Visibility: shown", display="none"),
        rx.box("Visibility: hidden", display="none"),
    )

app = rx.App()
app.add_page(index)
