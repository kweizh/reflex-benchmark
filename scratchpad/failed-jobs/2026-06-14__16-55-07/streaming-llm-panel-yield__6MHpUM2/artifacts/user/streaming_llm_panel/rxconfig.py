import reflex as rx

config = rx.Config(
    app_name="streaming_llm_panel",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)