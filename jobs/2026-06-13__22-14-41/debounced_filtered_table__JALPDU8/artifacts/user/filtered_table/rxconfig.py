import reflex as rx

config = rx.Config(
    app_name="filtered_table",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)