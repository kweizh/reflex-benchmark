"""CSV Upload + Async Processing Pipeline with Progress."""

import csv
import io
from typing import List

import reflex as rx
from reflex.model import Model


class Person(Model, table=True):
    """Model for storing person records."""

    name: str
    email: str
    age: int


class State(rx.State):
    """The app state for tracking CSV upload progress."""

    progress: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    errors: List[str] = []
    _csv_content: str = ""

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Receive the uploaded CSV file and trigger background processing.

        This is a regular (non-background) handler because upload handlers
        cannot be background tasks. It reads the file content and then
        yields a background event to process it.
        """
        file = files[0]
        content_bytes = await file.read()
        self._csv_content = content_bytes.decode("utf-8")
        self.progress = 0
        self.valid_count = 0
        self.invalid_count = 0
        self.errors = []
        yield State.process_csv

    @rx.event(background=True)
    async def process_csv(self):
        """Process the uploaded CSV file in the background.

        Reads the CSV content stored in state, validates each row,
        inserts valid rows into the database, and updates progress.
        All state mutations happen inside `async with self:` blocks.
        """
        # Read the CSV content outside the state lock
        # (may be stale, but that's acceptable for background tasks)
        csv_content = self._csv_content

        # Parse CSV
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        # Reset state at the start
        async with self:
            self.progress = 0
            self.valid_count = 0
            self.invalid_count = 0
            self.errors = []

        # Validate header
        if not rows:
            async with self:
                self.progress = 100
                self.errors.append("File is empty or contains no data.")
            return

        header = rows[0]
        expected_header = ["name", "email", "age"]
        if header != expected_header:
            async with self:
                self.progress = 100
                self.errors.append(
                    f"Header mismatch: expected {expected_header}, got {header}"
                )
            return

        data_rows = rows[1:]
        total = len(data_rows)

        if total == 0:
            async with self:
                self.progress = 100
            return

        # Process each data row
        for idx, row in enumerate(data_rows):
            row_number = idx + 2  # 1-based, header is row 1

            is_valid = True
            error_msg = None

            # Validate: exactly 3 fields
            if len(row) != 3:
                is_valid = False
                error_msg = f"Row {row_number}: expected 3 fields, got {len(row)}"
            else:
                name, email, age_str = row
                # Validate name non-empty
                if not name.strip():
                    is_valid = False
                    error_msg = f"Row {row_number}: name is empty"
                # Validate email contains @
                elif "@" not in email:
                    is_valid = False
                    error_msg = f"Row {row_number}: email does not contain @"
                # Validate age is a strictly positive integer
                else:
                    try:
                        age_val = int(age_str)
                        if age_val <= 0:
                            is_valid = False
                            error_msg = (
                                f"Row {row_number}: age must be a positive integer,"
                                f" got {age_str}"
                            )
                    except ValueError:
                        is_valid = False
                        error_msg = (
                            f"Row {row_number}: age is not a valid integer: {age_str}"
                        )

            if is_valid:
                name, email, age_str = row
                # Insert into DB
                async with rx.asession() as session:
                    person = Person(
                        name=name.strip(),
                        email=email.strip(),
                        age=int(age_str),
                    )
                    session.add(person)
                    await session.commit()

                async with self:
                    self.valid_count += 1
                    self.progress = int(((idx + 1) / total) * 100)
            else:
                async with self:
                    self.invalid_count += 1
                    self.errors.append(error_msg)
                    self.progress = int(((idx + 1) / total) * 100)

        # Ensure progress is exactly 100 at the end
        async with self:
            self.progress = 100


def index() -> rx.Component:
    """The main page with CSV upload, progress bar, and summary."""
    return rx.container(
        rx.vstack(
            rx.heading("CSV Upload", size="8"),
            rx.text("Upload a CSV file with columns: name, email, age"),
            rx.upload(
                rx.vstack(
                    rx.text("Drag and drop a CSV file here, or click to select"),
                ),
                id="csv_upload",
                accept={"text/csv": [".csv"]},
                multiple=False,
                border="1px dashed var(--color-border-1)",
                padding="2em",
            ),
            rx.hstack(
                rx.button(
                    "Upload & Process",
                    on_click=State.handle_upload(
                        rx.event.upload_files("csv_upload")
                    ),
                ),
                rx.button(
                    "Clear",
                    on_click=rx.clear_selected_files("csv_upload"),
                    variant="outline",
                ),
            ),
            rx.progress(value=State.progress, width="100%"),
            rx.cond(
                State.progress > 0,
                rx.text(f"Progress: {State.progress}%"),
                rx.text("No file processed yet."),
            ),
            rx.cond(
                State.progress == 100,
                rx.text(
                    f"Processed {State.valid_count + State.invalid_count} rows: "
                    f"{State.valid_count} valid, {State.invalid_count} invalid"
                ),
                rx.text(""),
            ),
            rx.cond(
                State.errors.length() > 0,
                rx.vstack(
                    rx.heading("Errors", size="4"),
                    rx.foreach(State.errors, lambda err: rx.text(err, color="red")),
                ),
                rx.text(""),
            ),
            spacing="4",
            align="stretch",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)