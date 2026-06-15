import reflex as rx

class ReactQuill(rx.NoSSRComponent):
    library = "react-quill@2.0.0"
    tag = "ReactQuill"
    
    value: rx.Var[str]
    
    on_change: rx.EventHandler[lambda v: [v]]

react_quill = ReactQuill.create
