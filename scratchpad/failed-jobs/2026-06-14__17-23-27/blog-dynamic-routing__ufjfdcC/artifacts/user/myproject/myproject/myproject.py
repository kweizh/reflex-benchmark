"""A minimal blog with dynamic routing using Reflex."""

import reflex as rx

# Hardcoded blog posts — exactly 3 entries with unique slugs.
POSTS = [
    {
        "id": 1,
        "slug": "hello-world",
        "title": "Hello World",
        "content": "This is the very first post on our blog. Welcome!",
    },
    {
        "id": 2,
        "slug": "reflex-rocks",
        "title": "Reflex Rocks",
        "content": "Building full-stack apps with pure Python is amazing.",
    },
    {
        "id": 3,
        "slug": "dynamic-routing",
        "title": "Dynamic Routing in Reflex",
        "content": "Learn how to use [slug] segments to create dynamic pages.",
    },
]


class PostState(rx.State):
    """State for the post detail page.

    The dynamic route /posts/[slug] automatically creates the computed var
    ``slug`` that reads the slug from the URL.
    """

    @rx.var
    def current_post(self) -> dict:
        """Return the post matching the dynamic slug, or an empty dict."""
        for post in POSTS:
            if post["slug"] == self.slug:
                return post
        return {}

    @rx.var
    def post_title(self) -> str:
        """The title of the current post, or a fallback."""
        post = self.current_post
        return post.get("title", "Post Not Found")

    @rx.var
    def post_content(self) -> str:
        """The content of the current post, or a fallback."""
        post = self.current_post
        return post.get(
            "content",
            "Sorry, no post exists with that slug.",
        )


@rx.page(route="/posts/[slug]", title="Blog Post")
def post_detail() -> rx.Component:
    """Render a single blog post identified by the URL slug."""
    return rx.container(
        rx.vstack(
            rx.heading(PostState.post_title, size="8"),
            rx.text(PostState.post_content, size="4"),
            rx.link(
                rx.button("← Back to Posts"),
                href="/",
            ),
            spacing="5",
            align="start",
            padding_top="2em",
        ),
    )


def index() -> rx.Component:
    """Home page that lists all posts with links to their detail pages."""
    return rx.container(
        rx.vstack(
            rx.heading("My Blog", size="9"),
            rx.text("Click a post to read more:", size="4"),
            rx.vstack(
                *[
                    rx.link(
                        post["title"],
                        href=f"/posts/{post['slug']}",
                        font_size="1.2em",
                    )
                    for post in POSTS
                ],
                spacing="3",
                align="start",
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
