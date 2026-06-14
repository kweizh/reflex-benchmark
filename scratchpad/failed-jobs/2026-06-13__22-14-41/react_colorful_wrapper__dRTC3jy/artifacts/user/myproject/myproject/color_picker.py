"""Custom Reflex component wrapping react-colorful's HexColorPicker."""

import reflex as rx


def hex_color_event(color: rx.Var[str]) -> tuple[rx.Var[str]]:
    """Event spec that passes the hex color string from the React callback.

    Args:
        color: The hex color string from the React onChange callback.

    Returns:
        A tuple containing the color string Var.
    """
    return (color,)


class HexColorPicker(rx.NoSSRComponent):
    """A Reflex wrapper for the react-colorful HexColorPicker component."""

    library = "react-colorful"
    tag = "HexColorPicker"
    is_default = False

    color: rx.Var[str]

    on_change: rx.EventHandler[hex_color_event]
