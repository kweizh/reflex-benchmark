import reflex as rx
import csv
import asyncio

class Person(rx.Model, table=True):
    name: str
    email: str
    age: int

class State(rx.State):
    progress: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    errors: list[str] = []
    
    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
            
        file = files[0]
        content = await file.read()
        
        # Start background task
        return State.process_csv(content)
        
    @rx.event(background=True)
    async def process_csv(self, content: bytes):
        text = content.decode('utf-8')
        lines = text.splitlines()
        if not lines:
            async with self:
                self.progress = 100
            return
            
        reader = csv.reader(lines)
        rows = list(reader)
        
        # Find first non-empty row
        header_idx = -1
        for idx, r in enumerate(rows):
            if r:
                header_idx = idx
                break
                
        if header_idx == -1:
            async with self:
                self.progress = 100
            return
            
        header = rows[header_idx]
        if header != ['name', 'email', 'age']:
            async with self:
                self.errors = ["Header mismatch"]
                self.progress = 100
            return
            
        data_rows = rows[header_idx + 1:]
        total_rows = len(data_rows)
        
        async with self:
            self.progress = 0
            self.valid_count = 0
            self.invalid_count = 0
            self.errors = []
            
        if total_rows == 0:
            async with self:
                self.progress = 100
            return
            
        valid_records = []
        
        for i, row in enumerate(data_rows):
            row_num = i + 2 # Header is row 1, data starts at row 2
            
            is_valid = False
            error_msg = ""
            
            if len(row) != 3:
                error_msg = f"Row {row_num}: Expected 3 fields, got {len(row)}"
            else:
                name, email, age_str = row
                if not name:
                    error_msg = f"Row {row_num}: Name is empty"
                elif '@' not in email:
                    error_msg = f"Row {row_num}: Email must contain @"
                else:
                    try:
                        age = int(age_str)
                        if age <= 0:
                            error_msg = f"Row {row_num}: Age must be positive"
                        else:
                            is_valid = True
                            valid_records.append(Person(name=name, email=email, age=age))
                    except ValueError:
                        error_msg = f"Row {row_num}: Age must be an integer"
                        
            # Update state for this row
            async with self:
                if is_valid:
                    self.valid_count += 1
                else:
                    self.invalid_count += 1
                    self.errors.append(error_msg)
                
                self.progress = int(((i + 1) / total_rows) * 100)
                
            # Yield to event loop
            await asyncio.sleep(0.001)
            
        # Save valid records to DB
        if valid_records:
            async with rx.asession() as session:
                session.add_all(valid_records)
                await session.commit()
                
        # Ensure progress is 100 at the end
        async with self:
            self.progress = 100

def index() -> rx.Component:
    return rx.vstack(
        rx.upload(
            rx.vstack(
                rx.button("Select File"),
                rx.text("Drag and drop files here or click to select files"),
            ),
            id="csv_upload",
            accept={"text/csv": [".csv"]},
            multiple=False,
            on_drop=State.handle_upload(rx.upload_files(upload_id="csv_upload")),
        ),
        rx.button("Upload", on_click=State.handle_upload(rx.upload_files(upload_id="csv_upload"))),
        rx.progress(value=State.progress),
        rx.text(f"Processed {State.valid_count + State.invalid_count} rows: {State.valid_count} valid, {State.invalid_count} invalid"),
        rx.vstack(
            rx.foreach(State.errors, lambda error: rx.text(error, color="red")),
        ),
        padding="2em",
    )

app = rx.App()
app.add_page(index)
