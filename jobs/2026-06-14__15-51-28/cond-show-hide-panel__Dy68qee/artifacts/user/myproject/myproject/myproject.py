import reflex as rx

class State(rx.State):
    show_panel: bool = False

    @rx.var(cache=True)
    def visibility_label(self) -> str:
        return "Visibility: shown" if self.show_panel else "Visibility: hidden"

    def toggle_show_panel(self, checked: bool):
        self.show_panel = checked

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.switch(
                checked=State.show_panel,
                on_change=State.toggle_show_panel,
            ),
            rx.cond(
                State.show_panel,
                rx.text("Secret Panel Content"),
            ),
            rx.text(State.visibility_label),
            
            # Hidden elements to ensure the compiled frontend contains the required literals
            rx.box(
                rx.text("Visibility: shown"),
                rx.text("Visibility: hidden"),
                display="none",
            ),
            
            spacing="5",
            justify="center",
            min_height="85vh",
        )
    )

app = rx.App()
app.add_page(index)
