"""Reflex file upload handler app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    """The app state."""

    uploaded_files: list[str] = []

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of files."""
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.filename
            with outfile.open("wb") as f:
                f.write(upload_data)
            self.uploaded_files.append(file.filename)


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("File Upload", size="7"),
            rx.upload(
                rx.vstack(
                    rx.button("Select Files"),
                    rx.text("Drag and drop .txt or .png files here, or click to select."),
                ),
                id="upload1",
                accept={
                    "text/plain": [".txt"],
                    "image/png": [".png"],
                },
                border="2px dashed #888",
                padding="2em",
                border_radius="8px",
            ),
            rx.button(
                "Upload",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
                color_scheme="blue",
            ),
            rx.heading("Uploaded Files", size="5"),
            rx.foreach(
                State.uploaded_files,
                lambda filename: rx.text(filename),
            ),
            spacing="4",
            align="start",
            padding="2em",
        ),
    )


app = rx.App()
app.add_page(index)
