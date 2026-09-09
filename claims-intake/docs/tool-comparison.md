# Tool comparison: one agent vs agents in worktrees

Day 4 was four files: routes, HTTP tests, Dockerfile, README. I did not give that to one agent in one folder. I made four git worktrees and started a Cursor agent in each, with a prompt that named one file and forbade the rest.

That is the comparison: Cursor agents in worktrees vs my usual habit of one chat on `main`.

## Worktrees and one agent per slice

**Easy.** Each agent only saw its file. The routes agent could not “finish” the tests. The test agent could not rewrite `routes.py` when a mapping looked wrong. Docker and README did not wait on HTTP. I could merge (or PR) A without opening C. The prompt “touch only `routes.py` / `test_routes.py` / `Dockerfile` / `README.md`” actually held because the other files lived in other directories.

**Awkward.** The trees do not update themselves. After routes landed, the test tree still had the stub app until I fetched and merged `origin/main`. Running pytest from the worktree root used the wrong `routes.py` and everything was 404. GitHub also does not care that you have four folders: merge to `main` with no PR, then you have nothing to open. The agents will not fix that. You are the integration step.

**Use it** when the work splits on files that must not overlap, and you want four small PRs instead of one mixed commit.

## Which I would pick

For Day 4 I would use worktrees again. One agent on `main` would have mixed A–D and I would not have had four PRs.

I would not use four worktrees for a one-line bugfix. The merge/pull cost is only worth it when the files must stay owned by different prompts.
