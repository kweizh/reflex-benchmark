# Reflex Blog with Dynamic Routing

## Background
Reflex is a full-stack Python framework that compiles Python UI definitions to a Next.js frontend and a FastAPI backend. In this task you will build a minimal blog with dynamic routing so each post is reachable at its own URL based on a slug segment.

## Requirements
- Build a Reflex application that:
  - Renders a home page at `/` listing exactly 3 hardcoded blog posts. Each post is an object with the fields `id`, `slug`, `title`, and `content`.
  - Renders a post detail page at the dynamic route `/posts/[slug]` showing a single post's title and content based on the `slug` URL segment.
  - Provides navigation from the index to each post detail page.
  - Shows a "Back to Posts" link on every detail page that navigates back to `/`.

## Implementation Hints
- Use the Reflex blank template and the `uv` package manager so that the dev environment is reproducible.
- Register the detail page with the route pattern `/posts/[slug]`, using either the `@rx.page(route=...)` decorator or `app.add_page(..., route=...)`.
- Read the dynamic slug from `self.router.page.params['slug']` (or the equivalent latest router API such as `self.router.url.path`) inside a state class, typically through a computed var.
- The list of posts can live as a class-level constant or as a base var. Keep the slugs unique across posts so each detail page is reachable.
- When the detail page receives an unknown slug, show a friendly fallback message instead of crashing.

## Acceptance Criteria
- Project path: /home/user/myproject
- Start command: `uv run reflex run`
- Ports: frontend on 3000, backend on 8000
- Routes:
  - `GET /` returns an HTML page that lists the title of each of the 3 posts and contains a link to that post's detail page under `/posts/<slug>`.
  - `GET /posts/<slug>` returns an HTML page that renders the title and content of the corresponding post and contains a link back to `/`.
- The Reflex source code must contain a page registration whose route is exactly `/posts/[slug]`, expressed using either `@rx.page(route="/posts/[slug]")` or `app.add_page(..., route="/posts/[slug]")`.
- The Reflex source code must access the dynamic slug through the Reflex router API (e.g., `self.router.page.params` or `self.router.url`) from inside a Reflex State subclass.
- The hardcoded posts collection must contain exactly 3 entries and each entry must have a unique non-empty `slug` value.
- Running `uv run reflex export --frontend-only --no-zip` inside the project directory must succeed and produce a Next.js build output that contains a generated page file for the dynamic route `posts/[slug]` (for example a path matching `.web/pages/posts/[slug].js`, `.web/.next/server/pages/posts/[slug].html`, or an equivalent file under `_export/`). The literal title of at least one of the three posts must appear somewhere in the generated build output.
- Kill all background servers started during the task (frontend, backend, dev server) before finishing.

