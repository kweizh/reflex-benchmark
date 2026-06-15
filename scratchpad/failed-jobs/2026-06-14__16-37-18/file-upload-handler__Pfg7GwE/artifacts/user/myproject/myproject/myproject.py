import reflex as rx

class State(rx.State):
    """The app state."""
    uploaded_files: list[str] = []

    async def handle_upload(self, files: list[rx.UploadFile]):
        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            upload_data = await file.read()
            outfile = upload_dir / file.filename
            
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)
            
            self.uploaded_files.append(file.filename)


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("File Upload App", size="9"),
            
            rx.upload(
                rx.text("Drag and drop files here or click to select files"),
                id="upload1",
                accept={
                    "text/plain": [".txt"],
                    "image/png": [".png"]
                },
            ),
            
            rx.button(
                "Upload",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload1"))
            ),
            
            rx.heading("Uploaded Files:", size="5"),
            rx.unordered_list(
                rx.foreach(
                    State.uploaded_files,
                    lambda filename: rx.list_item(filename)
                )
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )

app = rx.App()
app.add_page(index)
