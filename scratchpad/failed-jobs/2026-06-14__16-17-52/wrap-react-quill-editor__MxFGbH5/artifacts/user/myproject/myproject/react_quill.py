"""ReactQuill rich-text editor wrapped as a Reflex NoSSRComponent."""

from __future__ import annotations

import reflex as rx
from reflex.components.component import NoSSRComponent


class ReactQuill(NoSSRComponent):
    """A Quill rich-text editor component (client-side only)."""

    library: str = "react-quill@2.0.0"
    tag: str = "ReactQuill"
    is_default: bool = True

    # The HTML content controlled by the editor.
    value: rx.Var[str]

    # Fired with the new HTML string every time the user edits.
    on_change: rx.EventHandler[lambda v: [v]]


# Module-level factory for ergonomic use.
react_quill = ReactQuill.create
