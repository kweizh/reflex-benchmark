import reflex as rx

class State(rx.State):
    uploaded_files: list[str] = []

    async def handle_upload(self, files: list[rx.UploadFile]):
        for file in files:
            # Read each uploaded file's bytes asynchronously
            upload_data = await file.read()
            # Save the bytes to the Reflex upload directory using the original filename
            upload_dir = rx.get_upload_dir()
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / file.filename
            with open(file_path, "wb") as f:
                f.write(upload_data)
            # Append filename to state list
            self.uploaded_files.append(file.filename)

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Reflex File Upload Handler", size="8"),
            rx.text("Upload plain text (.txt) and PNG image (.png) files below."),
            rx.upload(
                rx.vstack(
                    rx.button("Select File", color_scheme="blue"),
                    rx.text("Drag and drop files here or click to select"),
                ),
                id="upload1",
                accept={
                    "text/plain": [".txt"],
                    "image/png": [".png"],
                },
                border="1px dashed var(--accent-12)",
                padding="5em",
            ),
            rx.button(
                "Upload",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload1")),
            ),
            rx.heading("Uploaded Files", size="6"),
            rx.vstack(
                rx.foreach(State.uploaded_files, lambda filename: rx.text(filename)),
                spacing="2",
            ),
            spacing="5",
            align="center",
            min_height="85vh",
            padding_top="2em",
        )
    )

app = rx.App()
app.add_page(index)
