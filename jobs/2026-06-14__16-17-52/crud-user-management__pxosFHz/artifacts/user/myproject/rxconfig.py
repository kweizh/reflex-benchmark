import reflex as rx

config = rx.Config(
    app_name="myproject",
    frontend_port=3000,
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
