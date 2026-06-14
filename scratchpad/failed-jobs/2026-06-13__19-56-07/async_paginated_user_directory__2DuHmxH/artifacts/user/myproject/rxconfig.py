import reflex as rx

config = rx.Config(
    app_name="myproject",
    db_url="sqlite:///reflex.db",
)
config.db_url = "sqlite+aiosqlite:///reflex.db"
