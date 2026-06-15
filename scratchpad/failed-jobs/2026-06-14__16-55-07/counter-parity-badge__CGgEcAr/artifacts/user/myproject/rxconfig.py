import reflex as rx

config = rx.Config(
    app_name="myproject",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)