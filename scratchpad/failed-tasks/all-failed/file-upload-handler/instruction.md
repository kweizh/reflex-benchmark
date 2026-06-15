# Reflex File Upload Handler

## Background
Build a Reflex web application that allows end users to upload text and image files through the browser. Reflex provides an `rx.upload(...)` component along with helper utilities such as `rx.get_upload_dir()` for persisting files server-side and `rx.foreach` for rendering dynamic lists from state.

## Requirements
- Implement a Reflex app that renders a single page with:
  - An `rx.upload(...)` component that accepts ONLY plain text (`.txt`) and PNG image (`.png`) files.
  - A button that triggers the upload to the backend.
  - A dynamic list of every successfully uploaded filename that updates after each upload.
- The backend must read each uploaded file asynchronously, save the bytes to the Reflex upload directory using the original filename, and append that filename to the state list.
- The application must run with the standard Reflex frontend on port 3000 and the backend on port 8000.

## Implementation Hints
- Use `uv` to manage the Python environment as described in the Reflex setup workflow (`uv init`, `uv add reflex`, `uv run reflex init --template blank`).
- The `rx.upload` component must specify an explicit `id="upload1"` and an `accept` prop mapping the MIME types `"text/plain"` and `"image/png"` to their respective file extensions.
- Define a state class with a single base var `uploaded_files: list[str] = []`.
- The upload event handler must be an `async` method accepting `files: list[rx.UploadFile]`. For each file, await `file.read()` to read the bytes, write them to a path obtained from `rx.get_upload_dir()`, and append the filename to `uploaded_files`.
- Render the dynamic list of filenames using `rx.foreach(State.uploaded_files, ...)`.
- Bind a button's `on_click` to `State.handle_upload(rx.upload_files(upload_id="upload1"))` to trigger the upload.
- Make sure to kill any background processes (`reflex run`, `next`, `uvicorn`, etc.) you start before reporting the task complete.

## Acceptance Criteria
- Project path: /home/user/myproject
- Start command: `cd /home/user/myproject && uv run reflex run --loglevel debug`
- Frontend port: 3000
- Backend port: 8000
- The Reflex application must define a state class with a base var `uploaded_files: list[str] = []`.
- The state class must define an async event handler `handle_upload(self, files: list[rx.UploadFile])` that:
  - Reads each uploaded file's bytes via `await file.read()`.
  - Saves the bytes to the directory returned by `rx.get_upload_dir()` using the original filename.
  - Appends the original filename to `uploaded_files`.
- The compiled frontend served at http://localhost:3000 must:
  - Contain an `rx.upload` component with `id="upload1"` that accepts `text/plain` (`.txt`) and `image/png` (`.png`) files.
  - Render the list of uploaded filenames using `rx.foreach`.
- The Reflex backend endpoint `POST http://localhost:8000/_upload` must accept multipart uploads, persist the file under the upload directory returned by `rx.get_upload_dir()`, and the uploaded filename must appear in the page's dynamic file list after the request succeeds.
- All background processes started during the task must be terminated before the task is reported complete.

