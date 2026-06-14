"""Welcome to Reflex! This file implements a theme system with cookie persistence."""

import reflex as rx
from typing import Literal


ThemeChoice = Literal["light", "dark", "auto"]
OsPreference = Literal["light", "dark"]


class State(rx.State):
    """The app state with theme management."""

    # The user's theme choice, persisted in a browser cookie.
    theme: str = rx.Cookie("auto", name="theme_pref")

    # Backend-only: simulated OS color scheme preference.
    _simulated_os_preference: OsPreference = "light"

    @rx.event
    def set_theme(self, value: ThemeChoice):
        """Set the user's theme preference."""
        self.theme = value

    @rx.event
    def set_simulated_light(self):
        """Simulate OS preferring light mode."""
        self._simulated_os_preference = "light"

    @rx.event
    def set_simulated_dark(self):
        """Simulate OS preferring dark mode."""
        self._simulated_os_preference = "dark"

    @rx.var
    def effective_theme(self) -> str:
        """The concrete theme used to render the UI.

        - When theme is 'light' or 'dark', effective_theme mirrors it.
        - When theme is 'auto', effective_theme mirrors the simulated OS preference.
        """
        if self.theme == "light":
            return "light"
        elif self.theme == "dark":
            return "dark"
        else:  # auto
            return self._simulated_os_preference

    @rx.var
    def palette(self) -> dict:
        """A computed palette keyed by bg, fg, and accent.

        Depends on effective_theme so the whole UI stays consistent.
        """
        if self.effective_theme == "light":
            return {
                "bg": "#f8f9fa",
                "fg": "#212529",
                "accent": "#4361ee",
                "header_bg": "#e9ecef",
                "header_fg": "#212529",
            }
        else:
            return {
                "bg": "#1a1a2e",
                "fg": "#eaeaea",
                "accent": "#f72585",
                "header_bg": "#16213e",
                "header_fg": "#eaeaea",
            }
