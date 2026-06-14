"""Generate and persist OAuth2 credentials and demo identity."""

import json
import secrets
from pathlib import Path

CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "credentials.json"

# ── Generated values ──────────────────────────────────────────────
CLIENT_ID: str = ""
CLIENT_SECRET: str = ""
REDIRECT_URI: str = "http://localhost:8000/auth/callback"
USERNAME: str = ""
ACCESS_TOKEN: str = ""


def generate() -> None:
    """Generate random credentials and write them to credentials.json."""
    global CLIENT_ID, CLIENT_SECRET, USERNAME, ACCESS_TOKEN

    CLIENT_ID = secrets.token_urlsafe(24)
    CLIENT_SECRET = secrets.token_urlsafe(48)
    USERNAME = f"demo_user_{secrets.token_hex(4)}"
    ACCESS_TOKEN = secrets.token_urlsafe(48)

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "username": USERNAME,
    }

    CREDENTIALS_PATH.write_text(json.dumps(payload, indent=2))


def load() -> None:
    """Load credentials from credentials.json if it exists, otherwise generate."""
    global CLIENT_ID, CLIENT_SECRET, USERNAME, ACCESS_TOKEN

    if CREDENTIALS_PATH.exists():
        data = json.loads(CREDENTIALS_PATH.read_text())
        CLIENT_ID = data["client_id"]
        CLIENT_SECRET = data["client_secret"]
        USERNAME = data["username"]
        # Regenerate access_token on every load so it's fresh
        ACCESS_TOKEN = secrets.token_urlsafe(48)
    else:
        generate()


# Initialise on import
load()