import reflex as rx

class State(rx.State):
    theme_pref: str = rx.Cookie("auto", name="theme_pref")
    simulated_os_pref: str = "light"

    def set_theme_pref(self, t: str):
        self.theme_pref = t

    def set_simulated_os_pref(self, p: str):
        self.simulated_os_pref = p

    @rx.var(cache=True)
    def effective_theme(self) -> str:
        if self.theme_pref == "light":
            return "light"
        elif self.theme_pref == "dark":
            return "dark"
        else:
            return self.simulated_os_pref

    @rx.var(cache=True)
    def palette(self) -> dict[str, str]:
        if self.effective_theme == "dark":
            return {
                "bg": "#121212",
                "fg": "#e0e0e0",
                "accent": "#bb86fc",
            }
        else:
            return {
                "bg": "#ffffff",
                "fg": "#121212",
                "accent": "#6200ee",
            }

def header() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.heading("My App", size="6", color=State.palette["fg"]),
            rx.spacer(),
            rx.text(f"Selected: ", State.theme_pref, color=State.palette["fg"]),
            rx.text(f"Effective: ", State.effective_theme, color=State.palette["fg"]),
            rx.select(
                ["light", "dark", "auto"],
                value=State.theme_pref,
                on_change=State.set_theme_pref,
                width="120px",
            ),
            align_items="center",
            width="100%",
        ),
        padding="1rem",
        background_color=rx.cond(
            State.effective_theme == "dark",
            "#333333",
            "#e0e0e0"
        ),
        border_bottom=f"2px solid {State.palette['accent']}",
    )

def index() -> rx.Component:
    return rx.box(
        header(),
        rx.vstack(
            rx.heading("Home Page", color=State.palette["fg"]),
            rx.text("This is the home page.", color=State.palette["fg"]),
            rx.button("Simulate system: light", on_click=lambda: State.set_simulated_os_pref("light")),
            rx.button("Simulate system: dark", on_click=lambda: State.set_simulated_os_pref("dark")),
            rx.link("Go to About", href="/about", color=State.palette["accent"]),
            padding="2rem",
            spacing="4",
        ),
        background_color=State.palette["bg"],
        min_height="100vh",
    )

def about() -> rx.Component:
    return rx.box(
        header(),
        rx.vstack(
            rx.heading("About Page", color=State.palette["fg"]),
            rx.text("This is the about page.", color=State.palette["fg"]),
            rx.button("Simulate system: light", on_click=lambda: State.set_simulated_os_pref("light")),
            rx.button("Simulate system: dark", on_click=lambda: State.set_simulated_os_pref("dark")),
            rx.link("Go to Home", href="/", color=State.palette["accent"]),
            padding="2rem",
            spacing="4",
        ),
        background_color=State.palette["bg"],
        min_height="100vh",
    )

app = rx.App()
app.add_page(index, route="/")
app.add_page(about, route="/about")
