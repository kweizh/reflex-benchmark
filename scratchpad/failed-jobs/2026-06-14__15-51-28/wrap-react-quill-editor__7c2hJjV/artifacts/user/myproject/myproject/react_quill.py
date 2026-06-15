import reflex as rx
from reflex.components.component import NoSSRComponent

class ReactQuill(NoSSRComponent):
    library = "react-quill@2.0.0"
    tag = "ReactQuill"
    lib_dependencies = ["quill@2.0.0"]

    value: rx.Var[str]
    on_change: rx.EventHandler[lambda v: [v]]

    def add_imports(self) -> dict[str, str | list[str]]:
        return {"": "react-quill/dist/quill.snow.css"}

react_quill = ReactQuill.create
