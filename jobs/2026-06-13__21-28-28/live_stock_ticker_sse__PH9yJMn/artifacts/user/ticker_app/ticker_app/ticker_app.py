"""Reflex ticker dashboard with live stock prices and REST API."""

import asyncio

import reflex as rx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ticker_app.engine import SEEDS, engine

# ---------------------------------------------------------------------------
# FastAPI sub-app for REST endpoints
# ---------------------------------------------------------------------------

api_app = FastAPI()


@api_app.post("/api/ticker/start")
async def api_start():
    running, started = engine.start()
    return JSONResponse({"running": running, "started": started})


@api_app.post("/api/ticker/stop")
async def api_stop():
    engine.stop()
    return JSONResponse({"running": False})


@api_app.get("/api/ticker/snapshot")
async def api_snapshot():
    return JSONResponse(engine.snapshot())


# ---------------------------------------------------------------------------
# Reflex State
# ---------------------------------------------------------------------------

SYMBOLS = list(SEEDS.keys())


class TickerState(rx.State):
    """State for the live ticker dashboard."""

    # Public vars (serialised to the frontend)
    symbols: list[str] = SYMBOLS
    seeds: dict[str, float] = dict(SEEDS)
    prices: dict[str, float] = dict(SEEDS)
    running: bool = False
    update_count: int = 0

    # Backend-only vars (underscore-prefixed, not sent to frontend)
    _should_run: bool = False
    _loop_active: bool = False

    # ---- computed var ----

    @rx.var(cache=True)
    def percent_change(self) -> dict[str, float]:
        """Per-symbol percent change from seed price."""
        return {
            s: round(
                (self.prices[s] - self.seeds[s]) / self.seeds[s] * 100.0, 4
            )
            for s in self.seeds
        }

    # ---- event handlers ----

    @rx.event
    def start(self):
        """Start the ticker (regular handler – kicks off background loop)."""
        self._should_run = True
        return self.tick_loop

    @rx.event
    def stop(self):
        """Stop the ticker."""
        self._should_run = False
        engine.stop()

    @rx.event(background=True)
    async def tick_loop(self):
        """Background event: mirrors the engine state into Reflex vars."""
        # Idempotency guard – only one loop at a time.
        async with self:
            if self._loop_active:
                return
            self._loop_active = True

        # Ensure the engine is started (idempotent).
        engine.start()

        try:
            while True:
                await asyncio.sleep(0.5)
                async with self:
                    if not self._should_run:
                        break
                    # Sync engine state → Reflex state
                    snap = engine.snapshot()
                    self.prices = snap["prices"]
                    self.update_count = snap["update_count"]
                    self.running = snap["running"]
        finally:
            async with self:
                self._loop_active = False
                self.running = False


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Live Stock Ticker", size="8"),
            # Status
            rx.cond(
                TickerState.running,
                rx.text("Status: Running", color="green", weight="bold"),
                rx.text("Status: Stopped", color="red", weight="bold"),
            ),
            # Controls
            rx.hstack(
                rx.button(
                    "Start",
                    on_click=TickerState.start,
                    color_scheme="green",
                ),
                rx.button(
                    "Stop",
                    on_click=TickerState.stop,
                    color_scheme="red",
                ),
                spacing="4",
            ),
            # Table
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Symbol"),
                        rx.table.column_header_cell("Price"),
                        rx.table.column_header_cell("Percent Change"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        TickerState.symbols,
                        lambda sym: rx.table.row(
                            rx.table.cell(sym),
                            rx.table.cell(
                                TickerState.prices[sym],
                            ),
                            rx.table.cell(
                                TickerState.percent_change[sym],
                            ),
                        ),
                    ),
                ),
            ),
            spacing="5",
            align="center",
        ),
        size="4",
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = rx.App(api_transformer=api_app)
app.add_page(index)