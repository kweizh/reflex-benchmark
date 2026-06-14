import reflex as rx

config = rx.Config(
    app_name="kanban_drag_drop_persistence",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)