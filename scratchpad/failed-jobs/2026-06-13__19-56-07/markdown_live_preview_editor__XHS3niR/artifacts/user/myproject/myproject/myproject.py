import reflex as rx
from markdown_it import MarkdownIt

md = MarkdownIt()

class State(rx.State):
    source: str = ""
    selection_start: int = 0
    selection_end: int = 0

    @rx.var(cache=True)
    def preview_html(self) -> str:
        return md.render(self.source)

    @rx.var(cache=True)
    def word_count(self) -> int:
        return len(self.source.split()) if self.source.strip() else 0

    @rx.var(cache=True)
    def char_count(self) -> int:
        return len(self.source)

    @rx.var(cache=True)
    def counter_text(self) -> str:
        return f"Words: {self.word_count} | Characters: {self.char_count}"

    def update_selection(self, start: int, end: int):
        self.selection_start = start
        self.selection_end = end

    def handle_change(self, value: str, start: int, end: int):
        self.source = value
        self.selection_start = start
        self.selection_end = end

    def wrap_bold(self):
        start, end = self.selection_start, self.selection_end
        selected = self.source[start:end]
        self.source = self.source[:start] + f"**{selected}**" + self.source[end:]
        new_pos = start + 2 if start == end else start + 2 + len(selected) + 2
        return rx.call_script(
            f"const el = document.getElementById('md-source'); if(el) {{ el.setSelectionRange({new_pos}, {new_pos}); el.focus(); }}"
        )

    def wrap_italic(self):
        start, end = self.selection_start, self.selection_end
        selected = self.source[start:end]
        self.source = self.source[:start] + f"*{selected}*" + self.source[end:]
        new_pos = start + 1 if start == end else start + 1 + len(selected) + 1
        return rx.call_script(
            f"const el = document.getElementById('md-source'); if(el) {{ el.setSelectionRange({new_pos}, {new_pos}); el.focus(); }}"
        )

    def wrap_code(self):
        start, end = self.selection_start, self.selection_end
        selected = self.source[start:end]
        self.source = self.source[:start] + f"`{selected}`" + self.source[end:]
        new_pos = start + 1 if start == end else start + 1 + len(selected) + 1
        return rx.call_script(
            f"const el = document.getElementById('md-source'); if(el) {{ el.setSelectionRange({new_pos}, {new_pos}); el.focus(); }}"
        )

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.hstack(
                rx.button("Bold", id="btn-bold", on_click=State.wrap_bold),
                rx.button("Italic", id="btn-italic", on_click=State.wrap_italic),
                rx.button("Code", id="btn-code", on_click=State.wrap_code),
                spacing="2",
            ),
            rx.hstack(
                rx.vstack(
                    rx.el.textarea(
                        id="md-source",
                        value=State.source,
                        on_change=State.handle_change(
                            rx.event_args[0].target.value,
                            rx.event_args[0].target.selectionStart,
                            rx.event_args[0].target.selectionEnd,
                        ),
                        on_click=State.update_selection(
                            rx.event_args[0].target.selectionStart,
                            rx.event_args[0].target.selectionEnd,
                        ),
                        on_key_up=State.update_selection(
                            rx.event_args[0].target.selectionStart,
                            rx.event_args[0].target.selectionEnd,
                        ),
                        on_select=State.update_selection(
                            rx.event_args[0].target.selectionStart,
                            rx.event_args[0].target.selectionEnd,
                        ),
                        style={
                            "width": "100%",
                            "height": "400px",
                            "padding": "1em",
                            "font-family": "monospace",
                        },
                    ),
                    rx.text(
                        State.counter_text,
                        id="md-counter",
                    ),
                    width="100%",
                ),
                rx.box(
                    rx.html(State.preview_html),
                    id="md-preview",
                    width="100%",
                    height="400px",
                    overflow="auto",
                    border="1px solid #ccc",
                    padding="1em",
                ),
                width="100%",
                spacing="4",
            ),
            width="100%",
            padding="2em",
        ),
        max_width="1200px",
    )

app = rx.App()
app.add_page(index)
