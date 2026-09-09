# Claims Intake Service

A service that accepts a first notice of loss, validates it against the policy
master and the rule table in `docs/api-contract.md`, and either records a
notification and issues a claim reference or refuses the submission with a
specific reason.

## Where things are

| Path | What it holds |
| --- | --- |
| `docs/api-contract.md` | What the service accepts, returns, and refuses. The authority. |
| `docs/requirements-brief.md` | The open work items and their acceptance criteria. |
| `docs/payload-triage.md` | Your Day 1 classification of the edge payloads. |
| `data/` | Synthetic policies and notification payloads. |
| `src/claims/` | The service. |
| `tests/` | Unit tests mirror `src/claims/`. Integration tests exercise HTTP. |

## Working in this repository

You are inside a Linux container. Confirm it before you start:

```
uname -sm     # Linux aarch64
pwd           # /workspaces/claims-intake
```

Dependencies are already installed when the container is created (`uv sync` has
already run). There is no install step. If a tool you need is missing, that is a
defect in the image specification and should be reported rather than worked
around.

Work from the `claims-intake/` directory (where `pyproject.toml` lives).

## Run the service

Start the HTTP API with uvicorn:

```
uv run uvicorn claims.api.routes:app --host 0.0.0.0 --port 8000
```

The app listens on port 8000. Leave the process running while you call it.

## Run checks

```
uv run pytest
uv run ruff check .
uv run mypy
```

## Build the container image

From `claims-intake/` (the directory with the Dockerfile):

```
docker buildx build --platform linux/amd64 -t claims-intake .
```

This environment is Linux aarch64 (ARM). The assigned runtime expects a
linux/amd64 image. Without `--platform linux/amd64`, Docker would build for ARM
and the resulting image would not match that amd64 runtime.

## Data

Everything in `data/` is synthetic and was authored for this program. It contains
no real client data and no named clients.
