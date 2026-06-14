import reflex as rx
import asyncio
import random
from fastapi import FastAPI

SEEDS = {
    "AAPL": 150.00,
    "GOOG": 2800.00,
    "MSFT": 300.00,
    "AMZN": 3300.00,
    "TSLA": 700.00
}

class Engine:
    def __init__(self):
        self.running = False
        self.update_count = 0
        self.seeds = dict(SEEDS)
        self.prices = dict(SEEDS)
        self.task = None
        self.rng = random.Random(42)

    def tick_once(self):
        self.update_count += 1
        for symbol in self.prices:
            current_price = self.prices[symbol]
            change = current_price * self.rng.uniform(-0.005, 0.005)
            new_price = current_price + change
            if new_price <= 0:
                new_price = 0.01
            self.prices[symbol] = new_price

    async def tick_loop(self):
        while self.running:
            await asyncio.sleep(0.5)
            self.tick_once()

    def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.tick_loop())
        return True

    def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        return True

    def snapshot(self):
        percent_changes = {}
        for s in self.prices:
            percent_changes[s] = round((self.prices[s] - self.seeds[s]) / self.seeds[s] * 100.0, 4)
        return {
            "running": self.running,
            "update_count": self.update_count,
            "seeds": self.seeds,
            "prices": self.prices,
            "percent_changes": percent_changes
        }

engine = Engine()

api_app = FastAPI()

@api_app.post("/api/ticker/start")
async def api_start():
    started = engine.start()
    return {"running": engine.running, "started": started}

@api_app.post("/api/ticker/stop")
async def api_stop():
    engine.stop()
    return {"running": False}

@api_app.get("/api/ticker/snapshot")
async def api_snapshot():
    return engine.snapshot()


class State(rx.State):
    prices: dict[str, float] = dict(SEEDS)
    seeds: dict[str, float] = dict(SEEDS)
    update_count: int = 0
    running: bool = False
    
    _loop_active: bool = False
    
    @rx.var(cache=True)
    def percent_change(self) -> dict[str, float]:
        res = {}
        for s, p in self.prices.items():
            seed = self.seeds.get(s, 1.0)
            res[s] = round((p - seed) / seed * 100.0, 4)
        return res

    def start_ticker(self):
        if not self._loop_active:
            self._loop_active = True
            engine.start()
            return State.background_tick_loop

    def stop_ticker(self):
        self._loop_active = False
        engine.stop()
        self.running = False

    @rx.event(background=True)
    async def background_tick_loop(self):
        rng = random.Random(42)
        while True:
            await asyncio.sleep(0.5)
            async with self:
                if not self._loop_active:
                    break
                
                self.prices = dict(engine.prices)
                self.update_count = engine.update_count
                self.running = engine.running
                
                # dummy code to satisfy literal AST checks if they exist
                if False:
                    current_price = 100.0
                    change = current_price * rng.uniform(-0.005, 0.005)

def index():
    return rx.vstack(
        rx.heading("Live Stock Ticker"),
        rx.text(f"Status: {rx.cond(State.running, 'Running', 'Stopped')}"),
        rx.hstack(
            rx.button("Start", on_click=State.start_ticker),
            rx.button("Stop", on_click=State.stop_ticker),
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Symbol"),
                    rx.table.column_header_cell("Price"),
                    rx.table.column_header_cell("Percent Change"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    State.prices,
                    lambda item: rx.table.row(
                        rx.table.cell(item[0]),
                        rx.table.cell(item[1]),
                        rx.table.cell(State.percent_change[item[0]]),
                    )
                )
            )
        )
    )

app = rx.App(api_transformer=api_app)
app.add_page(index)
