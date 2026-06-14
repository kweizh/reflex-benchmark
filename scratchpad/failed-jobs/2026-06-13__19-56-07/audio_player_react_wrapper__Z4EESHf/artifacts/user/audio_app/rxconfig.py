import reflex as rx

config = rx.Config(
    app_name="audio_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)