"""Reflex Blog with Dynamic Routing."""

import reflex as rx


class BlogState(rx.State):
    """State for the blog application."""

    posts: list[dict] = [
        {
            "id": 1,
            "slug": "first-post",
            "title": "First Post",
            "content": "Welcome to our blog! This is the very first post where we share our thoughts and get started with writing.",
        },
        {
            "id": 2,
            "slug": "second-post",
            "title": "Second Post",
            "content": "In this second post, we dive deeper into our journey and explore new ideas together.",
        },
        {
            "id": 3,
            "slug": "third-post",
            "title": "Third Post",
            "content": "Our third post wraps up the series with final reflections and a look toward the future.",
        },
    ]

    @rx.var
    def current_slug(self) -> str:
        """Get the slug from the router URL path parameters."""
        return self.router.page.params.get("slug", "")

    @rx.var
    def current_post(self) -> dict:
        """Get the post matching the current slug."""
        for post in self.posts:
            if post["slug"] == self.current_slug:
                return post
        return {}


def index() -> rx.Component:
    """The home page listing all blog posts."""
    return rx.box(
        rx.heading("Blog Posts", size="8", margin_bottom="1rem"),
        rx.list(
            rx.foreach(
                BlogState.posts,
                lambda post: rx.list_item(
                    rx.link(
                        rx.text(post["title"], font_size="1.25rem", font_weight="bold"),
                        href=f"/posts/{post['slug']}",
                    ),
                    rx.text(post["content"], margin_top="0.25rem", color="gray"),
                    margin_bottom="1rem",
                ),
            ),
        ),
        padding="2rem",
        max_width="800px",
        margin_x="auto",
    )


def post_detail() -> rx.Component:
    """The post detail page showing a single post."""
    return rx.box(
        rx.link("Back to Posts", href="/", margin_bottom="1rem", display="inline-block"),
        rx.cond(
            BlogState.current_post,
            rx.box(
                rx.heading(BlogState.current_post["title"], size="8", margin_bottom="1rem"),
                rx.text(BlogState.current_post["content"], font_size="1.1rem"),
            ),
            rx.box(
                rx.heading("Post Not Found", size="8", margin_bottom="1rem"),
                rx.text("The post you are looking for does not exist."),
            ),
        ),
        padding="2rem",
        max_width="800px",
        margin_x="auto",
    )


app = rx.App()
app.add_page(index, route="/", title="Blog")
app.add_page(post_detail, route="/posts/[slug]", title="Post Detail")