import reflex as rx
from typing import Dict

class State(rx.State):
    # theme_pref is persisted in a browser cookie named "theme_pref"
    theme_pref: str = rx.Cookie("auto", name="theme_pref")
    
    # simulated_os_pref is backend-only
    simulated_os_pref: str = "light"

    @rx.var(cache=True)
    def effective_theme(self) -> str:
        if self.theme_pref == "light":
            return "light"
        elif self.theme_pref == "dark":
            return "dark"
        else:
            return self.simulated_os_pref

    @rx.var(cache=True)
    def palette(self) -> Dict[str, str]:
        if self.effective_theme == "light":
            return {
                "bg": "#ffffff",
                "fg": "#000000",
                "accent": "#3b82f6",  # blue
                "header_bg": "#f3f4f6", # gray-100
            }
        else:
            return {
                "bg": "#111827", # gray-900
                "fg": "#f9fafb", # gray-50
                "accent": "#f59e0b", # amber
                "header_bg": "#1f2937", # gray-800
            }

    def set_theme_light(self):
        self.theme_pref = "light"

    def set_theme_dark(self):
        self.theme_pref = "dark"

    def set_theme_auto(self):
        self.theme_pref = "auto"

    def simulate_system_light(self):
        self.simulated_os_pref = "light"

    def simulate_system_dark(self):
        self.simulated_os_pref = "dark"

def header() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.heading("Theme App", size="7", color=State.palette["accent"]),
            rx.spacer(),
            rx.link("Home", href="/", padding="0 10px", color=State.palette["fg"]),
            rx.link("About", href="/about", padding="0 10px", color=State.palette["fg"]),
            justify="center",
            align="center",
            width="100%",
        ),
        rx.vstack(
            rx.hstack(
                rx.text(f"Selection: {State.theme_pref}", weight="bold"),
                rx.text(f"Effective: {State.effective_theme}", weight="bold"),
                spacing="4",
            ),
            rx.hstack(
                rx.button("Light", on_click=State.set_theme_light),
                rx.button("Dark", on_click=State.set_theme_dark),
                rx.button("Auto", on_click=State.set_theme_auto),
                spacing="2",
            ),
            rx.hstack(
                rx.button("Simulate system: light", on_click=State.simulate_system_light),
                rx.button("Simulate system: dark", on_click=State.simulate_system_dark),
                spacing="2",
            ),
            align="center",
            width="100%",
            padding_top="10px",
        ),
        width="100%",
        padding="20px",
        background_color=State.palette["header_bg"],
        color=State.palette["fg"],
        border_bottom=f"2px solid {State.palette['accent']}",
    )

def layout(content: rx.Component) -> rx.Component:
    return rx.box(
        header(),
        rx.box(
            content,
            padding="40px",
            min_height="100vh",
        ),
        background_color=State.palette["bg"],
        color=State.palette["fg"],
        width="100%",
    )

def index() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("Home Page", size="8"),
            rx.text("Welcome to the multi-page Reflex theme system demo."),
            rx.text(
                "This page's colors are derived from a single computed palette."
            ),
            spacing="5",
        )
    )

def about() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("About Page", size="8"),
            rx.text("This is the about page, sharing the same consistent theme."),
            rx.text(
                "Try changing the theme or simulating the system preference!"
            ),
            spacing="5",
        )
    )

app = rx.App()
app.add_page(index, route="/")
app.add_page(about, route="/about")
