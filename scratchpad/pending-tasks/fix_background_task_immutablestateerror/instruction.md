A Reflex application crashes with an `ImmutableStateError` because a developer attempted to mutate state directly inside a long-running concurrent operation without acquiring the proper lock.

You need to refactor the `run_long_operation` background task (`@rx.event(background=True)`) to ensure state mutations are thread-safe and the UI remains responsive during execution.

**Constraints:**
- You MUST use `async with self:` to wrap all state mutations inside the background task.
- Do NOT place `asyncio.sleep()` or simulated heavy I/O calls inside the state lock block.
- Ensure the `_task_running` backend-only var accurately reflects the task's active status.