"""Reflex Theme System with Cookie Persistence and Computed Palette."""

import reflex as rx


LIGHT_PALETTE = {
    "bg": "#f8f9fa",
    "fg": "#212529",
    "accent": "#0d6efd",
    "header_bg": "#ffffff",
    "header_fg": "#212529",
    "header_accent": "#0d6efd",
}

DARK_PALETTE = {
    "bg": "#1a1a2e",
    "fg": "#e0e0e0",
    "accent": "#e94560",
    "header_bg": "#16213e",
    "header_fg": "#e0e0e0",
    "header_accent": "#e94560",
}


class ThemeState(rx.State):
    """State for theme selection with cookie persistence."""

    # The user's theme choice, persisted in a cookie named "theme_pref"
    theme: rx.Cookie = rx.Cookie("light", name="theme_pref")

    # Simulated OS color-scheme preference (backend-only, not stored in cookie)
    _prefers_color_scheme: str = "light"

    @rx.var(cache=True)
    def effective_theme(self) -> str:
        """Return the concrete theme used for rendering.

        - theme=light → light
        - theme=dark  → dark
        - theme=auto  → mirrors the simulated OS preference
        """
        if self.theme == "light":
            return "light"
        if self.theme == "dark":
            return "dark"
        # theme == "auto" → use simulated OS preference
        return self._prefers_color_scheme

    @rx.var(cache=True)
    def palette(self) -> dict:
        """Return the colour palette dict based on effective_theme."""
        if self.effective_theme == "dark":
            return DARK_PALETTE
        return LIGHT_PALETTE

    def set_theme(self, value: str):
        """Set the theme selection (light / dark / auto)."""
        self.theme = value

    def simulate_light(self):
        """Simulate OS preferring a light colour scheme."""
        self._prefers_color_scheme = "light"

    def simulate_dark(self):
        """Simulate OS preferring a dark colour scheme."""
        self._prefers_color_scheme = "dark"


def header() -> rx.Component:
    """Header component that swaps palette based on effective_theme."""
    return rx.box(
        rx.hstack(
            rx.link(
                rx.heading("MyApp", size="4", weight="bold"),
                href="/",
            ),
            rx.hstack(
                rx.link("Home", href="/", padding_x="0.5em"),
                rx.link("About", href="/about", padding_x="0.5em"),
                spacing="4",
            ),
            rx.spacer(),
            rx.text(
                "Theme: ",
                rx.text(
                    ThemeState.theme,
                    weight="bold",
                    as_="span",
                ),
                " | Effective: ",
                rx.text(
                    ThemeState.effective_theme,
                    weight="bold",
                    as_="span",
                ),
                size="2",
            ),
            justify="between",
            align="center",
            width="100%",
        ),
        # Use rx.cond to swap header palette colours
        background=rx.cond(
            ThemeState.effective_theme == "dark",
            DARK_PALETTE["header_bg"],
            LIGHT_PALETTE["header_bg"],
        ),
        color=rx.cond(
            ThemeState.effective_theme == "dark",
            DARK_PALETTE["header_fg"],
            LIGHT_PALETTE["header_fg"],
        ),
        border_bottom=rx.cond(
            ThemeState.effective_theme == "dark",
            f"2px solid {DARK_PALETTE['header_accent']}",
            f"2px solid {LIGHT_PALETTE['header_accent']}",
        ),
        padding_x="1.5em",
        padding_y="0.75em",
        width="100%",
    )


def theme_selector() -> rx.Component:
    """Theme selector with light / dark / auto buttons."""
    return rx.vstack(
        rx.text("Select theme:", weight="bold", size="3"),
        rx.hstack(
            rx.button(
                "Light",
                on_click=ThemeState.set_theme("light"),
                variant=rx.cond(ThemeState.theme == "light", "solid", "outline"),
                size="2",
            ),
            rx.button(
                "Dark",
                on_click=ThemeState.set_theme("dark"),
                variant=rx.cond(ThemeState.theme == "dark", "solid", "outline"),
                size="2",
            ),
            rx.button(
                "Auto",
                on_click=ThemeState.set_theme("auto"),
                variant=rx.cond(ThemeState.theme == "auto", "solid", "outline"),
                size="2",
            ),
            spacing="3",
        ),
        spacing="1",
    )


def simulation_controls() -> rx.Component:
    """Controls to simulate the OS-level colour-scheme preference."""
    return rx.vstack(
        rx.text("Simulate system preference:", weight="bold", size="3"),
        rx.hstack(
            rx.button(
                "Simulate system: light",
                on_click=ThemeState.simulate_light,
                variant="outline",
                size="2",
            ),
            rx.button(
                "Simulate system: dark",
                on_click=ThemeState.simulate_dark,
                variant="outline",
                size="2",
            ),
            spacing="3",
        ),
        spacing="1",
    )


def page_shell(*children) -> rx.Component:
    """Common page shell: header + body with palette-driven colours."""
    return rx.box(
        header(),
        rx.box(
            *children,
            padding="2em",
            max_width="800px",
            margin="0 auto",
        ),
        background=rx.cond(
            ThemeState.effective_theme == "dark",
            DARK_PALETTE["bg"],
            LIGHT_PALETTE["bg"],
        ),
        color=rx.cond(
            ThemeState.effective_theme == "dark",
            DARK_PALETTE["fg"],
            LIGHT_PALETTE["fg"],
        ),
        min_height="100vh",
    )


def index() -> rx.Component:
    """Home page."""
    return page_shell(
        rx.vstack(
            rx.heading("Home", size="6"),
            rx.text("Welcome to the Theme Demo app."),
            rx.divider(margin_y="1em"),
            theme_selector(),
            rx.divider(margin_y="1em"),
            simulation_controls(),
            spacing="4",
            align="start",
        ),
    )


def about() -> rx.Component:
    """About page."""
    return page_shell(
        rx.vstack(
            rx.heading("About", size="6"),
            rx.text("This app demonstrates the Reflex theme system."),
            rx.text(
                "The theme selector lets you choose light, dark, or auto mode. "
                "When auto is selected, the simulated OS preference determines the "
                "effective theme. The entire UI palette updates accordingly."
            ),
            rx.divider(margin_y="1em"),
            theme_selector(),
            rx.divider(margin_y="1em"),
            simulation_controls(),
            spacing="4",
            align="start",
        ),
    )


app = rx.App()
app.add_page(index, route="/", title="Home")
app.add_page(about, route="/about", title="About")