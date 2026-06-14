import reflex as rx
from sqlmodel import select, col, asc, desc
from typing import List, Optional
from fastapi import FastAPI, Query

class Product(rx.Model, table=True):
    name: str
    category: str
    sku: str
    price: float
    in_stock: bool

CATEGORIES = ["Electronics", "Books", "Clothing", "Home", "Toys", "Sports"]

def build_filter_query(search: str, category: str, min_price: Optional[float], max_price: Optional[float], in_stock_only: bool, sort_by: str, sort_dir: str):
    query = select(Product)
    
    if search:
        query = query.where(col(Product.name).icontains(search))
    
    if category and category != "All":
        query = query.where(Product.category == category)
        
    if min_price is not None:
        query = query.where(Product.price >= min_price)
        
    if max_price is not None:
        query = query.where(Product.price <= max_price)
        
    if in_stock_only:
        query = query.where(Product.in_stock == True)
        
    sort_col = getattr(Product, sort_by, Product.id)
    if sort_dir == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(asc(sort_col))
        
    return query

def seed_data():
    with rx.session() as session:
        count = session.exec(select(Product)).first()
        if count is not None:
            return
        
        for c, cat in enumerate(CATEGORIES):
            for i in range(40):
                p = Product(
                    name=f"{cat} #{i+1:02d}",
                    category=cat,
                    sku=f"{cat[:3].upper()}-{i+1:03d}",
                    price=round(5.0 + (c * 5) + (i * 1.0), 2),
                    in_stock=(i % 4) != 3
                )
                session.add(p)
        session.commit()

class State(rx.State):
    search: str = ""
    category: str = "All"
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock_only: bool = False
    sort_by: str = "id"
    sort_dir: str = "asc"
    
    result_count: int = 0
    filtered: List[Product] = []
            
    async def load_data(self):
        seed_data()
        yield State.update_results

    @rx.event(background=True)
    async def update_results(self):
        async with self:
            search = self.search
            category = self.category
            min_price = self.min_price
            max_price = self.max_price
            in_stock_only = self.in_stock_only
            sort_by = self.sort_by
            sort_dir = self.sort_dir

        query = build_filter_query(search, category, min_price, max_price, in_stock_only, sort_by, sort_dir)
        
        async with rx.asession() as session:
            result = await session.exec(query)
            products = result.all()
            
        async with self:
            self.filtered = products
            self.result_count = len(products)
            
    def set_search(self, val: str):
        self.search = val
        return State.update_results
        
    def set_category(self, val: str):
        self.category = val
        return State.update_results
        
    def set_min_price(self, val: str):
        try:
            self.min_price = float(val) if val else None
        except ValueError:
            self.min_price = None
        return State.update_results
        
    def set_max_price(self, val: str):
        try:
            self.max_price = float(val) if val else None
        except ValueError:
            self.max_price = None
        return State.update_results
        
    def set_in_stock_only(self, val: bool):
        self.in_stock_only = val
        return State.update_results
        
    def set_sort_by(self, val: str):
        self.sort_by = val
        return State.update_results
        
    def set_sort_dir(self, val: str):
        self.sort_dir = val
        return State.update_results

def render_product(p: Product):
    return rx.table.row(
        rx.table.cell(p.id),
        rx.table.cell(p.name),
        rx.table.cell(p.category),
        rx.table.cell(p.price),
        rx.table.cell(rx.cond(p.in_stock, "Yes", "No"))
    )

def index() -> rx.Component:
    return rx.container(
        rx.heading("Product Catalog"),
        rx.text(f"Result count: {State.result_count}"),
        rx.vstack(
            rx.debounce_input(
                rx.input(
                    placeholder="Search...",
                    value=State.search,
                    on_change=State.set_search,
                ),
                debounce_timeout=300,
            ),
            rx.select(
                ["All"] + CATEGORIES,
                value=State.category,
                on_change=State.set_category,
            ),
            rx.input(
                placeholder="Min Price",
                on_change=State.set_min_price,
            ),
            rx.input(
                placeholder="Max Price",
                on_change=State.set_max_price,
            ),
            rx.checkbox(
                "In stock only",
                checked=State.in_stock_only,
                on_change=State.set_in_stock_only,
            ),
            rx.select(
                ["id", "name", "price", "category"],
                value=State.sort_by,
                on_change=State.set_sort_by,
            ),
            rx.select(
                ["asc", "desc"],
                value=State.sort_dir,
                on_change=State.set_sort_dir,
            ),
        ),
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
                rx.foreach(State.filtered, render_product)
            )
        ),
        on_mount=State.load_data,
    )

api = FastAPI()

@api.get("/api/filter")
def filter_api(
    search: str = "",
    category: str = "All",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id",
    sort_dir: str = "asc"
):
    query = build_filter_query(search, category, min_price, max_price, in_stock_only, sort_by, sort_dir)
    with rx.session() as session:
        result = session.exec(query)
        products = result.all()
        
    return {
        "result_count": len(products),
        "filtered": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "sku": p.sku,
                "price": p.price,
                "in_stock": p.in_stock
            } for p in products
        ]
    }

def api_transformer(app):
    app.mount("/", api)
    return app

app = rx.App(api_transformer=api_transformer)
app.add_page(index)
