"""Minimal blog application with dynamic routing."""

from typing import TypedDict

import reflex as rx

from rxconfig import config


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Post(TypedDict):
    id: int
    slug: str
    title: str
    content: str


POSTS: list[Post] = [
    {
        "id": 1,
        "slug": "hello-world",
        "title": "Hello, World!",
        "content": (
            "Welcome to our blog! This is the very first post. "
            "We are excited to share ideas, tutorials, and updates with you."
        ),
    },
    {
        "id": 2,
        "slug": "getting-started-with-reflex",
        "title": "Getting Started with Reflex",
        "content": (
            "Reflex is a full-stack Python framework that lets you build "
            "web applications entirely in Python. It compiles your UI "
            "definitions to a Next.js frontend and a FastAPI backend, "
            "so you get a fast, reactive app without writing any JavaScript."
        ),
    },
    {
        "id": 3,
        "slug": "dynamic-routing-in-reflex",
        "title": "Dynamic Routing in Reflex",
        "content": (
            "Reflex supports dynamic URL segments using the familiar "
            "Next.js bracket syntax, e.g. /posts/[slug]. "
            "You can read the current segment value from "
            "self.router.page.params inside any State subclass, "
            "making it straightforward to build detail pages that "
            "respond to the URL."
        ),
    },
]

# Handy lookup by slug
_POSTS_BY_SLUG: dict[str, Post] = {p["slug"]: p for p in POSTS}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class BlogState(rx.State):
    """Application state for the blog."""

    @rx.var
    def current_slug(self) -> str:
        """Return the slug URL segment (empty string when not on a post page)."""
        # Use the private _page attribute to avoid the deprecated .page property.
        # Reflex itself uses this path internally for dynamic route vars.
        return self.router._page.params.get("slug", "")

    @rx.var
    def current_post(self) -> Post | None:
        """Return the Post matching the current URL slug, or None."""
        slug = self.current_slug
        return _POSTS_BY_SLUG.get(slug)

    @rx.var
    def post_title(self) -> str:
        post = self.current_post
        return post["title"] if post else ""

    @rx.var
    def post_content(self) -> str:
        post = self.current_post
        return post["content"] if post else ""

    @rx.var
    def post_found(self) -> bool:
        return self.current_post is not None


# ---------------------------------------------------------------------------
# Index page  –  list all posts
# ---------------------------------------------------------------------------

def post_card(post: Post) -> rx.Component:
    """Render a single post preview card."""
    return rx.box(
        rx.heading(post["title"], size="5"),
        rx.link(
            rx.button("Read post →", variant="soft"),
            href=f"/posts/{post['slug']}",
        ),
        padding="1em",
        border="1px solid #e2e8f0",
        border_radius="8px",
        width="100%",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("My Blog", size="8", margin_bottom="0.5em"),
            rx.text("Welcome! Choose a post to read.", color_scheme="gray"),
            rx.divider(margin_y="1em"),
            *[post_card(p) for p in POSTS],
            spacing="4",
            align="start",
            width="100%",
        ),
        max_width="640px",
        margin="0 auto",
        padding="2em",
    )


# ---------------------------------------------------------------------------
# Post detail page  –  dynamic route /posts/[slug]
# ---------------------------------------------------------------------------

def post_detail() -> rx.Component:
    return rx.container(
        rx.cond(
            BlogState.post_found,
            # ── Post found ──────────────────────────────────────────────────
            rx.vstack(
                rx.heading(BlogState.post_title, size="7"),
                rx.divider(margin_y="0.5em"),
                rx.text(BlogState.post_content, size="3"),
                rx.link(
                    rx.button("← Back to Posts", variant="outline"),
                    href="/",
                    margin_top="1.5em",
                ),
                spacing="4",
                align="start",
                width="100%",
            ),
            # ── Post not found ──────────────────────────────────────────────
            rx.vstack(
                rx.heading("Post not found", size="6", color_scheme="red"),
                rx.text(
                    "Sorry, we couldn't find a post with that slug.",
                    color_scheme="gray",
                ),
                rx.link(
                    rx.button("← Back to Posts", variant="outline"),
                    href="/",
                    margin_top="1em",
                ),
                spacing="4",
                align="start",
            ),
        ),
        max_width="640px",
        margin="0 auto",
        padding="2em",
    )


# ---------------------------------------------------------------------------
# App & page registration
# ---------------------------------------------------------------------------

app = rx.App()
app.add_page(index, route="/")
app.add_page(post_detail, route="/posts/[slug]")
