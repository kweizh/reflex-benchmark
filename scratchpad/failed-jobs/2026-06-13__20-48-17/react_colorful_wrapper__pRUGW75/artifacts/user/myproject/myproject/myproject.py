import reflex as rx

class HexColorPicker(rx.NoSSRComponent):
    library = "react-colorful"
    tag = "HexColorPicker"

    color: rx.Var[str]

    on_change: rx.EventHandler[lambda color: [color]]

color_picker = HexColorPicker.create

class State(rx.State):
    color: str = "#aabbcc"

    def set_color(self, color: str):
        self.color = color

def index() -> rx.Component:
    return rx.container(
        color_picker(
            color=State.color,
            on_change=State.set_color
        ),
        rx.text(
            State.color,
            background_color=State.color
        )
    )

app = rx.App()
app.add_page(index)
