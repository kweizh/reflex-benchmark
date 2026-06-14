import asyncio
import random
import time
from fastapi import FastAPI
import reflex as rx

# --- Engine Logic ---

class TickerEngine:
    def __init__(self):
        self.symbols = ["AAPL", "GOOG", "MSFT", "AMZN", "TSLA"]
        self.seeds = {
            "AAPL": 150.0,
            "GOOG": 2800.0,
            "MSFT": 300.0,
            "AMZN": 3300.0,
            "TSLA": 700.0
        }
        self.prices = self.seeds.copy()
        self.update_count = 0
        self.running = False
        self._last_tick_time = 0
        self._lock = asyncio.Lock()
        self._global_task = None
        # Deterministic seed as requested
        random.seed(42)

    def tick(self):
        for s in self.symbols:
            change = random.uniform(-0.005, 0.005)
            self.prices[s] *= (1 + change)
            # Clamped so that price stays strictly positive
            if self.prices[s] <= 0:
                self.prices[s] = 0.01
        self.update_count += 1
        self._last_tick_time = time.time()

    async def tick_once(self):
        """Rate-limited tick to prevent double-ticking from multiple loops."""
        async with self._lock:
            now = time.time()
            if now - self._last_tick_time >= 0.4:  # 500ms target, 400ms threshold
                self.tick()

    def start(self):
        if not self.running:
            self.running = True
            if self._global_task is None or self._global_task.done():
                self._global_task = asyncio.create_task(self._global_loop())
            return True
        return False

    def stop(self):
        self.running = False

    async def _global_loop(self):
        while self.running:
            await self.tick_once()
            await asyncio.sleep(0.5)
        self._global_task = None

    def get_snapshot(self):
        percent_changes = {
            s: round((self.prices[s] - self.seeds[s]) / self.seeds[s] * 100.0, 4)
            for s in self.symbols
        }
        return {
            "running": self.running,
            "update_count": self.update_count,
            "seeds": self.seeds,
            "prices": {s: round(p, 4) for s, p in self.prices.items()},
            "percent_changes": percent_changes
        }

engine = TickerEngine()

# --- FastAPI Sub-app ---

api = FastAPI()

@api.post("/ticker/start")
async def api_start():
    started = engine.start()
    return {"running": True, "started": started}

@api.post("/ticker/stop")
async def api_stop():
    engine.stop()
    return {"running": False}

@api.get("/ticker/snapshot")
async def api_snapshot():
    return engine.get_snapshot()

# --- Reflex App ---

class State(rx.State):
    prices: dict[str, float] = engine.seeds.copy()
    seeds: dict[str, float] = engine.seeds.copy()
    running: bool = False
    update_count: int = 0
    
    # Backend-only vars (underscore prefixed)
    _loop_active: bool = False
    _should_run: bool = False

    @rx.var(cache=True)
    def percent_changes(self) -> dict[str, float]:
        # Depends on self.prices and self.seeds
        return {
            s: round((self.prices[s] - self.seeds[s]) / self.seeds[s] * 100.0, 4)
            for s in self.prices
        }

    @rx.event
    def start_ticker(self):
        self._should_run = True
        # Idempotency guard for the background task is inside the task itself
        return State.tick_loop

    @rx.event
    def stop_ticker(self):
        self._should_run = False
        engine.stop()

    @rx.event(background=True)
    async def tick_loop(self):
        async with self:
            if self._loop_active:
                return
            self._loop_active = True

        # Ensure engine is running (e.g. if started from UI)
        engine.start()

        while True:
            async with self:
                if not self._should_run or not engine.running:
                    self._loop_active = False
                    self.running = engine.running
                    return
                
                # Drive the engine (rate-limited)
                await engine.tick_once()
                
                # Mirror the engine state
                self.prices = engine.prices.copy()
                self.update_count = engine.update_count
                self.running = engine.running
            
            await asyncio.sleep(0.5)

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Stock Ticker", size="9"),
            rx.text(
                rx.cond(
                    State.running,
                    "Status: Running",
                    "Status: Stopped"
                ),
                color=rx.cond(State.running, "green", "red")
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
                        State.prices.keys(),
                        lambda symbol: rx.table.row(
                            rx.table.cell(symbol),
                            rx.table.cell(State.prices[symbol].to_string()),
                            rx.table.cell(State.percent_changes[symbol].to_string() + "%"),
                        )
                    )
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button("Start", on_click=State.start_ticker, color_scheme="green"),
                rx.button("Stop", on_click=State.stop_ticker, color_scheme="red"),
            ),
            spacing="5",
            padding="5",
        )
    )

app = rx.App(api_transformer=lambda app: app.mount("/api", api) or app)
app.add_page(index)
