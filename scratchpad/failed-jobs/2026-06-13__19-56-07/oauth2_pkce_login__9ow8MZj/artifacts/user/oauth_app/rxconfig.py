import reflex as rx

config = rx.Config(
    app_name="oauth_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)