# Global Agent Instructions

## Language & Wording (Chinese replies)

- **Banned words:** 守 / 守护 / 防线 ("guard/defend" metaphors), 高杠杆 / 杠杆 ("leverage" framing), 根因 (say "真正的原因" instead), 一句话 (just state the point, don't announce it).
- Avoid jargon, buzzwords, and business-speak — write plainly.
- Keep technical terms in English (`import`, lazy initialization, etc.); explain them in plain Chinese around the term.
- Skip forced analogies/metaphors when a direct explanation works better.


## Git Workflow

- Check for a git repo at session start. If missing, ask before `git init` — unless the user says git isn't needed.
- Commit atomically: one logical change per commit, immediately after it's done.
- Never add `Co-Authored-By` or other AI attribution lines.
- Match `git log`'s existing style. No history yet? Use **Conventional Commits**:
    ```
    feat: add user authentication module
    fix: correct off-by-one in pagination logic
    docs: update API usage examples
    refactor: extract validation into shared utility
    test: add unit tests for order calculation
    chore: configure eslint and prettier
    ```

## Scripting

- Prefer Python over bash / PowerShell for scripts — avoids symbol-escaping issues (quotes, `$`, backticks).
- Use bash / PowerShell only for trivial one-liners or shell-specific needs (pipelines, native CLI calls).

## Code-Quality Tools (ub-mode companions)

- `crapper`, `dryer` and `mutator` are not part of the `ub-mode` skill install; chezmoi checks them out as git-repo externals at `~/.agents/tools/unclebob/<tool>/`.
- Run `~/.agents/tools/unclebob/<tool>/<tool>` from a project root (Linux/macOS); on Windows run `~/.agents/tools/unclebob/<tool>/.venv/Scripts/python -m <tool>`. A chezmoi script builds each tool's `.venv` with uv (and installs uv if missing). `mutator` expects `crapper` next to it, which this layout provides.

## Brain (Code Repos)

Each repo keeps a `brain/` directory at its root: project memory plus work records, shared by every agent.

- `brain/index.md` — entry point: relative markdown links (`[title](notes/x.md)`) to every note, design doc, plan and changelog, plus the `logs/` folder and other artifact folders. No inlined content.
- `brain/notes/` — durable project knowledge: gotchas, decisions the user stated, tool quirks. One topic per file, lowercase-hyphenated name, under ~50 lines.
- `brain/design/` — architecture decisions, component design, API contracts.
- `brain/changelog/` — what changed and why, beyond `git log`.
- `brain/plans/` — execution-ready plans a subagent can run with.
- `brain/logs/<agent-identity>-YYYY-MM-DD.md` — operation logs: purpose, key decisions and reasoning, branch/base or remote-sync corrections, abandoned approaches with reasons, current local state.

Reading:

- At session start in a repo, read `brain/index.md` if it exists, then the notes relevant to the task.
- In a git worktree, `brain/` lives in the main checkout: the parent of `git rev-parse --path-format=absolute --git-common-dir`.
- `worklogs` next to `brain/` is a symlink kept for old path references; write through `brain/`. A repo with a real `worklogs/` directory and no `brain/` hasn't been migrated: use `worklogs/` the same way and don't rename it unless the user asks (scheduled tasks may reference its paths).

Writing:

- After a correction or a stated decision that would matter in a different task, add or update a note in `brain/notes/` and its index line. Merge into an existing note before creating a new one; delete notes that turn out wrong.
- If a lesson can be enforced by a lint rule, hook, script, or permission setting, propose that instead of a note.
- Preferences that apply to every project belong in this global file, not a repo brain: propose the edit to the user instead of writing it into the repo.

The brain is local by default:

- Don't stage/commit `brain/` files unless the user explicitly asks for a specific one.
- `/brain/` and `/worklogs` are ignored by the global git ignore (`~/.config/git/ignore`, managed by chezmoi), so repos don't need a `.gitignore` entry.
- Summarize useful brain content in the PR body instead of committing the files.
