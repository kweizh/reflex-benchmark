"""Credentials generation and persistence.

On import, generates random credentials and writes them to
credentials.json if the file does not already exist.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

CREDENTIALS_PATH = Path("/home/user/oauth_app/credentials.json")

# Load existing or generate new credentials
if CREDENTIALS_PATH.exists():
    _data = json.loads(CREDENTIALS_PATH.read_text())
    CLIENT_ID: str = _data["client_id"]
    CLIENT_SECRET: str = _data["client_secret"]
    REDIRECT_URI: str = _data["redirect_uri"]
    USERNAME: str = _data["username"]
else:
    CLIENT_ID = secrets.token_urlsafe(32)
    CLIENT_SECRET = secrets.token_urlsafe(32)
    REDIRECT_URI = "http://localhost:8000/auth/callback"
    USERNAME = f"demo_user_{secrets.token_hex(4)}"

    CREDENTIALS_PATH.write_text(
        json.dumps(
            {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "username": USERNAME,
            },
            indent=2,
        )
        + "\n"
    )
