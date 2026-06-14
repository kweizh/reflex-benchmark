import reflex as rx
from typing import List

class Person(rx.Model, table=True):
    name: str
    email: str
    age: int

class State(rx.State):
    progress: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    errors: List[str] = []
    processing: bool = False
    csv_content: str = ""

    async def handle_upload(self, files: List[rx.UploadFile]):
        if not files:
            return
        
        file_data = await files[0].read()
        async with self:
            self.csv_content = file_data.decode("utf-8")
            self.progress = 0
            self.valid_count = 0
            self.invalid_count = 0
            self.errors = []
            self.processing = True
        
        return State.process_csv

    @rx.event(background=True)
    async def process_csv(self):
        async with self:
            content = self.csv_content
        
        if not content:
            async with self:
                self.processing = False
                self.progress = 100
            return

        lines = content.splitlines()
        h_idx = -1
        for i, line in enumerate(lines):
            if line.strip():
                h_idx = i
                break
        
        if h_idx == -1:
            async with self:
                self.processing = False
                self.progress = 100
            return

        header = lines[h_idx].strip()
        if header != "name,email,age":
            async with self:
                self.errors.append("Header mismatch: expected 'name,email,age'")
                self.processing = False
                self.progress = 100
            return

        data_rows = lines[h_idx + 1:]
        total_rows = len(data_rows)
        
        if total_rows == 0:
            async with self:
                self.processing = False
                self.progress = 100
            return

        for i, row_str in enumerate(data_rows):
            row_num = i + 2  # counting from header as row 1
            
            fields = row_str.split(",")
            
            is_valid = True
            error_msg = ""
            
            if len(fields) != 3:
                is_valid = False
                error_msg = f"Row {row_num}: Invalid number of fields"
            else:
                name, email, age_str = [f.strip() for f in fields]
                if not name:
                    is_valid = False
                    error_msg = f"Row {row_num}: Name is empty"
                elif "@" not in email:
                    is_valid = False
                    error_msg = f"Row {row_num}: Email missing @"
                else:
                    try:
                        age = int(age_str)
                        if age <= 0:
                            is_valid = False
                            error_msg = f"Row {row_num}: Age must be positive"
                    except ValueError:
                        is_valid = False
                        error_msg = f"Row {row_num}: Age not an integer"

            if is_valid:
                async with rx.asession() as session:
                    session.add(Person(name=name, email=email, age=age))
                    await session.commit()
                async with self:
                    self.valid_count += 1
            else:
                async with self:
                    self.invalid_count += 1
                    self.errors.append(error_msg)
            
            # Update progress
            async with self:
                self.progress = int(((i + 1) / total_rows) * 100)

        async with self:
            self.processing = False
            self.progress = 100

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("CSV Upload"),
            rx.upload(
                rx.vstack(
                    rx.button("Select File", color_scheme="blue"),
                    rx.text("Drag and drop files here or click to select"),
                ),
                id="csv_upload",
                accept={"text/csv": [".csv"]},
                multiple=False,
                border="1px dashed var(--gray-10)",
                padding="2em",
            ),
            rx.button(
                "Upload",
                on_click=State.handle_upload(rx.upload_files(upload_id="csv_upload")),
            ),
            rx.progress(value=State.progress, width="100%"),
            rx.text(
                f"Processed {State.valid_count + State.invalid_count} rows: {State.valid_count} valid, {State.invalid_count} invalid",
            ),
            rx.vstack(
                rx.foreach(State.errors, rx.text),
                color="red",
            ),
            spacing="4",
            padding="2em",
        )
    )

app = rx.App()
app.add_page(index)
