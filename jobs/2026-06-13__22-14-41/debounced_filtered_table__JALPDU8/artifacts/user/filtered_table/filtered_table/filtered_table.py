"""Debounced Multi-Filter Data Table application."""

from typing import Optional

import reflex as rx
import sqlmodel
from sqlmodel import select, col


# ── Seed Algorithm Constants ────────────────────────────────────────────────

CATEGORIES = ["Electronics", "Books", "Clothing", "Home", "Toys", "Sports"]


# ── Product Model ───────────────────────────────────────────────────────────

class Product(rx.Model, table=True):
    """Product catalog table."""

    name: str
    category: str
    sku: str
    price: float
    in_stock: bool


# ── Shared Filter/Sort Query Builder ────────────────────────────────────────

SORT_COLUMNS = {
    "id": Product.id,
    "name": Product.name,
    "price": Product.price,
    "category": Product.category,
}


def build_filter_query(
    search: str = "",
    category: str = "All",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id",
    sort_dir: str = "asc",
):
    """Build a SQLModel select statement with filters and ordering.

    Args:
        search: Case-insensitive substring match against Product.name.
        category: Category filter ("All" or empty means no filter).
        min_price: Minimum price filter (inclusive).
        max_price: Maximum price filter (inclusive).
        in_stock_only: When True, only include in-stock products.
        sort_by: Column to sort by (id, name, price, category).
        sort_dir: Sort direction (asc or desc).

    Returns:
        A SQLModel select statement.
    """
    conditions = []

    # Text search: case-insensitive substring match against name
    if search and search.strip():
        conditions.append(col(Product.name).ilike(f"%{search.strip()}%"))

    # Category filter
    if category and category != "All":
        conditions.append(Product.category == category)

    # Price range filters
    if min_price is not None:
        conditions.append(Product.price >= min_price)
    if max_price is not None:
        conditions.append(Product.price <= max_price)

    # In-stock filter
    if in_stock_only:
        conditions.append(Product.in_stock == True)  # noqa: E712

    # Build select
    stmt = select(Product)
    if conditions:
        stmt = stmt.where(*conditions)

    # Ordering
    sort_col = SORT_COLUMNS.get(sort_by, Product.id)
    if sort_dir == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    return stmt


# ── State ───────────────────────────────────────────────────────────────────

class FilterState(rx.State):
    """Application state for the filterable data table."""

    # Filter vars
    search: str = ""
    category: str = "All"
    min_price: str = ""  # bound to text input, parsed as float
    max_price: str = ""  # bound to text input, parsed as float
    in_stock_only: bool = False
    sort_by: str = "id"
    sort_dir: str = "asc"

    # Results
    filtered: list[dict] = []
    result_count: int = 0

    async def _apply_filters(self):
        """Recompute filtered results based on current filter/sort vars."""
        # Parse price values
        min_price_val: Optional[float] = None
        max_price_val: Optional[float] = None
        try:
            if self.min_price.strip():
                min_price_val = float(self.min_price.strip())
        except ValueError:
            pass
        try:
            if self.max_price.strip():
                max_price_val = float(self.max_price.strip())
        except ValueError:
            pass

        stmt = build_filter_query(
            search=self.search,
            category=self.category,
            min_price=min_price_val,
            max_price=max_price_val,
            in_stock_only=self.in_stock_only,
            sort_by=self.sort_by,
            sort_dir=self.sort_dir,
        )

        async with rx.asession() as session:
            result = await session.exec(stmt)
            rows = list(result.all())

        # Convert to list of dicts for JSON serialization to frontend
        data = [
            {
                "id": row.id,
                "name": row.name,
                "category": row.category,
                "sku": row.sku,
                "price": row.price,
                "in_stock": row.in_stock,
            }
            for row in rows
        ]

        async with self:
            self.filtered = data
            self.result_count = len(data)

    @rx.event(background=True)
    async def handle_filter_change(self):
        """Background event handler triggered on any filter/sort change."""
        await self._apply_filters()

    @rx.event
    def set_search(self, value: str):
        """Set the search text and trigger filter recomputation."""
        self.search = value
        return FilterState.handle_filter_change  # type: ignore[return-value]

    @rx.event
    def set_category(self, value: str):
        """Set the category filter and trigger filter recomputation."""
        self.category = value
        return FilterState.handle_filter_change  # type: ignore[return-value]

    @rx.event
    def set_min_price(self, value: str):
        """Set the min price filter and trigger filter recomputation."""
        self.min_price = value
        return FilterState.handle_filter_change  # type: ignore[return-value]

    @rx.event
    def set_max_price(self, value: str):
        """Set the max price filter and trigger filter recomputation."""
        self.max_price = value
        return FilterState.handle_filter_change  # type: ignore[return-value]

    @rx.event
    def set_in_stock_only(self, value: bool):
        """Set the in-stock-only filter and trigger filter recomputation."""
        self.in_stock_only = value
        return FilterState.handle_filter_change  # type: ignore[return-value]

    @rx.event
    def set_sort_by(self, value: str):
        """Set the sort column and trigger filter recomputation."""
        self.sort_by = value
        return FilterState.handle_filter_change  # type: ignore[return-value]

    @rx.event
    def set_sort_dir(self, value: str):
        """Set the sort direction and trigger filter recomputation."""
        self.sort_dir = value
        return FilterState.handle_filter_change  # type: ignore[return-value]


# ── Seed Function ───────────────────────────────────────────────────────────

def seed_database():
    """Seed the database with 240 Product rows if the table is empty."""
    from sqlmodel import Session, select as sync_select
    from reflex.model import get_engine

    engine = get_engine()
    with Session(engine) as session:
        # Check if products already exist
        existing = session.exec(sync_select(Product).limit(1)).first()
        if existing is not None:
            return  # Already seeded, skip

        products = []
        for c, cat_name in enumerate(CATEGORIES):
            for i in range(40):
                name = f"{cat_name} #{i+1:02d}"
                sku = f"{cat_name[:3].upper()}-{i+1:03d}"
                price = round(5.0 + (c * 5) + (i * 1.0), 2)
                in_stock = (i % 4) != 3

                products.append(
                    Product(
                        name=name,
                        category=cat_name,
                        sku=sku,
                        price=price,
                        in_stock=in_stock,
                    )
                )

        session.add_all(products)
        session.commit()


# ── UI Components ───────────────────────────────────────────────────────────

def filter_controls() -> rx.Component:
    """Render the filter control panel."""
    return rx.vstack(
        rx.heading("Product Catalog", size="7"),
        rx.hstack(
            rx.text("Search:"),
            rx.debounce_input(
                rx.input(
                    value=FilterState.search,
                    placeholder="Search by name...",
                    width="300px",
                ),
                debounce_timeout=300,
                value=FilterState.search,
                on_change=FilterState.set_search,
            ),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.text("Category:"),
            rx.select(
                ["All"] + CATEGORIES,
                value=FilterState.category,
                on_change=FilterState.set_category,
            ),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.text("Min Price:"),
            rx.input(
                value=FilterState.min_price,
                placeholder="0.00",
                width="120px",
                type="number",
                on_change=FilterState.set_min_price,
            ),
            rx.text("Max Price:"),
            rx.input(
                value=FilterState.max_price,
                placeholder="999.99",
                width="120px",
                type="number",
                on_change=FilterState.set_max_price,
            ),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.checkbox(
                "In stock only",
                checked=FilterState.in_stock_only,
                on_change=FilterState.set_in_stock_only,
            ),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            rx.text("Sort by:"),
            rx.select(
                ["id", "name", "price", "category"],
                value=FilterState.sort_by,
                on_change=FilterState.set_sort_by,
            ),
            rx.select(
                ["asc", "desc"],
                value=FilterState.sort_dir,
                on_change=FilterState.set_sort_dir,
            ),
            spacing="2",
            align="center",
        ),
        spacing="4",
        padding="1em",
        border="1px solid #e0e0e0",
        border_radius="8px",
        width="100%",
    )


def product_row(product: dict) -> rx.Component:
    """Render a single product row."""
    return rx.table.row(
        rx.table.cell(product["id"]),
        rx.table.cell(product["name"]),
        rx.table.cell(product["category"]),
        rx.table.cell(f"${product['price']:.2f}"),
        rx.table.cell(
            rx.badge(
                "In Stock" if product["in_stock"] else "Out of Stock",
                color_scheme="green" if product["in_stock"] else "red",
            )
        ),
    )


def product_table() -> rx.Component:
    """Render the data table with rx.foreach."""
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("ID"),
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Category"),
                rx.table.column_header_cell("Price"),
                rx.table.column_header_cell("Status"),
            )
        ),
        rx.table.body(
            rx.foreach(FilterState.filtered, product_row),
        ),
        width="100%",
        variant="surface",
    )


def index() -> rx.Component:
    """Main page with filter controls and results table."""
    return rx.container(
        rx.vstack(
            filter_controls(),
            rx.hstack(
                rx.text("Results: ", weight="bold"),
                rx.text(FilterState.result_count),
                spacing="2",
            ),
            product_table(),
            spacing="4",
            padding="1em",
        ),
        max_width="1200px",
    )


# ── App Initialization ──────────────────────────────────────────────────────

# Seed the database before creating the app
seed_database()

# Import the FastAPI app for the /api/filter endpoint
from filtered_table.api import api_app  # noqa: E402

app = rx.App(
    api_transformer=api_app,
)
app.add_page(index, route="/")
