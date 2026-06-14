"""Shared in-memory ticker engine used by both Reflex State and REST endpoints."""

import asyncio
import random
from typing import Dict, Tuple

SEEDS: Dict[str, float] = {
    "AAPL": 150.00,
    "GOOG": 2800.00,
    "MSFT": 300.00,
    "AMZN": 3300.00,
    "TSLA": 700.00,
}


class TickerEngine:
    """In-memory price engine with its own asyncio task for the tick loop."""

    def __init__(self) -> None:
        self.seeds: Dict[str, float] = dict(SEEDS)
        self.prices: Dict[str, float] = dict(SEEDS)
        self.running: bool = False
        self.update_count: int = 0
        self._loop_active: bool = False
        self._task: asyncio.Task | None = None
        self._rng: random.Random = random.Random(42)

    # ---- public API ----

    def start(self) -> Tuple[bool, bool]:
        """Start the ticker idempotently.

        Returns:
            (running, started) where *started* is True only if this call
            actually started a new loop.
        """
        if self._loop_active:
            return (True, False)

        self._loop_active = True
        self.running = True
        self.update_count = 0
        self.prices = dict(SEEDS)
        self._rng = random.Random(42)  # reset RNG for reproducibility
        self._task = asyncio.ensure_future(self._tick_loop())
        return (True, True)

    def stop(self) -> bool:
        """Stop the ticker. Returns False (the new running state)."""
        self._loop_active = False
        self.running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        return False

    def snapshot(self) -> dict:
        """Return a snapshot of the current state."""
        return {
            "running": self.running,
            "update_count": self.update_count,
            "seeds": dict(self.seeds),
            "prices": dict(self.prices),
            "percent_changes": {
                s: round(
                    (self.prices[s] - self.seeds[s]) / self.seeds[s] * 100.0, 4
                )
                for s in self.seeds
            },
        }

    # ---- internal ----

    async def _tick_loop(self) -> None:
        try:
            while self._loop_active:
                await asyncio.sleep(0.5)
                if self._loop_active:
                    self._tick()
        except asyncio.CancelledError:
            pass

    def _tick(self) -> None:
        for symbol in self.seeds:
            delta = self.prices[symbol] * self._rng.uniform(-0.005, 0.005)
            new_price = self.prices[symbol] + delta
            if new_price <= 0:
                new_price = 0.01
            self.prices[symbol] = new_price
        self.update_count += 1


# Module-level singleton
engine = TickerEngine()