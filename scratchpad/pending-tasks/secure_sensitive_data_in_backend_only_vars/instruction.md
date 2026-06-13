An application currently stores a sensitive API token in a standard Reflex state variable. This exposes the token in the compiled JavaScript bundle and risks a `VarTypeError` if assigned a non-serializable client object.

You need to refactor the `AppState` class to securely store a third-party API key without synchronizing or serializing it to the frontend client.

**Constraints:**
- You MUST prefix the sensitive variable with an underscore (e.g., `_api_key`) to convert it into a Backend-Only Var.
- You must ensure this variable is NEVER hardcoded into the declarative UI layout (e.g., inside `rx.text()`).
- Implement a secure event handler that utilizes this private variable for backend logic without exposing its value.