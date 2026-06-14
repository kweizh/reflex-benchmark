"""Markdown Editor with Live HTML Preview."""

import reflex as rx
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark")

# JavaScript to read selection from the textarea
SELECTION_JS = (
    "(() => {"
    "  const el = document.getElementById('md-source');"
    "  return [el.selectionStart, el.selectionEnd];"
    "})()"
)


class State(rx.State):
    """The app state."""

    source: str = ""
    selection_start: int = 0
    selection_end: int = 0

    @rx.var(cache=True)
    def preview_html(self) -> str:
        """Convert markdown source to HTML."""
        return md.render(self.source)

    @rx.var(cache=True)
    def word_count(self) -> int:
        """Return the number of words in the source."""
        if not self.source:
            return 0
        return len(self.source.split())

    @rx.var(cache=True)
    def char_count(self) -> int:
        """Return the number of characters in the source."""
        return len(self.source)

    @rx.var(cache=True)
    def counter_text(self) -> str:
        """Return the formatted counter text."""
        return f"Words: {self.word_count} | Characters: {self.char_count}"

    def update_selection(self, selection: list):
        """Update the selection range from the textarea."""
        self.selection_start = int(selection[0])
        self.selection_end = int(selection[1])

    def wrap_bold(self, selection: list):
        """Wrap the selected text with ** markers."""
        start = int(selection[0])
        end = int(selection[1])
        self.selection_start = start
        self.selection_end = end
        before = self.source[:start]
        selected = self.source[start:end]
        after = self.source[end:]
        self.source = before + "**" + selected + "**" + after

    def wrap_italic(self, selection: list):
        """Wrap the selected text with * markers."""
        start = int(selection[0])
        end = int(selection[1])
        self.selection_start = start
        self.selection_end = end
        before = self.source[:start]
        selected = self.source[start:end]
        after = self.source[end:]
        self.source = before + "*" + selected + "*" + after

    def wrap_code(self, selection: list):
        """Wrap the selected text with ` markers."""
        start = int(selection[0])
        end = int(selection[1])
        self.selection_start = start
        self.selection_end = end
        before = self.source[:start]
        selected = self.source[start:end]
        after = self.source[end:]
        self.source = before + "`" + selected + "`" + after


def index() -> rx.Component:
    """The main page layout."""
    return rx.box(
        rx.vstack(
            # Toolbar
            rx.hstack(
                rx.button(
                    "Bold",
                    id="btn-bold",
                    on_click=rx.call_script(
                        SELECTION_JS,
                        callback=State.wrap_bold,
                    ),
                ),
                rx.button(
                    "Italic",
                    id="btn-italic",
                    on_click=rx.call_script(
                        SELECTION_JS,
                        callback=State.wrap_italic,
                    ),
                ),
                rx.button(
                    "Code",
                    id="btn-code",
                    on_click=rx.call_script(
                        SELECTION_JS,
                        callback=State.wrap_code,
                    ),
                ),
                spacing="2",
            ),
            # Editor and Preview
            rx.hstack(
                rx.text_area(
                    id="md-source",
                    value=State.source,
                    on_change=State.set_source,
                    on_mouse_up=rx.call_script(
                        SELECTION_JS,
                        callback=State.update_selection,
                    ),
                    on_key_up=rx.call_script(
                        SELECTION_JS,
                        callback=State.update_selection,
                    ),
                    style={
                        "width": "50%",
                        "min_height": "400px",
                        "font_family": "monospace",
                    },
                ),
                rx.box(
                    rx.html(State.preview_html),
                    id="md-preview",
                    style={
                        "width": "50%",
                        "min_height": "400px",
                        "padding": "1rem",
                        "overflow": "auto",
                        "border": "1px solid #ccc",
                    },
                ),
                spacing="4",
                align="start",
                width="100%",
            ),
            # Counter
            rx.text(
                State.counter_text,
                id="md-counter",
            ),
            spacing="4",
            align="start",
            width="100%",
        ),
        padding="2rem",
        width="100%",
    )


app = rx.App()
app.add_page(index)