"""Audio player app wrapping react-h5-audio-player as a Reflex NoSSRComponent."""

import reflex as rx
from reflex.components.component import NoSSRComponent, field
from reflex.event import EventHandler
from reflex.vars.base import Var


def _no_args() -> list:
    """Serializer for event triggers that produce zero positional arguments."""
    return []


class AudioPlayer(NoSSRComponent):
    """Wrapper for react-h5-audio-player."""

    library = "react-h5-audio-player"

    tag = "AudioPlayer"

    is_default = True

    _rename_props: dict[str, str] = {"autoplay": "autoPlay"}

    # Props
    src: Var[str] = field(default=Var.create(""))
    autoplay: Var[bool] = field(default=Var.create(False))

    # Event triggers
    on_play: EventHandler[_no_args] = field(doc="Fired when playback starts.")
    on_pause: EventHandler[_no_args] = field(doc="Fired when playback is paused.")
    on_ended: EventHandler[_no_args] = field(doc="Fired when playback ends.")

    def add_imports(self) -> dict:
        """Import the CSS stylesheet for react-h5-audio-player."""
        return {
            "": "react-h5-audio-player/lib/styles.css",
        }


class State(rx.State):
    """App state for the playlist."""

    tracks: list[dict[str, str]] = [
        {"title": "Track 1", "src": "/tracks/track1.mp3"},
        {"title": "Track 2", "src": "/tracks/track2.mp3"},
        {"title": "Track 3", "src": "/tracks/track3.mp3"},
    ]

    current_index: int = 0

    @rx.event
    def select_track(self, index: int) -> None:
        """Set the current track by index."""
        self.current_index = index

    @rx.event
    def next_track(self) -> None:
        """Advance to the next track, looping back to 0 after the last."""
        self.current_index = (self.current_index + 1) % len(self.tracks)


def index() -> rx.Component:
    """The main page displaying the audio player and track list."""
    return rx.container(
        rx.vstack(
            rx.heading("Audio Player", size="7"),
            AudioPlayer.create(
                src=State.tracks[State.current_index]["src"],
                on_ended=State.next_track,
            ),
            rx.divider(),
            rx.heading("Playlist", size="5"),
            rx.vstack(
                rx.foreach(
                    State.tracks,
                    lambda track, index: rx.button(
                        track["title"],
                        on_click=State.select_track(index),
                        variant="outline",
                        width="100%",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            spacing="4",
            align="stretch",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)