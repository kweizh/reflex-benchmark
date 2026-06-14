import reflex as rx

class State(rx.State):
    tracks: list[dict[str, str]] = [
        {"title": "Track 1", "src": "/tracks/track1.mp3"},
        {"title": "Track 2", "src": "/tracks/track2.mp3"},
        {"title": "Track 3", "src": "/tracks/track3.mp3"},
    ]
    current_index: int = 0

    def set_track(self, index: int):
        self.current_index = index

    def handle_ended(self):
        self.current_index = (self.current_index + 1) % 3

    @rx.var
    def current_track_src(self) -> str:
        return self.tracks[self.current_index]["src"]

class AudioPlayer(rx.NoSSRComponent):
    library = "react-h5-audio-player"
    tag = "AudioPlayer"
    is_default = True

    src: rx.Var[str]
    autoplay: rx.Var[bool]

    _rename_props = {"autoplay": "autoPlay"}

    on_play: rx.EventHandler[lambda: []]
    on_pause: rx.EventHandler[lambda: []]
    on_ended: rx.EventHandler[lambda: []]

    def _get_custom_code(self) -> str:
        return "import 'react-h5-audio-player/lib/styles.css';"

audio_player = AudioPlayer.create

def track_item(track: dict[str, str], index: int) -> rx.Component:
    return rx.button(
        track["title"],
        on_click=State.set_track(index),
        color_scheme=rx.cond(State.current_index == index, "blue", "gray"),
        variant="solid",
        width="100%",
    )

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Audio Player"),
            audio_player(
                src=State.current_track_src,
                autoplay=True,
                on_ended=State.handle_ended
            ),
            rx.vstack(
                rx.foreach(
                    State.tracks,
                    lambda track, index: track_item(track, index)
                ),
                width="100%",
            ),
            spacing="5",
            justify="center",
            margin_top="50px"
        ),
    )

app = rx.App()
app.add_page(index)
