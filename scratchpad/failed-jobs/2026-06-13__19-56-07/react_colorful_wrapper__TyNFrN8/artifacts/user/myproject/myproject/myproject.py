import reflex as rx
from reflex.components.component import NoSSRComponent

class HexColorPicker(NoSSRComponent):
    library = "react-colorful"
    tag = "HexColorPicker"

    # The color prop bound to the React component's color prop.
    color: rx.Var[str]

    # The on_change event trigger that serializes the React (color) => void callback.
    on_change: rx.EventHandler[lambda color: [color]]

hex_color_picker = HexColorPicker.create

class State(rx.State):
    color: str = "#db114b"

    def set_color(self, color: str):
        self.color = color

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            hex_color_picker(
                color=State.color,
                on_change=State.set_color,
            ),
            rx.text(
                State.color,
                background_color=State.color,
                padding="1em",
                border_radius="0.5em",
                font_weight="bold",
                color=rx.color("gray", 1), # Ensure text is readable
            ),
            spacing="4",
            padding="2em",
        ),
        height="100vh",
    )

app = rx.App()
app.add_page(index)
