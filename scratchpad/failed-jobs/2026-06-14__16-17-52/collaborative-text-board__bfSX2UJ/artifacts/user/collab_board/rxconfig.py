import reflex as rx

config = rx.Config(
    app_name="collab_board",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)