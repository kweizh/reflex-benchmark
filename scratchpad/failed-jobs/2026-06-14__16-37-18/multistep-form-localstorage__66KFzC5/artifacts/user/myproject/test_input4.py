import reflex as rx

class State(rx.State):
    email: str = rx.LocalStorage("", name="email")
    
    def set_email(self, email: str):
        self.email = email

def index():
    return rx.input(value=State.email, on_change=State.set_email)

app = rx.App()
app.add_page(index)
