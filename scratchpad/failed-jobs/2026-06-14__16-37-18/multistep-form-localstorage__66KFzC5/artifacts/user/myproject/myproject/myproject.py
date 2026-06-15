import reflex as rx

class State(rx.State):
    """The app state."""
    step: int = 1
    submitted: bool = False
    
    name: str = rx.LocalStorage("", name="name")
    email: str = rx.LocalStorage("", name="email")
    address: str = rx.LocalStorage("", name="address")
    city: str = rx.LocalStorage("", name="city")
    password: str = rx.LocalStorage("", name="password")
    confirm_password: str = rx.LocalStorage("", name="confirm_password")
    
    def set_name(self, val: str):
        self.name = val

    def set_email(self, val: str):
        self.email = val

    def set_address(self, val: str):
        self.address = val

    def set_city(self, val: str):
        self.city = val

    def set_password(self, val: str):
        self.password = val

    def set_confirm_password(self, val: str):
        self.confirm_password = val

    def next_step(self):
        if self.step == 1:
            if self.name.strip() and self.email.strip() and "@" in self.email:
                self.step += 1
        elif self.step == 2:
            if self.address.strip() and self.city.strip():
                self.step += 1
        elif self.step == 3:
            if self.password and self.confirm_password and self.password == self.confirm_password:
                self.submitted = True
                self.name = ""
                self.email = ""
                self.address = ""
                self.city = ""
                self.password = ""
                self.confirm_password = ""

    def prev_step(self):
        if self.step > 1:
            self.step -= 1


def step1() -> rx.Component:
    return rx.vstack(
        rx.heading("Step 1: Personal Info"),
        rx.input(placeholder="Name", value=State.name, on_change=State.set_name, name="name"),
        rx.input(placeholder="Email", value=State.email, on_change=State.set_email, name="email"),
        rx.button("Next", on_click=State.next_step),
    )

def step2() -> rx.Component:
    return rx.vstack(
        rx.heading("Step 2: Address"),
        rx.input(placeholder="Address", value=State.address, on_change=State.set_address, name="address"),
        rx.input(placeholder="City", value=State.city, on_change=State.set_city, name="city"),
        rx.button("Back", on_click=State.prev_step),
        rx.button("Next", on_click=State.next_step),
    )

def step3() -> rx.Component:
    return rx.vstack(
        rx.heading("Step 3: Password"),
        rx.input(placeholder="Password", value=State.password, on_change=State.set_password, type="password", name="password"),
        rx.input(placeholder="Confirm Password", value=State.confirm_password, on_change=State.set_confirm_password, type="password", name="confirm_password"),
        rx.button("Back", on_click=State.prev_step),
        rx.button("Submit", on_click=State.next_step),
    )

def index() -> rx.Component:
    return rx.container(
        rx.cond(
            State.submitted,
            rx.heading("Registration complete"),
            rx.match(
                State.step,
                (1, step1()),
                (2, step2()),
                (3, step3()),
                step1(),
            )
        )
    )

app = rx.App()
app.add_page(index, route="/")
