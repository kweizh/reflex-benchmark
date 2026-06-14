"""Entry point for the OAuth2 PKCE Reflex application."""

from oauth_app.app import app

# The app is created as a side-effect of importing oauth_app.app
# (which also generates credentials.json on first import).
# ``reflex run`` will discover ``app`` from this module.
