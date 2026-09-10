---
name: codebase-onboarder
description: >
  Map an unfamiliar codebase into a refreshable onboarding cache: architecture,
  entry points, config locations, and gotchas. Use whenever you are dropped
  into a customer repo, a new repository, or a codebase you have not seen;
  when the user asks how the system is structured, where the app starts, where
  config lives, or what the landmines are; or when returning on a later visit
  and the onboarding files may be stale. Use even if they say "look around",
  "get oriented", "what's the layout", "onboard me", or "refresh the map"
  without naming this skill.
---

# Codebase Onboarder

You have been dropped into a repo. Produce a **cache**: four living files at the project root that a later agent (and a human) can **refresh** instead of rediscovering. Cache what looking cannot cheaply tell you — the shape, the **entry**, the override order, the **gotcha**. Leave `ls`, script names, and `--help` to the environment.

This is mapping, not redesign. Read `CONTEXT.md` / `CONTEXT-MAP.md` if they exist and use those terms. Leave those files alone. Do not invent `AGENTS.md`. If `AGENTS.md` already exists and has no pointer to the four files, add one line naming them.

Read [references/templates.md](references/templates.md) before writing. Fill those skeletons; do not invent a fifth file.

## 0. This repo (claims-intake)

Pre-resolved so a later agent does not re-derive it. Re-verify each line against current code; correct it here when it goes stale.

**Root.** The git root `/workspaces/claims-intake` is a holding folder, not the app. The inner project is `claims-intake/` — it owns `pyproject.toml`, `uv.lock`, `src/claims/`, `tests/`, `Dockerfile`, `.devcontainer/`, `README.md`, `docs/`. Cache the four files at `claims-intake/`, beside `README.md`. `StatusTracker/` at the git root is not a project: it is git-ignored (`git status --ignored` reports `!! StatusTracker/`) and holds only a stale `.venv`. Do not onboard it and do not treat it as a second app.

**Authored docs — read, cite, never rewrite.** These are this repo's `CONTEXT.md`:

- `claims-intake/docs/api-contract.md` — the authority. Where code and this document disagree, the document is correct and the code is a defect. Sections 1–3 are fixed.
- `claims-intake/docs/requirements-brief.md` — work items `WI-####` and their binary acceptance criteria.
- `claims-intake/docs/payload-triage.md`, `docs/agent-log.md` (accepted/rejected decisions), `docs/tool-comparison.md`.

**Entry, already known.** `POST /notifications` in `claims-intake/src/claims/api/routes.py`; served by `uv run uvicorn claims.api.routes:app --host 0.0.0.0 --port 8000` from `claims-intake/`; same app in the `Dockerfile` `CMD`; checks in `.github/workflows/checks.yaml` at the **git root** with `working-directory: claims-intake`.

**Landmines to re-verify, not rediscover.**

- Every `uv run` command belongs in `claims-intake/`, not the git root. Running from the root makes pytest import the wrong `claims.api.routes` (all HTTP tests return 404) and makes mypy fail with `Duplicate module named "__main__"`.
- The venv is `claims-intake/.venv`. There is no venv at the git root.
- `.worktrees/` holds parallel git worktrees (`git worktree list`) and is git-ignored at the root. A file can look missing simply because you are in a worktree that has not merged `origin/main`.
- `StubPolicyClient` (`src/claims/policy_client.py`) reads `data/policies.json`; `fail_with` fakes the three failure reasons. `PolicyNotFound` is 422 and `PolicyLookupFailed` is 5xx — collapsing them is a defect, not a simplification.
- `NotificationRepository` is in-memory; recorded claims vanish when uvicorn restarts.

**Refresh when** a module moves under `src/claims/`, a new **entry** appears, the contract's section 5/6 mapping changes, or the devcontainer/Dockerfile changes how the app is run.

## 1. Locate the root

The **root** is the directory the four files will live in.

- Prefer the git root of the project the user is actually working in (`git rev-parse --show-toplevel` from their cwd).
- Nested workspaces (a parent git repo that contains several apps): onboard the inner project they are in, not the holding folder. If cwd is the holding folder and two or more inner projects look equally like "the app", ask once which root to cache, then proceed.
- A monorepo that _is_ the app (packages that only make sense together): onboard that outer root and map the packages inside it.

Done when you can name one absolute path as the root and say why it won.

## 2. First visit or refresh

The branch is the four files themselves, as a set, at that root:

- `ARCHITECTURE.md`
- `ENTRYPOINTS.md`
- `CONFIG.md`
- `GOTCHAS.md`

If all four exist, this is a **refresh**. If any is missing, treat it as a first visit for the missing ones and a refresh for the rest — still write all four before you stop.

Done when you have chosen the branch and read every existing file in the set.

## 3. Explore

Hunt; do not inventory. Open README, manifests (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`), Docker/devcontainer, CI, env examples, the source tree's real **entry** modules, and a slice of tests.

For a large or multi-package repo, spawn parallel explore subagents and merge:

- runtime and **entry** (CLIs, HTTP, workers, jobs)
- config and infra (env, compose, secrets vs examples, override order)
- package/module graph (what talks to what)
- tests, CI, and comments that confess a **gotcha**

Use domain terms from `CONTEXT.md` when they exist. Cite every claim with a real path.

Done when you can fill every required section in the templates from evidence, not from a directory listing.

## 4. Write or patch

Write all four files at the root, in one pass, from the templates.

- Co-locate each claim with its path and the reason it matters.
- Keep each file short enough to re-read on a later visit. Sediment (a restated file tree, a pasted script list, a **gotcha** that is just "read the README") does not earn its keep.
- `ARCHITECTURE.md` carries a Mermaid graph of modules/packages and runtime flow. A file tree is not a map.
- `ENTRYPOINTS.md` names each **entry** and _why_ a later agent would start there.
- `CONFIG.md` records override order and what `.env.example` (or equivalent) does not confess. Point at the example file; cache the unwritten (which vars are actually required, which file wins).
- `GOTCHAS.md` is only landmines: unwritten convention, surprising coupling, local-vs-container traps, generated code, dual layouts.

**Refresh** (when the files already existed): patch in place. Spot-check every path and every graph edge against current code. Correct stale pointers. Add new **gotcha**s you can evidence. Prune sediment. Rewrite a file from scratch only when the map is structurally wrong — a package split, a new runtime, a deleted **entry**. A lie in the cache (a module that no longer exists) is removed, not appended-beside.

If `AGENTS.md` exists, one pointer line is enough, for example: `Onboarding cache: ARCHITECTURE.md, ENTRYPOINTS.md, CONFIG.md, GOTCHAS.md.`

Done when all four files exist at the root, every required template heading has substance, every cited path exists, and a named-but-missing module cannot be found in the map.

## 5. Brief

Tell the human the root path, that the four files are there, and the 3–5 facts that would have wasted the most time. Do not paste the files back into chat.

Done when the briefing names those facts and points at the files rather than restating them.
