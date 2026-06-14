import reflex as rx
from typing import Any
from reflex_components_core.el.elements.forms import Textarea
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark")

class RawTextArea(Textarea):
    def get_event_triggers(self) -> dict[str, Any]:
        triggers = super().get_event_triggers()
        triggers.update({
            "on_select": lambda e0: [e0.target.selectionStart, e0.target.selectionEnd],
            "on_click": lambda e0: [e0.target.selectionStart, e0.target.selectionEnd],
            "on_key_up": lambda e0: [e0.target.selectionStart, e0.target.selectionEnd],
            "on_change": lambda e0: [e0.target.value, e0.target.selectionStart, e0.target.selectionEnd],
        })
        return triggers

class State(rx.State):
    source: str = ""
    selection_start: int = 0
    selection_end: int = 0

    def update_selection(self, start: int, end: int):
        self.selection_start = start
        self.selection_end = end
        
    def set_source_and_selection(self, value: str, start: int, end: int):
        self.source = value
        self.selection_start = start
        self.selection_end = end

    @rx.var(cache=True)
    def preview_html(self) -> str:
        return md.render(self.source)

    @rx.var(cache=True)
    def word_count(self) -> int:
        return len(self.source.split())

    @rx.var(cache=True)
    def char_count(self) -> int:
        return len(self.source)

    def _wrap_selection(self, marker: str):
        start = self.selection_start
        end = self.selection_end
        if start > end:
            start, end = end, start
            
        before = self.source[:start]
        selected = self.source[start:end]
        after = self.source[end:]
        
        self.source = f"{before}{marker}{selected}{marker}{after}"

    def wrap_bold(self):
        self._wrap_selection("**")

    def wrap_italic(self):
        self._wrap_selection("*")

    def wrap_code(self):
        self._wrap_selection("`")

def index():
    return rx.hstack(
        rx.vstack(
            rx.hstack(
                rx.button("Bold", id="btn-bold", on_click=State.wrap_bold),
                rx.button("Italic", id="btn-italic", on_click=State.wrap_italic),
                rx.button("Code", id="btn-code", on_click=State.wrap_code),
            ),
            RawTextArea.create(
                id="md-source",
                value=State.source,
                on_select=State.update_selection,
                on_click=State.update_selection,
                on_key_up=State.update_selection,
                on_change=State.set_source_and_selection,
                style={"width": "100%", "height": "80vh"},
            ),
            rx.text(
                f"Words: {State.word_count} | Characters: {State.char_count}",
                id="md-counter"
            ),
            width="50%",
        ),
        rx.html(
            State.preview_html,
            id="md-preview",
            style={
                "width": "50%",
                "height": "80vh",
                "padding": "1em",
                "border": "1px solid #ccc",
                "overflow_y": "auto",
            }
        ),
        width="100vw",
        padding="2em",
    )

app = rx.App()
app.add_page(index)
