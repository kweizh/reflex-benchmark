"""React-Quill wrapper for Reflex."""

import reflex as rx
from reflex.components.component import NoSSRComponent


class ReactQuill(NoSSRComponent):
    """A Reflex wrapper around the react-quill rich-text editor."""

    library = "react-quill@2.0.0"
    tag = "ReactQuill"

    lib_dependencies: list[str] = ["quill@2.0.0"]

    value: rx.Var[str] = ""

    on_change: rx.EventHandler[lambda v: [v]] = None  # type: ignore


react_quill = ReactQuill.create