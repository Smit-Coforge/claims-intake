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

Work from the `claims-intake/` directory (where `pyproject.toml` lives):

```
cd /workspaces/claims-intake/claims-intake
```

## Run and test the service from scratch

You need two terminals. One holds the API process. The other sends HTTP
requests against it.

### 1. Start the API (terminal 1)

From `claims-intake/`:

```
uv run uvicorn claims.api.routes:app --host 0.0.0.0 --port 8000
```

Leave this process running. The app listens on port 8000. You should see uvicorn
report that it is serving; do not stop it while you exercise the endpoints.

### 2. Send a notice of loss (terminal 2)

In a second terminal, still from `claims-intake/` (or any directory — this call
only needs the running server), post a notification:

```
curl -sS -X POST http://127.0.0.1:8000/notifications \
  -H 'Content-Type: application/json' \
  -d '{
    "policy_number": "MOT-4471",
    "loss_date": "2026-04-02",
    "claim_type": "collision",
    "estimated_amount": "4200.00",
    "description": "Rear ended at a junction."
  }'
```

This payload is `VALID-01` from `data/fnol_valid.json`. Policy `MOT-4471` is in
`data/policies.json` and admits this loss.

### 3. What a successful response looks like

On success the service returns `201` and a body like:

```
{
  "claim_reference": "CLM-2026-000001",
  "status": "recorded"
}
```

`claim_reference` is unique. The sequence number increments for each recorded
notification.

### 4. Try a refusal (optional)

Sending the same payload again should fail with `409` and
`DUPLICATE_NOTIFICATION`, because a notification for that policy, loss date, and
claim type is already recorded. Other refusal cases (unknown policy, amount over
limit, cancelled policy, and so on) are defined in `docs/api-contract.md`. Sample
invalid and edge payloads live in `data/fnol_invalid.json` and
`data/fnol_edge.json`.

## Run the automated checks

From `claims-intake/`:

```
uv run pytest
uv run ruff check .
uv run mypy
```

These do not require the uvicorn process. The integration tests start the app in
process.

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
