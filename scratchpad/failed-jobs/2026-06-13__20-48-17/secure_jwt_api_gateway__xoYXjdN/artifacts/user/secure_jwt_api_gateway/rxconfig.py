import reflex as rx

config = rx.Config(
    app_name="secure_jwt_api_gateway",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)