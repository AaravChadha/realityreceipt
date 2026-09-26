# RealityReceipt

Agent instructions for this repo, for every tool (Claude Code, Cursor, Codex, or anything else). Project docs: `BRIEF.md` (frozen seed), `PLAN.md` (living plan), `JOURNAL.md` (rolling journal). Product rules come from `docs/RealityReceipt_Build_Spec.pdf`; the constraints at the top of `PLAN.md` bind every task.

## Team workflow (this repo, until Sun 2026-09-27 08:00 EDT)

Four people on four machines, each running several agent sessions. For this repo these rules replace any personal "one integrator merges everything" rule.

**The agent runs every command; the person only approves.** Nobody copies commands by hand. Before a command that creates a worktree, installs something, commits, pushes, opens a PR or merges, the agent says in one line what it will run and why, then waits for approval: the tool's permission prompt, or the person typing "go". Anything else from the person is not approval.

1. **GitHub `main` is the only integration point.** Work reaches it only through a pull request, squash-merged when the `ci` check passes. No review is required. Each person merges their own sessions' PRs. Never commit on `main` (a local hook refuses it), never force-push, never rewrite `main`.
2. **One session = one task = one branch = one worktree**, branched from fresh `origin/main`. The agent creates it as its first step and does all the task's work inside it:
   `git fetch origin` then `git worktree add --no-track -b feature/<task-id>-<slug> .claude/worktrees/<task-id> origin/main`
   (`--no-track` matters: without it git records the upstream in `.git/config`, which Claude Code's sandbox write-protects, and the command creates the branch but not the worktree.)
   then, inside it: `python3 -m venv api/.venv`, `api/.venv/bin/pip install -r api/requirements.txt`, `npm --prefix web ci`.
3. **Take a task by its ID from `PLAN.md`** and do only that task. Edit only the files your row owns in `PLAN.md` "File ownership". A change in another row's file is a request to that row's owner, not an edit.
4. **Done means the task's `**Acceptance:**` command passes**, run from the worktree root. Tick only that task's box in `PLAN.md`, in the same commit. Commit subject: `task <id>: <what>`. No AI attribution trailers.
5. **Land it (the agent, with approval):** `git push origin feature/<task-id>-<slug>`; `gh pr create --fill --head feature/<task-id>-<slug>` with the acceptance command and its output in the PR body; `gh pr merge --squash --auto`. It merges itself when CI passes. The agent reports the PR URL; if CI fails, it reads the failing check and fixes it on the same branch.
6. **Before building on another track's work, check it is on `origin/main`** (`git fetch origin` then `git log origin/main --oneline`). **Catching up or resolving a conflict:** if your PR shows a merge conflict, or you need work merged after you started, run `git fetch origin` then `git merge origin/main` inside your branch, resolve, rerun the Acceptance command, and push. Never rebase and never force-push: a rebased branch can only be pushed with force, and force-pushes are blocked. A PLAN.md conflict is almost always two ticked boxes: keep both ticks.
7. **Dependencies and contracts have one owner each.** A new package is a request to the operator (Track 0). A change to `api/app/models.py`, `contracts/` or `web/src/contracts.ts` goes through the A1 owner with a message to the whole team first.
8. **Secrets:** keys live only in `api/.env` (gitignored). Never paste a key into a committed file, a PR body or a log.

**First time on a machine** (the agent does it, with approval): install the no-commits-on-main hook from `PLAN.md` task 0.6, confirm `gh auth status` succeeds, and for Claude Code install acstack (`git clone https://github.com/AaravChadha/acstack.git ~/acstack`, then `~/acstack/setup`).

**Claude Code sessions:** set up the worktree (step 2), run `/do <task-id>` inside it for steps 3 and 4 (`/do` stops at the commit), then land it (step 5) on the person's approval. **Other agents (Cursor, Codex, ...)** get this prompt:

> Read AGENTS.md and PLAN.md. Do only task `<task-id>`. First create your own worktree and branch as AGENTS.md step 2 says, and do all work inside it. Edit only the files that task's row owns in PLAN.md "File ownership". Run the task's Acceptance command from the worktree root and show me the output; if it fails, fix the code, never weaken the test. When it passes, tick only that task's checkbox in PLAN.md, commit as `task <task-id>: <what>`, then land it as AGENTS.md step 5 says. Before every command that needs approval, tell me what you will run and wait for my OK or "go".

<!-- BEGIN:acstack-referrals -->
## Typed-only skills

These skills carry `disable-model-invocation: true`, which keeps them out
of the model's skill listing — so an agent will not reach for one on its
own, and the roster below exists because otherwise nobody would find them.

**That is a discoverability control, not an enforcement boundary.** A model
handed the name explicitly can still run it: a session told "type /plan
seed" invoked it end to end (observed 2026-08-04). The same honest scope as
`allowed-tools` — the flag governs what the model is *offered*, not what it
is *prevented* from doing. Treat these as user-initiated by convention, not
by mechanism.

Suggest one when its column-three condition is true, per conduct rule 9:
name it once, never repeat it, and treat silence or a pivot as a no.

| Skill | What it does | Suggest when |
|---|---|---|
| `/plan` | Frozen BRIEF → written architecture pushback → living PLAN.md with runnable exit criteria | The repo has no PLAN.md (or legacy equivalent) and the user is starting something new — **or** a build request lands in such a repo and the work is not a bounded single-file change (new files, new surface, or multi-file). Never for a one-line fix. Do the work first; make the offer with the end-of-increment status statement, naming concrete options and a recommendation ("spec first in docs/ / a short design sketch / keep building as-is — I'd suggest X because Y"), with one clause of reason: simple-looking work is where unexamined assumptions cost most. Once per session per repo; nothing is recorded, so a later session may ask once more. |
| `/eval-spec` | The eval is the spec: golden set with category minimums, refusal cases, pinned grader — written before the system exists | An LLM-shaped feature is heading into build and no `eval/` exists |
<!-- END:acstack-referrals -->

<!-- BEGIN:acstack-conduct -->
## Agent conduct

These rules bind every session in this repo. Full text: CONDUCT.md in the
acstack pack.

1. The word is the mode. "Explain" = complete explanation, then stop — no
   menus, no actions, no scaffolding in the same turn. "Plan" = design docs
   only. Build only on an explicit go.
2. The user sets the pace. An approved plan authorizes the what, not the
   when. End each increment with a status statement; do not roll into the
   next increment uninvited.
3. Answer what was asked before anything else. The answer is the
   deliverable; don't bury it.
4. Be direct. Push back in writing when the user is wrong. No sycophancy.
5. Don't ask permission for what was requested; don't do what wasn't.
   Before an act that cannot be undone, name it and confirm — even when
   it was requested.
6. Don't relitigate decided things. New evidence gets one plain sentence,
   then the user rules.
7. Surface conflicts between instructions, conventions, or config — never
   silently pick a side.
8. When unsure, ask before starting. Ambiguity is a reason to stop, not to
   guess-and-build.
9. Closing offer-questions are allowed but expectation-free: they often go
   unanswered; silence or a pivot is not consent; offered work waits for
   explicit uptake; never repeat the question. Referrals to typed-only
   skills (the `acstack-referrals` roster) are offers under this rule:
   name one once, never repeat it, and do the requested work first.
10. Commits: short subject starting with the work-item reference
    (`ticket #42: …` in tickets mode; `task 3.2.1: …` in document
    mode), a brief what-and-why body, and no attribution trailers — no
    Co-Authored-By bots, no "Generated with" footers (per the
    `attribution` config, default none).
<!-- END:acstack-conduct -->
