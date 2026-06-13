You are building a text analysis interface in Reflex that provides real-time feedback on user input. 

You need to create a text area input that reactively counts and displays both the character count and word count of the typed text using a cached computed variable.

**Constraints:**
- Must utilize the Reflex `rx.State` class to manage the primary text input variable.
- The word and character counts MUST be derived using the `@rx.var(cache=True)` decorator.
- Do NOT use standard JavaScript directly; all UI rendering must be constructed via `rx.text_area` and `rx.text`.