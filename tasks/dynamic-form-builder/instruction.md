# Dynamic Form Builder (Reflex)

## Background
Build a single-page "dynamic form builder" web app using the **Reflex** Python framework. A user composes a form by adding, removing, and reordering field definitions. A live preview panel renders the form that is being built, and submitting a valid form persists the resulting schema and values to a local SQLite database.

The environment already has `uv` and Reflex's system prerequisites installed. Manage the Python environment for the app exclusively with `uv` (some Reflex dependencies conflict with system packages). Everything runs locally — no external services, accounts, or network APIs are involved.

## Requirements
Implement a Reflex app served at the index route `/` with two side-by-side panels:

**Builder panel** (left):
- A text input to type a new field's label, a selector to pick the new field's type (one of exactly `text`, `number`, `select`), and a button to append the field to the form definition.
- The current list of field definitions, rendered in order. Each row shows the field's label and offers: a control to toggle whether the field is **required**, a control to move the field one position **up**, a control to move it one position **down**, and a control to **remove** it.

**Preview panel** (right):
- The generated form, rendered dynamically from the field-definition list. Each field renders a different input widget depending on its type: a text field renders a text input, a number field renders a numeric input, and a select field renders a dropdown/combobox. The widget used per type must be chosen by matching on the field's type value (not hard-coded per field).
- A read-only indicator of the current field count and a read-only indicator of whether the form is currently valid (a form is valid only when every field marked required has a non-empty submitted value). Both indicators must update reactively as fields and values change.
- A submit button. Submitting when any required field is empty must reject the submission and surface a visible error, without writing to the database. Submitting a valid form must persist one record and surface a visible success message.

**Persistence:**
- Store each successful submission as one row in a local SQLite table named `submission`, with a text column `schema_json` and a text column `values_json`.
- `schema_json` holds a JSON array of the field definitions in their current order; each element is an object with exactly the keys `label`, `type`, and `required`.
- `values_json` holds a JSON object mapping each field's `label` to its submitted value (as a string).

## Implementation Hints
- Model each field definition as a serializable structured type (e.g., a subclass of `rx.Base`) held in a list state var, and render the definition rows and the preview widgets with `rx.foreach`.
- Select the preview widget for each field with `rx.match` keyed on the field type.
- Derive the field count and the validity indicator with computed vars (`@rx.var`).
- Persist submissions with an `rx.Model` table and a Reflex session; initialize/migrate the database so the `submission` table exists before running.
- Use `uv` for all Python/Reflex commands (e.g., `uv init`, `uv add reflex`, `uv run reflex init --template blank`, `uv run reflex db ...`, `uv run reflex run`). Initialize the project non-interactively with the blank template.

### Interface (hard requirements the tests rely on)
- Project path: `/home/user/dynamic_form_builder` (Reflex app name `dynamic_form_builder`).
- Start command: `uv run reflex run` (run from the project path). Frontend port: `3000`. Backend port: `8000`.
- The index page (`http://localhost:3000/`) must display the visible heading text `Dynamic Form Builder`.
- The field-count indicator must render the exact text `Fields: N` where `N` is the current number of field definitions (e.g., `Fields: 0` initially).
- The validity indicator must render the exact text `Status: valid` when the form is valid and `Status: invalid` otherwise.
- The new-field label input must use the placeholder `New field label`.
- The new-field type selector must offer exactly the option values `text`, `number`, and `select`.
- The button that appends a field must have the visible label `Add Field`.
- Each field-definition row must, in field order, provide: a required toggle (a checkbox), a move-up control with visible label `Up`, a move-down control with visible label `Down`, and a remove control with visible label `Remove`.
- In the preview, each `text` and `number` field's input must use that field's label as its placeholder.
- The submit button must have the visible label `Submit`.
- On an invalid submit, show visible text containing `Please fill required fields` and do not insert a database row.
- On a valid submit, show visible text containing `Saved` and insert exactly one row into the `submission` table.
- SQLite database file: `/home/user/dynamic_form_builder/reflex.db` (the default Reflex SQLite database).
- After you finish, you MUST stop/kill every background server or process you started (e.g., the `reflex run` dev server) so that ports 3000 and 8000 are free. The evaluation starts its own server.

