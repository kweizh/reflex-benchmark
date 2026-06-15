import reflex as rx

class State(rx.State):
    email: str = rx.LocalStorage("", name="email")

print(getattr(State, "set_email"))
