# Evaluation Dataset Research: Reflex Framework

This document contains a deep technical analysis of the **Reflex** (formerly Pynecone) full-stack Python framework. It is structured specifically for creating high-quality evaluation datasets and benchmark tasks for AI coding agents.

---

## 1. Library Overview

### Description
**Reflex** is an open-source, full-stack framework that enables developers to build and deploy web applications entirely in pure Python. It compiles declarative Python UI definitions into a Next.js/React frontend while running a FastAPI backend server, establishing a unified websocket-based state synchronization protocol between the client and server.

### Ecosystem Role
Reflex eliminates the typical context switching of web development by merging frontend UI, backend server logic, state management, and database models into a single Python codebase. It is primarily used for:
* **AI & LLM Applications**: Building rich, interactive AI chat interfaces and agent dashboards with streaming responses.
* **Data Dashboards**: Constructing real-time analytical interfaces wrapping libraries like Plotly or Pyplot.
* **Internal Tools & SaaS Boilerplates**: Rapid prototyping of data-driven systems with built-in database ORMs and user authentication.

### Project Setup (Non-Interactive CLI)

To initialize and run a Reflex application in a non-interactive environment (such as a Docker container or CI/CD runner), use the Astral `uv` package manager with the `--template blank` flag to bypass CLI prompts.

```bash
# 1. Create and enter project directory
mkdir hello_reflex
cd hello_reflex

# 2. Initialize a Python project and add Reflex
uv init
uv add reflex

# 3. Initialize the Reflex project non-interactively using the blank template
uv run reflex init --template blank

# 4. Initialize and apply the SQLite database schema/migrations
uv run reflex db init
uv run reflex db makemigrations --message "initial schema"
uv run reflex db migrate

# 5. Run the Reflex application in development mode (hot-reloads enabled)
# This spins up the frontend on port 3000 and the backend on port 8000
uv run reflex run --loglevel debug
```

**IMPORTANT NOTES:**

Please note that, some dependencies of reflex has conflicts with the system python packages. So, MUST use `uv` to manage the python environment in Dockerfile and task description.
When using `uv`, MUST make sure the dependencies are installed and the environment is activated before run.

For initial state and final state tests, it always run by the system python3 and python3-tests, so should not assume reflex installed and only check the env and outputs.

### Cloud Deployment (Reflex Cloud)

Reflex provides a managed hosting service (Reflex Cloud) to easily deploy applications without configuring infrastructure.

**Prerequisites:**
- `reflex>=0.6.6`
- A working Reflex application
- A `requirements.txt` file at the root of the project containing all Python dependencies (e.g., generated via `uv pip freeze > requirements.txt`).

**Deployment Steps:**

1. **Authentication:**
   Log in to Reflex Cloud via the CLI.
   This must be executed in a reflex project folder.

   ```bash
   uv run reflex cloud config --no-interactive --token REFLEX_CLOUD_TOKEN
   ```

2. **Deployment:**
   Use the `reflex deploy` command with your project ID (obtained from the Reflex Cloud Web UI dashboard).
   ```bash
   uv run reflex deploy --project REFLEX_CLOUD_PROJECT_ID
   ```
   The deployment process is interactive by default and will check your `requirements.txt`, confirm the new app deployment, and optionally ask for a description. Once uploaded, the deployment continues on the cloud infrastructure, and the live application URL will be available in the Reflex Cloud Dashboard.

3. **App Management (Reflex Cloud Apps CLI):**
   Reflex Cloud provides several commands to manage deployed applications.

   - **List deployments:**
     ```bash
     uv run reflex cloud apps list
     ```
   - **Check deployment status:**
     ```bash
     uv run reflex cloud apps status <deployment-id>
     ```
   - **Stop/Start an application:**
     ```bash
     uv run reflex cloud apps stop <app-id>
     uv run reflex cloud apps start <app-id>
     ```
   - **Scale an application (e.g., change VM type or regions):**
     ```bash
     uv run reflex cloud apps scale <app-id> --vmtype <type> --regions <region>
     ```
   - **View application logs:**
     ```bash
     uv run reflex cloud apps logs <app-id> --follow
     ```
   - **Delete an application:**
     ```bash
     uv run reflex cloud apps delete <app-id>
     ```

---

## 2. Core Primitives & APIs

### Key Concepts & Documentation Index

* [State Overview](https://reflex.dev/docs/state/overview/): Defining the state class, backend/frontend vars, and state lifecycle.
* [Base Vars](https://reflex.dev/docs/vars/base-vars/): Fields inside the State class representing mutable data synchronized with the client.
* [Computed Vars](https://reflex.dev/docs/vars/computed-vars/): Derived read-only properties calculated on the backend, with caching configurations.
* [Custom Vars & Dataclasses](https://reflex.dev/docs/vars/custom-vars/): Utilizing Pydantic models or dataclasses for complex data structures.
* [Custom Serializers](https://reflex.dev/docs/wrapping-react/serializers/): Registering custom JSON encoders for non-primitive types.
* [Event Handlers & Triggers](https://reflex.dev/docs/events/events-overview/): Server-side methods responding to user actions.
* [Yielding Updates & Chaining](https://reflex.dev/docs/events/yield-events/): Creating generator event handlers to stream UI updates or chain handlers.
* [Background Tasks](https://reflex.dev/docs/events/background-events/): Long-running concurrent operations using `@rx.event(background=True)`.
* [Conditional Rendering & Iterables](https://reflex.dev/docs/components/conditional-rendering/): Dynamic UI generation using `rx.cond`, `rx.match`, and `rx.foreach`.
* [Pages & Dynamic Routing](https://reflex.dev/docs/pages/dynamic-routing/): Defining application routes, dynamic path segments, and query parameters.
* [Database Models & Queries](https://reflex.dev/docs/database/overview/): Defining SQL tables using `rx.Model` and executing queries.
* [Client Storage](https://reflex.dev/docs/client-storage/overview/): Storing data on the browser via `rx.Cookie` and `rx.LocalStorage`.
* [API Transformer](https://reflex.dev/docs/api-routes/overview/): Integrating custom FastAPI applications and ASGI middleware.
* [Wrapping React Components](https://reflex.dev/docs/wrapping-react/overview/): Creating custom Reflex components wrapping npm packages.

---

### Detailed Primitives & Code Snippets

#### A. State Architecture, Vars, and Background Tasks
Reflex splits state variables into **Base Vars** (synchronized), **Backend-Only Vars** (prefixed with `_`), and **Computed Vars** (derived). Long-running async tasks use `@rx.event(background=True)` and must acquire an exclusive lock via `async with self` to modify state.

```python
import asyncio
import reflex as rx

class AppState(rx.State):
    # 1. Base Var (Synchronized to client)
    status_message: str = "Ready"
    progress: int = 0

    # 2. Backend-Only Var (Never sent to client; secure/sensitive)
    _api_key: str = "sk-secure-token-12345"
    _task_running: bool = False

    # 3. Computed Var (Derived, cached by default)
    @rx.var(cache=True)
    def progress_percentage(self) -> str:
        return f"{self.progress}%"

    # 4. Background Task (Concurrent execution)
    @rx.event(background=True)
    async def run_long_operation(self):
        async with self:
            if self._task_running:
                return  # Prevent duplicate task execution
            self._task_running = True
            self.status_message = "Processing..."
            self.progress = 0

        # Run expensive async I/O outside the state lock to avoid blocking the UI
        for i in range(1, 6):
            await asyncio.sleep(1)

            # Re-enter State lock to safely mutate synchronized vars
            async with self:
                self.progress = i * 20

        async with self:
            self.status_message = "Completed!"
            self._task_running = False
```

#### B. Database Integration (SQLModel ORM)
Reflex database models inherit from `rx.Model` (a wrapper around SQLModel/SQLAlchemy). Queries are executed using `rx.session()` (synchronous) or `rx.asession()` (asynchronous for background events).

```python
from typing import Optional
import reflex as rx

# 1. Database Model Definition
class User(rx.Model, table=True):
    username: str
    email: str
    is_active: bool = True

class DatabaseState(rx.State):
    users: list[User] = []
    search_query: str = ""

    # Synchronous DB transaction inside standard event handler
    @rx.event
    def create_user(self, username: str, email: str):
        with rx.session() as session:
            new_user = User(username=username, email=email)
            session.add(new_user)
            session.commit()
            session.refresh(new_user)  # Populates autogenerated ID field
        return DatabaseState.fetch_users  # Chain event handler

    # Asynchronous DB query inside a background event handler
    @rx.event(background=True)
    async def fetch_users(self):
        async with rx.asession() as asession:
            if self.search_query:
                stmt = User.select().where(User.username.contains(self.search_query))
            else:
                stmt = User.select()
            result = await asession.execute(stmt)
            users_list = [row[0] for row in result.all()]

            async with self:
                self.users = users_list
```

#### C. Custom Type Serialization
Custom classes used inside state variables must be JSON-serializable. This is accomplished by subclassing `rx.Base` or registering a custom serializer function using `@rx.serializer`.

```python
import datetime
import reflex as rx

# Option 1: Subclassing rx.Base (wraps Pydantic)
class TaskItem(rx.Base):
    title: str
    created_at: str = datetime.datetime.now().isoformat()
    priority: int = 1

# Option 2: Custom Serializer for non-serializable objects (e.g., datetime)
@rx.serializer
def serialize_datetime(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

class CustomTypeState(rx.State):
    tasks: list[TaskItem] = []
    last_checked: datetime.datetime = datetime.datetime.now()

    @rx.event
    def add_task(self, title: str):
        self.tasks.append(TaskItem(title=title))
        self.last_checked = datetime.datetime.now()
```

#### D. Wrapping React Components (Extending UI)
You can wrap any npm-published React component into Reflex by subclassing `rx.Component` or `NoSSRComponent` (to bypass server-side rendering issues).

```python
from reflex.components.component import NoSSRComponent
import reflex as rx

class ColorPicker(NoSSRComponent):
    # 1. Define the npm package name and version
    library = "react-colorful@5.7.0"

    # 2. Define the React component tag
    tag = "HexColorPicker"

    # 3. Define the component's props as rx.Var types
    color: rx.Var[str]

    # 4. Define event triggers and serialize their arguments into list formats
    on_change: rx.EventHandler[lambda color: [color]]

# Expose a clean constructor function
color_picker = ColorPicker.create
```

---

## 3. Real-World Use Cases & Templates

### Showcase & Reference Implementations
* **[Reflex Chat App](https://github.com/reflex-dev/reflex-chat)**: A production-ready ChatGPT clone. Demonstrates real-time streaming using generator-based event handlers (`yield`), responsive message layouts, and multiple-room session state.
* **[Reflex LLM Examples](https://github.com/reflex-dev/reflex-llm-examples)**: A curated repository of advanced AI applications, including RAG (Retrieval-Augmented Generation) pipelines and multi-agent workflows.
* **[Chat Template Demo](https://github.com/reflex-dev/chat-template-demo)**: An interactive application demonstrating how to load LlamaIndex, Traceloop, and OpenAI SDKs inside Reflex to query local knowledge bases.
* **[Official Templates Gallery](https://reflex.dev/templates/)**: A compilation of structured dashboards, portfolio pages, and SaaS starter kits highlighting grid layouts and client-side storage persistence.

---

## 4. Developer Friction Points

### 1. ImmutableStateError in Background Tasks
* **Symptom**: The application crashes with the error:
  `reflex.utils.exceptions.ImmutableStateError: Background task StateProxy is immutable outside of a context manager. Use async with self to modify state.`
* **Cause**: Background tasks (`@rx.event(background=True)`) execute concurrently. To maintain thread-safety and prevent race conditions, Reflex marks the State proxy as immutable. Attempting to write to `self.var` directly outside of an `async with self` context raises this exception.
* **Resolution**: Always wrap any state mutations in an `async with self:` block. Keep network requests or heavy calculations outside the block to prevent locking the UI thread.
* **Link**: [Background Tasks Docs](https://reflex.dev/docs/events/background-events.md)

### 2. VarTypeError with Non-Serializable State Fields
* **Symptom**: During app compilation or state update, the console raises:
  `reflex.utils.exceptions.VarTypeError: State vars must be of a serializable type. Valid types include strings, numbers, booleans, lists, dictionaries, dataclasses, datetime objects, and pydantic models. Found var ... with type ...`
* **Cause**: Reflex synchronizes state fields to the frontend by converting them to JSON. If a developer stores a database connection, a raw numpy array, or a complex third-party class directly in a standard state variable, the JSON encoder fails.
* **Resolution**:
  1. Prefix the field with an underscore (e.g., `_my_db_conn`) to mark it as backend-only (this skips JSON synchronization).
  2. Register a custom serializer using `@rx.serializer`.
  3. Subclass `rx.Base` for custom data structures.
* **Link**: [Custom Vars Docs](https://reflex.dev/docs/vars/custom-vars.md)

### 3. Security Risk: Public Exposure of Statically Rendered UI Data
* **Symptom**: Private tokens, configuration keys, or unauthorized data are visible in the browser's source files (network tab / compiled JavaScript assets) even when hidden behind dynamic logic like `rx.cond`.
* **Cause**: Reflex compiles Python UI definitions into static React/Next.js pages at compile-time. Any static strings or parameters passed to components during compilation (e.g., `rx.text("SECRET_API_KEY")` or hardcoded lists) are written directly into the compiled JavaScript bundle.
* **Resolution**: Never hardcode sensitive parameters in the layout function. Instead, bind the component to a reactive State var (e.g., `rx.text(State.sensitive_data)`). The state variable should start empty and only be populated at runtime from a secure backend-only variable (`_api_key`) after verifying user permissions.
* **Link**: [Authentication Overview Docs](https://reflex.dev/docs/authentication/authentication-overview.md)

### 4. Evaluation values requirements

* If a value is required from the user, they should be passed as environment variables, like REFLEX_CLOUD_TOKEN, REFLEX_CLOUD_PROJECT_ID, etc.
* If a value is optional, then should pick a good default value and should not be passed as an environment variable.
* If a value is a random value or specific value for the evaluation, for example, JWT_SECRET, USERNAME, PASSWORD, then should generate a random value directly and should not be passed as an environment variable.

### 5. Always kill the background server after evaluation

Background jobs may be used during the evaluation, for example, to run a dev server for tests, but MUST specify in task description to ask models to kill all background servers after evaluation, and SHOULD start the required servers in final tests for validation if necessary.

---

## 5. Evaluation Ideas

* **Simple: Real-Time Character Counter**
  * *Difficulty*: Simple
  * *Description*: Build a text area input that reactively counts and displays character and word counts using a cached computed var.
* **Simple: Dynamic Tab-Based Toggle Panel**
  * *Difficulty*: Simple
  * *Description*: Implement a dynamic tab system using `rx.match` to switch between different component layouts based on the active tab state.
* **Medium: Async Paginated Database Table**
  * *Difficulty*: Medium
  * *Description*: Create a paginated user directory table that loads chunks of data asynchronously from an SQLite database using `rx.asession` and a background task.
* **Medium: Multi-Step Form Wizard with Client-Side Persistence**
  * *Difficulty*: Medium
  * *Description*: Implement a multi-page registration wizard that validates inputs at each step and persists draft data in `rx.LocalStorage` to survive browser refreshes.
* **Medium: LLM Streaming Panel with Loading States**
  * *Difficulty*: Medium
  * *Description*: Build an interface that streams simulated chunked text responses using a generator-based event handler (`yield`), toggling a loading spinner at the beginning and end of the stream.
* **Complex: Custom React Rich-Text Editor Wrapper**
  * *Difficulty*: Complex
  * *Description*: Wrap a third-party React rich-text editor (such as `react-quill`) into a custom Reflex component, defining proper state bindings and serializing change event arguments.
* **Complex: Secure Token-Based API Gateway Integration**
  * *Difficulty*: Complex
  * *Description*: Mount a custom FastAPI authentication router onto a Reflex application using the `api_transformer` initialization parameter, ensuring JWT tokens are stored in backend-only state variables.
* **Complex: Real-Time Collaborative Document Canvas**
  * *Difficulty*: Complex
  * *Description*: Develop a multi-client drawing canvas or text board that uses background tasks (`@rx.event(background=True)`), state locking, and polling to coordinate and broadcast concurrent edits.

---

## 6. Sources

1. [Reflex Official Documentation](https://reflex.dev/docs/): The primary documentation portal for the Reflex framework.
2. [Reflex LLMs.txt Index](https://reflex.dev/docs/llms.txt): A structured Markdown index of the entire documentation suite optimized for LLMs.
3. [Reflex Framework GitHub Repository](https://github.com/reflex-dev/reflex): Open-source codebase, issues, and releases.
4. [Reflex Chat App Template](https://github.com/reflex-dev/reflex-chat): Official OpenAI chat application template using Reflex.
5. [Reflex LLM Examples Collection](https://github.com/reflex-dev/reflex-llm-examples): Curated repository of advanced AI applications and RAG integrations.
6. [SQLModel Select Tutorial](https://sqlmodel.tiangolo.com/tutorial/select/): Reference for SQLModel select query syntax which Reflex models subclass.
7. [Astral uv Documentation](https://docs.astral.sh/uv/): Installation and environment management reference.
