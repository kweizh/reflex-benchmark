import reflex as rx

config = rx.Config(
    app_name="myproject",
    db_url="sqlite:///reflex.db",
    frontend_port=3000,
    backend_port=8000,
)
