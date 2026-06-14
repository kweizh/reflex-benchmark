import reflex as rx
from reflex.components.component import NoSSRComponent
from typing import Any, Dict, List, Optional, Union

class AudioPlayer(NoSSRComponent):
    library = "react-h5-audio-player"
    tag = "AudioPlayer"
    is_default = True

    # Props mapping
    src: rx.Var[str]
    autoplay: rx.Var[bool]

    _rename_props = {
        "autoplay": "autoPlay",
    }

    def _get_imports(self) -> rx.ImportDict:
        imports = super()._get_imports()
        # Add CSS import
        imports.setdefault("react-h5-audio-player/lib/styles.css", [])
        return imports

    # Event triggers
    on_play: rx.EventHandler[lambda: []]
    on_pause: rx.EventHandler[lambda: []]
    on_ended: rx.EventHandler[lambda: []]

class State(rx.State):
    tracks: List[Dict[str, str]] = [
        {"title": "Track 1", "src": "/tracks/track1.mp3"},
        {"title": "Track 2", "src": "/tracks/track2.mp3"},
        {"title": "Track 3", "src": "/tracks/track3.mp3"},
    ]
    current_index: int = 0

    def set_track(self, index: int):
        self.current_index = index

    def next_track(self):
        self.current_index = (self.current_index + 1) % 3

@rx.page(route="/")
def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Reflex Audio Player"),
            AudioPlayer.create(
                src=State.tracks[State.current_index]["src"],
                autoplay=True,
                on_ended=State.next_track,
            ),
            rx.vstack(
                rx.foreach(
                    State.tracks,
                    lambda track, index: rx.button(
                        track["title"],
                        on_click=lambda: State.set_track(index),
                        variant=rx.cond(State.current_index == index, "solid", "outline"),
                        width="100%",
                    )
                ),
                width="100%",
                spacing="2",
            ),
            spacing="5",
            padding="5",
        )
    )

app = rx.App()
