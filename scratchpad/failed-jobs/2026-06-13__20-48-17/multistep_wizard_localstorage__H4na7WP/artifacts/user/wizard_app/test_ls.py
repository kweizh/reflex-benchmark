import reflex as rx
class State(rx.State):
    val: str = rx.LocalStorage("hello", name="test_ls")
