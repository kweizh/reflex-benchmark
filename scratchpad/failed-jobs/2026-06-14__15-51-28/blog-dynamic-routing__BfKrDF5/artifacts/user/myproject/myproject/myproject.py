import reflex as rx

class BlogState(rx.State):
    # Exactly 3 hardcoded blog posts
    posts: list[dict] = [
        {
            "id": 1,
            "slug": "first-post",
            "title": "First Blog Post",
            "content": "This is the content of the first blog post. Reflex is pretty awesome!"
        },
        {
            "id": 2,
            "slug": "second-post",
            "title": "Second Blog Post",
            "content": "In this second post, we explore dynamic routing in Reflex using square brackets."
        },
        {
            "id": 3,
            "slug": "third-post",
            "title": "Third Blog Post",
            "content": "Wrapping up our minimal blog with Reflex. Build, run, and export with ease!"
        }
    ]

    @rx.var
    def current_slug(self) -> str:
        # Access the dynamic slug through the Reflex router API
        params = self.router.page.params
        return params.get("slug", "")

    @rx.var
    def post_exists(self) -> bool:
        slug = self.current_slug
        return any(post["slug"] == slug for post in self.posts)

    @rx.var
    def post_title(self) -> str:
        slug = self.current_slug
        for post in self.posts:
            if post["slug"] == slug:
                return post["title"]
        return "Post Not Found"

    @rx.var
    def post_content(self) -> str:
        slug = self.current_slug
        for post in self.posts:
            if post["slug"] == slug:
                return post["content"]
        return "The requested blog post could not be found. Please check the URL or return to the home page."


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("My Reflex Blog", size="9"),
            rx.text("Welcome to my minimal blog built with Reflex and Python!", size="4"),
            rx.divider(margin_y="1em"),
            rx.vstack(
                # Post 1
                rx.box(
                    rx.heading("First Blog Post", size="6"),
                    rx.text("This is the content of the first blog post. Reflex is pretty awesome!", line_clamp=1, size="2"),
                    rx.link("Read More", href="/posts/first-post", size="3", color_scheme="blue"),
                    border="1px solid #ccc",
                    padding="1.5em",
                    border_radius="8px",
                    width="100%",
                ),
                # Post 2
                rx.box(
                    rx.heading("Second Blog Post", size="6"),
                    rx.text("In this second post, we explore dynamic routing in Reflex using square brackets.", line_clamp=1, size="2"),
                    rx.link("Read More", href="/posts/second-post", size="3", color_scheme="blue"),
                    border="1px solid #ccc",
                    padding="1.5em",
                    border_radius="8px",
                    width="100%",
                ),
                # Post 3
                rx.box(
                    rx.heading("Third Blog Post", size="6"),
                    rx.text("Wrapping up our minimal blog with Reflex. Build, run, and export with ease!", line_clamp=1, size="2"),
                    rx.link("Read More", href="/posts/third-post", size="3", color_scheme="blue"),
                    border="1px solid #ccc",
                    padding="1.5em",
                    border_radius="8px",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            spacing="5",
            align_items="start",
            padding="2em",
        )
    )


def post_detail() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.cond(
                BlogState.post_exists,
                rx.vstack(
                    rx.heading(BlogState.post_title, size="9"),
                    rx.text(BlogState.post_content, size="5", margin_top="1em"),
                    spacing="4",
                    align_items="start",
                    width="100%",
                ),
                rx.vstack(
                    rx.heading(BlogState.post_title, size="9", color="red"),
                    rx.text(BlogState.post_content, size="5", margin_top="1em"),
                    spacing="4",
                    align_items="start",
                    width="100%",
                ),
            ),
            rx.divider(margin_y="2em"),
            rx.link(
                "Back to Posts",
                href="/",
                size="4",
                color_scheme="blue",
            ),
            spacing="5",
            align_items="start",
            padding="2em",
        )
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(post_detail, route="/posts/[slug]")
