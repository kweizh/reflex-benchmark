import reflex as rx
from typing import Any
from reflex_components_core.el.elements.forms import Textarea

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

print("Subclassed successfully!")
