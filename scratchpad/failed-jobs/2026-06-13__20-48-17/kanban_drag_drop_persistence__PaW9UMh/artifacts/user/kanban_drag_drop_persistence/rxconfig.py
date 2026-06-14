import reflex as rx
import os

config = rx.Config(
    app_name="kanban_drag_drop_persistence",
    db_url=f"sqlite:///{os.path.abspath('reflex.db')}",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)