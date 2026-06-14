import reflex as rx

config = rx.Config(
    app_name="email_scheduler",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)