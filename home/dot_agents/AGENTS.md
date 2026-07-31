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

## Worklogs (Code Repos)

Maintain a `worklogs/` directory at the repo root:

1. **Design docs** (`worklogs/design/`) — architecture decisions, component design, API contracts.
2. **Changelog** (`worklogs/changelog/`) — what changed and why, beyond `git log`.
3. **Plans** (`worklogs/plans/`) — execution-ready plans a subagent can run with.
4. **Agent operation logs** (`worklogs/<agent-identity>-YYYY-MM-DD.md`) — dated record of the session.

Operation logs must cover: purpose, key decisions and reasoning, branch/base or remote-sync corrections, abandoned approaches with reasons, and current local state.

Worklogs are local by default:

- Don't stage/commit `worklogs/` files unless the user explicitly asks for a specific one.
- Prefer gitignoring `worklogs/`; if a branch needs that `.gitignore` update, make it a separate atomic commit (droppable later via rebase).
- Summarize useful worklog content in the PR body instead of committing the files.
