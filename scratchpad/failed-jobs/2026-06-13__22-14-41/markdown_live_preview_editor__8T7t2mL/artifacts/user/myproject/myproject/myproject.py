"""Markdown Editor with Live HTML Preview."""

import reflex as rx
from markdown_it import MarkdownIt


# Instantiate the Markdown converter (commonmark preset)
md = MarkdownIt("commonmark")


class State(rx.State):
    """The app state."""

    source: str = ""
    selection_start: int = 0
    selection_end: int = 0

    @rx.event
    def set_source(self, value: str):
        """Update the source text."""
        self.source = value

    @rx.event
    def update_selection(self, data: dict):
        """Update the selection range from the browser."""
        start = data.get("selectionStart", 0)
        end = data.get("selectionEnd", 0)
        self.selection_start = int(start) if start is not None else 0
        self.selection_end = int(end) if end is not None else 0

    @rx.var(cache=True)
    def preview_html(self) -> str:
        """Convert Markdown source to HTML."""
        return md.render(self.source)

    @rx.var(cache=True)
    def word_count(self) -> int:
        """Return the number of words in the source."""
        if not self.source.strip():
            return 0
        return len(self.source.split())

    @rx.var(cache=True)
    def char_count(self) -> int:
        """Return the number of characters in the source."""
        return len(self.source)

    def _wrap_selection(self, marker: str):
        """Wrap the current selection with the given marker."""
        text = self.source
        start = self.selection_start
        end = self.selection_end

        if start == end:
            # No selection: insert marker pair at cursor
            self.source = text[:start] + marker + marker + text[start:]
        else:
            # Wrap the selection with markers
            selected = text[start:end]
            self.source = text[:start] + marker + selected + marker + text[end:]

    @rx.event
    def wrap_bold(self):
        """Wrap selection with **...**."""
        self._wrap_selection("**")

    @rx.event
    def wrap_italic(self):
        """Wrap selection with *...*."""
        self._wrap_selection("*")

    @rx.event
    def wrap_code(self):
        """Wrap selection with `...`."""
        self._wrap_selection("`")


def index() -> rx.Component:
    """The main page."""
    return rx.container(
        rx.vstack(
            rx.heading("Markdown Editor", size="7"),
            # Toolbar
            rx.hstack(
                rx.button("Bold", id="btn-bold", on_click=State.wrap_bold),
                rx.button("Italic", id="btn-italic", on_click=State.wrap_italic),
                rx.button("Code", id="btn-code", on_click=State.wrap_code),
                spacing="2",
            ),
            # Counter
            rx.text(
                rx.text.span("Words: "),
                rx.text.span(State.word_count),
                rx.text.span(" | Characters: "),
                rx.text.span(State.char_count),
                id="md-counter",
            ),
            # Editor + Preview split
            rx.hstack(
                # Left: Markdown source textarea
                rx.text_area(
                    value=State.source,
                    on_change=[
                        State.set_source,
                        rx.call_script(
                            "JSON.stringify({selectionStart: document.getElementById('md-source').selectionStart, selectionEnd: document.getElementById('md-source').selectionEnd})",
                            callback=State.update_selection,
                        ),
                    ],
                    on_select=rx.call_script(
                        "JSON.stringify({selectionStart: document.getElementById('md-source').selectionStart, selectionEnd: document.getElementById('md-source').selectionEnd})",
                        callback=State.update_selection,
                    ),
                    on_click=rx.call_script(
                        "JSON.stringify({selectionStart: document.getElementById('md-source').selectionStart, selectionEnd: document.getElementById('md-source').selectionEnd})",
                        callback=State.update_selection,
                    ),
                    on_key_up=rx.call_script(
                        "JSON.stringify({selectionStart: document.getElementById('md-source').selectionStart, selectionEnd: document.getElementById('md-source').selectionEnd})",
                        callback=State.update_selection,
                    ),
                    placeholder="Type your Markdown here...",
                    id="md-source",
                    width="50%",
                    min_height="400px",
                ),
                # Right: HTML preview
                rx.box(
                    rx.html(State.preview_html),
                    id="md-preview",
                    width="50%",
                    min_height="400px",
                    border="1px solid #ccc",
                    padding="1em",
                    overflow="auto",
                ),
                width="100%",
                align_items="start",
                spacing="4",
            ),
            spacing="4",
            width="100%",
        ),
        max_width="1200px",
    )


app = rx.App()
app.add_page(index)
