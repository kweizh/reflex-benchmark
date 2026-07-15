# Threaded Comment System with Reflex and SQLite

## Background
Build a full-stack threaded (nested) comment board using the **Reflex** Python web framework, persisted in a local SQLite database. Comments form a tree: every comment may have an optional parent, and replies can nest arbitrarily deep. The UI renders the whole tree recursively, and readers can reply to any comment or upvote it. All data is stored locally in SQLite via `rx.session`; there are no external services.

## Requirements
- Define a self-referential comment model (a Reflex `rx.Model` table) with an author, a body, an optional `parent_id` referencing another comment (null for a top-level/root comment), and an integer vote count that starts at 0.
- Build the nested comment tree in the backend from the flat rows and render it in the UI using a **recursive** `rx.foreach` so that replies appear nested under their parent to any depth.
- Provide a way in the UI to post a new top-level comment and to reply to any existing comment (an event handler that receives the target parent id), plus an upvote control on every comment (an event handler that receives the target comment id). Replies and votes must persist to SQLite.
- Use a computed var to derive the total number of comments, and derive a per-comment **score** for every node.
- In addition to the UI, expose a small read/write JSON API on the same Reflex FastAPI backend (mount a FastAPI app via the Reflex app's `api_transformer`) that operates on the same database and the same tree-building / score logic. This API is what automated checks will use.

## Implementation Hints
- Use `uv` to manage the Python environment (`uv add reflex`, `uv run reflex ...`). The project is scaffolded with the blank template and its dependencies are already installed.
- Reflex cannot use a Python `for` loop over state vars; render the tree with `rx.foreach`, and make the per-node render function call itself to render each node's children recursively.
- Persist all writes with `rx.session()` and `session.commit()`. The database must be the project's local SQLite file configured as `db_url="sqlite:///reflex.db"` (so the file lives at the project root).
- Share one helper that turns the flat comment rows into the nested tree, and reuse it for both the UI computed var and the JSON API so both stay consistent.
- **Score definition**: a comment's `score` is its own `votes` plus the sum of the `score` of all of its descendants (i.e. the total votes of its entire subtree, including itself).
- Project path: /home/user/threaded_comments
- Start command: `uv run reflex run` (run from the project path). Frontend serves on port 3000 and backend on port 8000.
- Database file: /home/user/threaded_comments/reflex.db (SQLite, configured via `db_url="sqlite:///reflex.db"`).
- The UI page at `/` (http://localhost:3000) must render the recursive comment tree and display the total comment count. Include the exact heading text `Threaded Comments` somewhere on the page.
- JSON API endpoints on the backend (http://localhost:8000), all using standard JSON:
  - `GET /api/comments`: returns status 200 and a JSON array of the **root** comment nodes (those with no parent), ordered by ascending id. Each node object must have exactly the keys `id`, `author`, `body`, `votes`, `score`, and `children`, where `children` is an array of child node objects using the same shape, each ordered by ascending id, nested to full depth.

    ```json
    {
      "id": number,
      "author": string,
      "body": string,
      "votes": number,
      "score": number,
      "children": []
    }
    ```

  - `GET /api/stats`: returns status 200 and `{"total_comments": number}` where the value is the total number of comment rows in the database.
  - `POST /api/comments`: accepts `{"author": string, "body": string, "parent_id": number | null}` and creates a comment. When `parent_id` is null or omitted the comment is a root comment. If `parent_id` refers to a comment that does not exist, return status 404. On success return status 201 with `{"id": number}` (the new comment id).
  - `POST /api/comments/{comment_id}/upvote`: increments that comment's vote count by 1 and returns status 200 with `{"id": number, "votes": number}` (the new vote count). If the comment does not exist, return status 404.
- The database starts empty (no seed data): a freshly started server must report `total_comments` of 0. The app must create its database schema automatically at startup when the SQLite file does not exist yet (for example using Reflex's model create/migrate helpers), so it works against a fresh database without any manual migration commands.
- After you finish and verify your work, you MUST stop/kill every background process or dev server you started (e.g. any `reflex run`), so no server is left listening on ports 3000 or 8000.

