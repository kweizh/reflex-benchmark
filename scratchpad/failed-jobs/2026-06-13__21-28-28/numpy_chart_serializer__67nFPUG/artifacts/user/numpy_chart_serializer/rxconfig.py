import reflex as rx

config = rx.Config(
    app_name="numpy_chart_serializer",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)