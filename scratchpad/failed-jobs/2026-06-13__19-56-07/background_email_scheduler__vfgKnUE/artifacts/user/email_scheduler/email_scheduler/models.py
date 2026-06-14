import reflex as rx
from typing import Optional

class EmailDigest(rx.Model, table=True):
    recipient: str
    period_seconds: int
    last_sent_at: Optional[float] = None
    next_due_at: float

class SentEmail(rx.Model, table=True):
    digest_id: int
    recipient: str
    sent_at: float
