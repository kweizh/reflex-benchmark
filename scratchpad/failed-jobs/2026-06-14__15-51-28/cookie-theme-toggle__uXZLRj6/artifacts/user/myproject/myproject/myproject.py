import reflex as rx

class State(rx.State):
    theme: str = rx.Cookie("light", name="app_theme")

    def toggle_theme(self):
        if self.theme == "light":
            self.theme = "dark"
        else:
            self.theme = "light"

def index() -> rx.Component:
    return rx.vstack(
        rx.heading(f"Current: {State.theme}"),
        rx.button("Toggle Theme", on_click=State.toggle_theme),
    )

app = rx.App()
app.add_page(index)
