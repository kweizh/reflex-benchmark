import reflex as rx
from typing import List, Optional
import sqlmodel
from sqlmodel import select, or_, asc, desc, func
from fastapi import FastAPI, Query

CATEGORIES = ["Electronics", "Books", "Clothing", "Home", "Toys", "Sports"]

class Product(rx.Model, table=True):
    name: str
    category: str
    sku: str
    price: float
    in_stock: bool

def get_filtered_query(
    search: str = "",
    category: str = "All",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id",
    sort_dir: str = "asc"
):
    query = select(Product)
    
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    
    if category and category != "All":
        query = query.where(Product.category == category)
        
    if min_price is not None:
        query = query.where(Product.price >= min_price)
        
    if max_price is not None:
        query = query.where(Product.price <= max_price)
        
    if in_stock_only:
        query = query.where(Product.in_stock == True)
        
    # Sorting
    sort_col = getattr(Product, sort_by, Product.id)
    if sort_dir == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(asc(sort_col))
        
    return query

def seed_db():
    with rx.session() as session:
        try:
            # Check if already seeded
            existing = session.exec(select(Product).limit(1)).first()
            if existing:
                return
            
            products = []
            for c, cat_name in enumerate(CATEGORIES):
                for i in range(40):
                    name = f"{cat_name} #{i+1:02d}"
                    sku = f"{cat_name[:3].upper()}-{i+1:03d}"
                    price = round(5.0 + (c * 5) + (i * 1.0), 2)
                    in_stock = (i % 4) != 3
                    products.append(Product(
                        name=name,
                        category=cat_name,
                        sku=sku,
                        price=price,
                        in_stock=in_stock
                    ))
            session.add_all(products)
            session.commit()
        except Exception:
            pass

class State(rx.State):
    search: str = ""
    category: str = "All"
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock_only: bool = False
    sort_by: str = "id"
    sort_dir: str = "asc"
    
    filtered: List[Product] = []
    result_count: int = 0
    
    def on_load(self):
        seed_db()
        return State.filter_products()

    @rx.event(background=True)
    async def filter_products(self):
        async with self:
            search = self.search
            category = self.category
            min_price = self.min_price
            max_price = self.max_price
            in_stock_only = self.in_stock_only
            sort_by = self.sort_by
            sort_dir = self.sort_dir

        async with rx.asession() as session:
            query = get_filtered_query(
                search, category, min_price, max_price, in_stock_only, sort_by, sort_dir
            )
            results = (await session.exec(query)).all()
            count = len(results)
            
            async with self:
                self.filtered = results
                self.result_count = count

    def set_search(self, val):
        self.search = val
        return State.filter_products()

    def set_category(self, val):
        self.category = val
        return State.filter_products()

    def set_min_price(self, val):
        try:
            self.min_price = float(val) if val != "" else None
        except ValueError:
            self.min_price = None
        return State.filter_products()

    def set_max_price(self, val):
        try:
            self.max_price = float(val) if val != "" else None
        except ValueError:
            self.max_price = None
        return State.filter_products()

    def set_in_stock_only(self, val):
        self.in_stock_only = val
        return State.filter_products()

    def set_sort_by(self, val):
        self.sort_by = val
        return State.filter_products()

    def set_sort_dir(self, val):
        self.sort_dir = val
        return State.filter_products()

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Product Catalog", size="8"),
            rx.hstack(
                rx.vstack(
                    rx.text("Search"),
                    rx.debounce_input(
                        rx.input(
                            placeholder="Search by name...",
                            on_change=State.set_search,
                            value=State.search,
                        ),
                        debounce_timeout=300,
                    ),
                ),
                rx.vstack(
                    rx.text("Category"),
                    rx.select(
                        ["All"] + CATEGORIES,
                        value=State.category,
                        on_change=State.set_category,
                    ),
                ),
                rx.vstack(
                    rx.text("Min Price"),
                    rx.input(
                        type="number",
                        on_change=State.set_min_price,
                    ),
                ),
                rx.vstack(
                    rx.text("Max Price"),
                    rx.input(
                        type="number",
                        on_change=State.set_max_price,
                    ),
                ),
                rx.vstack(
                    rx.text("In stock only"),
                    rx.checkbox(
                        on_change=State.set_in_stock_only,
                        is_checked=State.in_stock_only,
                    ),
                ),
                rx.vstack(
                    rx.text("Sort By"),
                    rx.select(
                        ["id", "name", "price", "category"],
                        value=State.sort_by,
                        on_change=State.set_sort_by,
                    ),
                ),
                rx.vstack(
                    rx.text("Sort Dir"),
                    rx.select(
                        ["asc", "desc"],
                        value=State.sort_dir,
                        on_change=State.set_sort_dir,
                    ),
                ),
                spacing="4",
                align_items="end",
            ),
            rx.text(f"Total Results: {State.result_count}"),
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
                        State.filtered,
                        lambda p: rx.table.row(
                            rx.table.cell(p.id),
                            rx.table.cell(p.name),
                            rx.table.cell(p.category),
                            rx.table.cell(p.price),
                            rx.table.cell(rx.cond(p.in_stock, "true", "false")),
                        )
                    )
                ),
                width="100%",
            ),
            spacing="5",
            padding="5",
        )
    )

# API Endpoint
api_app = FastAPI()

@api_app.on_event("startup")
def on_startup():
    seed_db()

@api_app.get("/api/filter")
async def api_filter(
    search: str = "",
    category: str = "All",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: str = "false",
    sort_by: str = "id",
    sort_dir: str = "asc"
):
    in_stock_bool = in_stock_only.lower() == "true"
    
    with rx.session() as session:
        query = get_filtered_query(
            search, category, min_price, max_price, in_stock_bool, sort_by, sort_dir
        )
        results = session.exec(query).all()
        
        return {
            "result_count": len(results),
            "filtered": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "sku": p.sku,
                    "price": p.price,
                    "in_stock": p.in_stock
                } for p in results
            ]
        }

app = rx.App(api_transformer=api_app)
app.add_page(index, on_load=State.on_load)
