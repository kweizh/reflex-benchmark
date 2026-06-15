import reflex as rx

config = rx.Config(
    app_name="myproject",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
    stylesheets=[
        "https://cdn.quilljs.com/1.3.6/quill.snow.css",
    ],
)