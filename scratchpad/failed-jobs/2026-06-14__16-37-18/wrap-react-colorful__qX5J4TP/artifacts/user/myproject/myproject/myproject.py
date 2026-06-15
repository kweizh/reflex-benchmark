import reflex as rx
from reflex.components.component import NoSSRComponent

class ColorPicker(NoSSRComponent):
    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"

    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]

color_picker = ColorPicker.create

class State(rx.State):
    color: str = "#ff0000"

    def set_color(self, c: str):
        self.color = c

def index() -> rx.Component:
    return rx.vstack(
        rx.box(width="80px", height="80px", background=State.color),
        color_picker(color=State.color, on_change=State.set_color)
    )

app = rx.App()
app.add_page(index)
