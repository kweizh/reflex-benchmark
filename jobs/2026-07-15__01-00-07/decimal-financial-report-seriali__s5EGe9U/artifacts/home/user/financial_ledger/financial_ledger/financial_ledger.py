import decimal
import datetime
import reflex as rx
from pydantic import BaseModel

# Custom serializers for Decimal and datetime
@rx.serializer(overwrite=True)
def serialize_decimal(val: decimal.Decimal) -> str:
    if val < 0:
        return f"-${abs(val):,.2f}"
    else:
        return f"${val:,.2f}"

@rx.serializer(overwrite=True)
def serialize_datetime(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

class LedgerEntry(BaseModel):
    description: str
    amount: decimal.Decimal
    timestamp: datetime.datetime

class LedgerRow(BaseModel):
    description: str
    amount: decimal.Decimal
    timestamp: datetime.datetime
    balance: decimal.Decimal

class State(rx.State):
    # Seed the state with exactly these four entries in order
    entries: list[LedgerEntry] = [
        LedgerEntry(description="Opening balance", amount=decimal.Decimal("1000.00"), timestamp=datetime.datetime(2024, 1, 1, 9, 0)),
        LedgerEntry(description="Grocery store", amount=decimal.Decimal("-234.56"), timestamp=datetime.datetime(2024, 1, 2, 14, 30)),
        LedgerEntry(description="Salary", amount=decimal.Decimal("2500.00"), timestamp=datetime.datetime(2024, 1, 5, 8, 0)),
        LedgerEntry(description="Electric bill", amount=decimal.Decimal("-89.99"), timestamp=datetime.datetime(2024, 1, 10, 16, 45)),
    ]

    # Input fields for adding a new entry
    new_description: str = ""
    new_amount: str = ""

    @rx.event
    def set_new_description(self, val: str):
        self.new_description = val

    @rx.event
    def set_new_amount(self, val: str):
        self.new_amount = val

    @rx.var
    def ledger_rows(self) -> list[LedgerRow]:
        rows = []
        current_sum = decimal.Decimal("0.00")
        for entry in self.entries:
            current_sum += entry.amount
            rows.append(
                LedgerRow(
                    description=entry.description,
                    amount=entry.amount,
                    timestamp=entry.timestamp,
                    balance=current_sum,
                )
            )
        return rows

    @rx.var
    def total_credits(self) -> decimal.Decimal:
        total = decimal.Decimal("0.00")
        for entry in self.entries:
            if entry.amount > 0:
                total += entry.amount
        return total

    @rx.var
    def total_debits(self) -> decimal.Decimal:
        total = decimal.Decimal("0.00")
        for entry in self.entries:
            if entry.amount < 0:
                total += abs(entry.amount)
        return total

    @rx.var
    def net_balance(self) -> decimal.Decimal:
        total = decimal.Decimal("0.00")
        for entry in self.entries:
            total += entry.amount
        return total

    @rx.var
    def is_net_balance_positive(self) -> bool:
        return self.net_balance >= 0

    @rx.event
    def add_entry(self):
        desc = self.new_description.strip()
        if not desc:
            return
        
        try:
            amt = decimal.Decimal(self.new_amount.strip())
        except (decimal.InvalidOperation, ValueError):
            return
        
        now = datetime.datetime.now()
        new_entry = LedgerEntry(
            description=desc,
            amount=amt,
            timestamp=now
        )
        self.entries.append(new_entry)
        
        # Clear inputs
        self.new_description = ""
        self.new_amount = ""


def show_row(row: LedgerRow):
    return rx.table.row(
        rx.table.cell(row.description),
        rx.table.cell(row.amount),
        rx.table.cell(row.timestamp),
        rx.table.cell(row.balance),
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Financial Ledger Report", size="8", margin_bottom="0.5em"),
            
            # Ledger Table
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Description"),
                            rx.table.column_header_cell("Amount"),
                            rx.table.column_header_cell("Timestamp"),
                            rx.table.column_header_cell("Balance"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(State.ledger_rows, show_row)
                    ),
                    width="100%",
                ),
                width="100%",
                border="1px solid #e5e7eb",
                border_radius="6px",
                overflow="hidden",
                margin_bottom="1.5em",
            ),
            
            # Totals Section
            rx.card(
                rx.vstack(
                    rx.heading("Summary Totals", size="4", margin_bottom="0.25em"),
                    rx.hstack(
                        rx.text("Total Credits: ", font_weight="bold"),
                        rx.text(State.total_credits, color="green"),
                        justify="between",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.text("Total Debits: ", font_weight="bold"),
                        rx.text(State.total_debits, color="red"),
                        justify="between",
                        width="100%",
                    ),
                    rx.divider(),
                    rx.hstack(
                        rx.text("Net Balance: ", font_weight="bold"),
                        rx.text(
                            State.net_balance,
                            color=rx.cond(State.is_net_balance_positive, "green", "red"),
                            font_weight="bold",
                        ),
                        justify="between",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                ),
                width="100%",
                margin_bottom="1.5em",
            ),
            
            # Add Entry Form
            rx.card(
                rx.vstack(
                    rx.heading("Add New Entry", size="4", margin_bottom="0.5em"),
                    rx.hstack(
                        rx.input(
                            value=State.new_description,
                            on_change=State.set_new_description,
                            placeholder="Description (e.g., Coffee)",
                            flex="1",
                        ),
                        rx.input(
                            value=State.new_amount,
                            on_change=State.set_new_amount,
                            placeholder="Amount (e.g., -4.50 or 15.00)",
                            width="200px",
                        ),
                        rx.button("Add Entry", on_click=State.add_entry),
                        width="100%",
                        spacing="3",
                    ),
                    width="100%",
                ),
                width="100%",
            ),
            
            spacing="4",
            padding="2em",
            max_width="800px",
            margin="0 auto",
        )
    )


app = rx.App()
app.add_page(index)
