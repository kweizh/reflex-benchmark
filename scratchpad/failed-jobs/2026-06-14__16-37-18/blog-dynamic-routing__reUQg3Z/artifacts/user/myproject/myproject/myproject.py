import reflex as rx

POSTS = [
    {"id": 1, "slug": "first-post", "title": "First Post", "content": "This is the first post."},
    {"id": 2, "slug": "second-post", "title": "Second Post", "content": "Here is the second post."},
    {"id": 3, "slug": "third-post", "title": "Third Post", "content": "And the third one."}
]

class PostState(rx.State):
    @rx.var
    def post_slug(self) -> str:
        return self.router.page.params.get("slug", "")
        
    @rx.var
    def post_title(self) -> str:
        slug = self.post_slug
        for p in POSTS:
            if p["slug"] == slug:
                return p["title"]
        return ""

    @rx.var
    def post_content(self) -> str:
        slug = self.post_slug
        for p in POSTS:
            if p["slug"] == slug:
                return p["content"]
        return ""

    @rx.var
    def post_exists(self) -> bool:
        slug = self.post_slug
        return any(p["slug"] == slug for p in POSTS)

def index() -> rx.Component:
    return rx.container(
        rx.heading("Blog Posts"),
        rx.vstack(
            *[
                rx.link(
                    rx.text(post["title"]),
                    href=f"/posts/{post['slug']}"
                )
                for post in POSTS
            ]
        )
    )

@rx.page(route="/posts/[slug]")
def post_detail() -> rx.Component:
    return rx.container(
        rx.cond(
            PostState.post_exists,
            rx.vstack(
                rx.heading(PostState.post_title),
                rx.text(PostState.post_content),
                rx.link("Back to Posts", href="/")
            ),
            rx.vstack(
                rx.heading("Post not found"),
                rx.text("The post you are looking for does not exist."),
                rx.link("Back to Posts", href="/")
            )
        )
    )

app = rx.App()
app.add_page(index, route="/")
