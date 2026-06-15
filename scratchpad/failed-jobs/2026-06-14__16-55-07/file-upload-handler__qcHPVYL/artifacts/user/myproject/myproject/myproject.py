"""Reflex file upload application."""

import reflex as rx


class State(rx.State):
    """The app state."""

    uploaded_files: list[str] = []

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle file upload by reading and saving each file."""
        for file in files:
            file_data = await file.read()
            upload_dir = rx.get_upload_dir()
            save_path = upload_dir / file.filename
            with open(save_path, "wb") as f:
                f.write(file_data)
            self.uploaded_files.append(file.filename)


def index() -> rx.Component:
    """The main page with upload component and file list."""
    return rx.container(
        rx.vstack(
            rx.heading("File Upload", size="9"),
            rx.upload(
                id="upload1",
                accept={
                    "text/plain": [".txt"],
                    "image/png": [".png"],
                },
            ),
            rx.button(
                "Upload",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
            ),
            rx.divider(),
            rx.heading("Uploaded Files", size="7"),
            rx.foreach(
                State.uploaded_files,
                lambda filename: rx.text(filename),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)