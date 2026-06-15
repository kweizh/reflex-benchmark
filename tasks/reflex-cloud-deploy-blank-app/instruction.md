# Deploy a Blank Reflex App to Reflex Cloud

## Background
Reflex is a Python full-stack web framework. Reflex Cloud is the managed hosting service offered by the Reflex team that lets developers deploy a Reflex application from the CLI without provisioning any infrastructure.

In this task you will scaffold a minimal Reflex application from the `blank` template, prepare it for cloud deployment, write a reproducible deploy script, and push the app to Reflex Cloud non-interactively using your `REFLEX_CLOUD_TOKEN` and `REFLEX_CLOUD_PROJECT_ID`.

## Requirements
- Scaffold a minimal Reflex project at `/home/user/myproject` using `uv` and the `blank` template.
- Produce a `requirements.txt` file at the project root that lists `reflex` as a dependency.
- Author a deployment script `deploy.sh` at the project root that, when executed, performs the entire deploy flow non-interactively against Reflex Cloud and records the deployed app name to a log file.
- The deployed app name MUST be generated at deploy time so each run is unique (use a short random suffix produced inside `deploy.sh` itself — e.g. via `python3 -c "import secrets; print(secrets.token_hex(4))"` or `openssl rand -hex 4`). Do **NOT** pass the suffix in via an environment variable.
- Run `deploy.sh` so the app is actually deployed to Reflex Cloud.

## Implementation Hints
- Use `uv init && uv add reflex && uv run reflex init --template blank` to scaffold the project without any interactive prompts.
- Generate `requirements.txt` from the locked uv environment (e.g. `uv pip freeze > requirements.txt`). The file must contain a line for `reflex`.
- For the Reflex Cloud CLI, the official non-interactive flag is `--no-interactive`. Pass the token with `--token` and the project with `--project`. You may also pass `--app-name` to set the unique app name on the deploy command.
- The `reflex cloud apps list` command supports a `--json` flag which is convenient if you want to inspect deployments programmatically; the task verifier only requires that at least one deployment row is present.
- Before exiting, `deploy.sh` MUST kill any Reflex background processes it may have started (frontend on port 3000 or backend on port 8000) so the environment is left clean.

## Acceptance Criteria
- Project path: `/home/user/myproject`
- The executor is responsible for actually running `deploy.sh` so the deployment really happens on Reflex Cloud.
- Log file: `/home/user/myproject/deploy.log`
- Files at the project root:
  - `rxconfig.py` exists (created by `reflex init`).
  - `requirements.txt` exists and contains a line matching the regex `^reflex(\b|[<>=~!].*)?$` (case-insensitive).
  - `deploy.sh` exists and is executable.
- `deploy.sh` MUST be a self-contained Bash script that:
  - Reads `REFLEX_CLOUD_TOKEN` and `REFLEX_CLOUD_PROJECT_ID` from the environment (it MUST NOT hard-code these values).
  - Generates a unique app name suffix at execution time and uses it for the deployed app name (so re-running the script produces a different app name each time).
  - Calls the Reflex Cloud CLI with `--no-interactive` for any commands that would otherwise prompt.
  - Writes the deployed app name to `/home/user/myproject/deploy.log` in the format `Deployed app: <app_name>`.
- After `deploy.sh` finishes, running `uv run reflex cloud apps list --project "$REFLEX_CLOUD_PROJECT_ID" --token "$REFLEX_CLOUD_TOKEN" --no-interactive` MUST return at least one non-empty deployment row on stdout.
- No Reflex background processes (frontend or backend) may remain running after the deploy finishes.

