"""Reflex file upload handler application."""

import reflex as rx


class State(rx.State):
    """The app state."""

    uploaded_files: list[str] = []

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of files.

        Args:
            files: The list of uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = rx.get_upload_dir() / file.filename
            outfile.write_bytes(upload_data)
            self.uploaded_files.append(file.filename)


def index() -> rx.Component:
    """Render the main page."""
    return rx.container(
        rx.vstack(
            rx.heading("File Upload", size="9"),
            rx.upload(
                rx.vstack(
                    rx.text("Drag and drop files here or click to select"),
                    rx.text(
                        "Accepted: .txt and .png files",
                        font_size="sm",
                        color_scheme="gray",
                    ),
                    rx.button(
                        "Upload",
                        on_click=State.handle_upload(
                            rx.upload_files(upload_id="upload1")
                        ),
                    ),
                ),
                id="upload1",
                accept={
                    "text/plain": [".txt"],
                    "image/png": [".png"],
                },
                border="1px dashed var(--accent-12)",
                padding="5em",
                text_align="center",
            ),
            rx.heading("Uploaded Files", size="5"),
            rx.foreach(
                State.uploaded_files,
                lambda filename: rx.text(filename),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
        padding="2em",
    )


app = rx.App()
app.add_page(index)
