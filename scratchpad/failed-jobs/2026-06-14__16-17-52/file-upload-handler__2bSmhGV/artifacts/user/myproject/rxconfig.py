import reflex as rx

config = rx.Config(
    app_name="myproject",
    frontend_port=3000,
    backend_port=8000,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
