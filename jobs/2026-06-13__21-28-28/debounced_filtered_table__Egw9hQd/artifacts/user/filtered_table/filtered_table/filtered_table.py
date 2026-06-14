"""Filtered table application with debounced search, multi-filter, and sorting."""

from __future__ import annotations

from typing import Optional

import reflex as rx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from sqlmodel import select

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = ["Electronics", "Books", "Clothing", "Home", "Toys", "Sports"]

SORT_COLUMNS = ["id", "name", "price", "category"]
SORT_DIRECTIONS = ["asc", "desc"]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Product(rx.Model, table=True):
    """A product row in the catalog."""

    name: str = ""
    category: str = ""
    sku: str = ""
    price: float = 0.0
    in_stock: bool = True


# ---------------------------------------------------------------------------
# Shared filter/sort query builder
# ---------------------------------------------------------------------------


def build_filter_query(
    search: str = "",
    category: str = "All",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id",
    sort_dir: str = "asc",
):
    """Build a SQLModel select statement with the given filter/sort params."""
    stmt = select(Product)

    # Search filter: case-insensitive substring match on name
    if search:
        stmt = stmt.where(Product.name.icontains(search))

    # Category filter
    if category and category != "All":
        stmt = stmt.where(Product.category == category)

    # Price range filters
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)

    # In-stock filter
    if in_stock_only:
        stmt = stmt.where(Product.in_stock == True)  # noqa: E712

    # Sort
    sort_col = {
        "id": Product.id,
        "name": Product.name,
        "price": Product.price,
        "category": Product.category,
    }.get(sort_by, Product.id)

    if sort_dir == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    return stmt


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TableState(rx.State):
    """Reactive state for the filterable data table."""

    # Filter vars
    search: str = ""
    category: str = "All"
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock_only: bool = False
    sort_by: str = "id"
    sort_dir: str = "asc"

    # Result vars
    result_count: int = 0
    filtered: list[Product] = []

    @rx.event
    def set_search(self, value: str):
        self.search = value
        return self.filter_products()

    @rx.event
    def set_category(self, value: str):
        self.category = value
        return self.filter_products()

    @rx.event
    def set_min_price_str(self, value: str):
        """Handle min_price input from the UI."""
        if value == "":
            self.min_price = None
        else:
            try:
                self.min_price = float(value)
            except ValueError:
                self.min_price = None
        return self.filter_products()

    @rx.event
    def set_max_price_str(self, value: str):
        """Handle max_price input from the UI."""
        if value == "":
            self.max_price = None
        else:
            try:
                self.max_price = float(value)
            except ValueError:
                self.max_price = None
        return self.filter_products()

    @rx.event
    def toggle_in_stock_only(self, checked: bool):
        self.in_stock_only = checked
        return self.filter_products()

    @rx.event
    def set_sort_by(self, value: str):
        self.sort_by = value
        return self.filter_products()

    @rx.event
    def set_sort_dir(self, value: str):
        self.sort_dir = value
        return self.filter_products()

    @rx.event(background=True)
    async def filter_products(self):
        """Background event that queries the database with current filters."""
        stmt = build_filter_query(
            search=self.search,
            category=self.category,
            min_price=self.min_price,
            max_price=self.max_price,
            in_stock_only=self.in_stock_only,
            sort_by=self.sort_by,
            sort_dir=self.sort_dir,
        )
        async with rx.asession() as session:
            results = (await session.exec(stmt)).all()

        async with self:
            self.filtered = [Product(**p.model_dump()) for p in results]
            self.result_count = len(self.filtered)


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------


async def seed_products():
    """Seed the database with 240 product rows if not already seeded."""
    async with rx.asession() as session:
        count = (await session.exec(select(Product))).all()
        if len(count) > 0:
            return  # Already seeded

        products = []
        for c, cat in enumerate(CATEGORIES):
            for i in range(40):
                products.append(
                    Product(
                        name=f"{cat} #{i+1:02d}",
                        category=cat,
                        sku=f"{cat[:3].upper()}-{i+1:03d}",
                        price=round(5.0 + (c * 5) + (i * 1.0), 2),
                        in_stock=(i % 4) != 3,
                    )
                )

        session.add_all(products)
        await session.commit()


# ---------------------------------------------------------------------------
# API endpoint (FastAPI)
# ---------------------------------------------------------------------------

api_app = FastAPI()


@api_app.get("/api/filter")
async def api_filter(
    search: str = Query(default=""),
    category: str = Query(default="All"),
    min_price: Optional[float] = Query(default=None),
    max_price: Optional[float] = Query(default=None),
    in_stock_only: bool = Query(default=False),
    sort_by: str = Query(default="id"),
    sort_dir: str = Query(default="asc"),
):
    """JSON API endpoint that applies the same filter+sort logic."""
    stmt = build_filter_query(
        search=search,
        category=category,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    async with rx.asession() as session:
        results = (await session.exec(stmt)).all()

    filtered = [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "sku": p.sku,
            "price": p.price,
            "in_stock": p.in_stock,
        }
        for p in results
    ]
    return JSONResponse(
        content={
            "result_count": len(filtered),
            "filtered": filtered,
        }
    )


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def product_row(p: Product) -> rx.Component:
    """Render a single product row in the table."""
    return rx.table.row(
        rx.table.cell(p.id),
        rx.table.cell(p.name),
        rx.table.cell(p.category),
        rx.table.cell(f"${p.price:.2f}"),
        rx.table.cell(rx.cond(p.in_stock, "Yes", "No")),
    )


def index() -> rx.Component:
    """The main page with filter controls and data table."""
    return rx.container(
        rx.vstack(
            rx.heading("Product Catalog", size="8"),
            # ── Filter controls ──
            rx.hstack(
                rx.debounce_input(
                    rx.input(
                        value=TableState.search,
                        on_change=TableState.set_search,
                        placeholder="Search by name...",
                    ),
                    debounce_timeout=300,
                ),
                rx.select(
                    ["All"] + CATEGORIES,
                    value=TableState.category,
                    on_change=TableState.set_category,
                ),
                rx.input(
                    value=TableState.min_price if TableState.min_price is not None else "",
                    on_change=TableState.set_min_price_str,
                    placeholder="Min price",
                    type="number",
                ),
                rx.input(
                    value=TableState.max_price if TableState.max_price is not None else "",
                    on_change=TableState.set_max_price_str,
                    placeholder="Max price",
                    type="number",
                ),
                rx.checkbox(
                    "In stock only",
                    checked=TableState.in_stock_only,
                    on_change=TableState.toggle_in_stock_only,
                ),
                spacing="3",
                flex_wrap="wrap",
            ),
            rx.hstack(
                rx.text("Sort by:"),
                rx.select(
                    SORT_COLUMNS,
                    value=TableState.sort_by,
                    on_change=TableState.set_sort_by,
                ),
                rx.text("Direction:"),
                rx.select(
                    SORT_DIRECTIONS,
                    value=TableState.sort_dir,
                    on_change=TableState.set_sort_dir,
                ),
                spacing="3",
            ),
            # ── Result count ──
            rx.text(f"Results: ", TableState.result_count),
            # ── Data table ──
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("ID"),
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Category"),
                        rx.table.column_header_cell("Price"),
                        rx.table.column_header_cell("In Stock"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        TableState.filtered,
                        product_row,
                    )
                ),
            ),
            spacing="4",
            min_height="85vh",
        ),
        max_width="1200px",
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = rx.App(api_transformer=api_app)
app.register_lifespan_task(seed_products)
app.add_page(index)