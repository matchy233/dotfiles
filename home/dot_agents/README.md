# agents

Dotfiles and shared configuration for AI coding agents (Claude Code, Codex, etc.).

## Setup

```bash
git clone git@github.com:matchy233/agents.git ~/.agents
cd ~/.agents

# Symlink configs into ~/.claude and ~/.codex
python init-config.py

# Install skills from lock file
python install-skills.py
# or: npx skills experimental_install

# Copy and fill in API keys
cp claude/cc-deepseek.settings.example.json claude/cc-deepseek.settings.json
```

On Windows, enable Developer Mode for symlinks or run as admin.

## Structure

```
.
├── AGENTS.md              # Shared agent instructions (→ ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md)
├── claude/
│   ├── settings.json      # Claude Code global settings (→ ~/.claude/settings.json)
│   └── cc-deepseek.settings.example.json
├── codex/
│   └── config.toml        # Codex CLI config (→ ~/.codex/config.toml)
├── my-skills/             # Custom skills, linked into ~/.claude/skills/
├── skills/                # Skills installed via npx skills (gitignored)
├── .skill-lock.json       # Skill lock file for reproducible installs
├── init-config.py         # Symlink setup script
└── install-skills.py      # Reinstall skills from lock file
```

## Adding a custom skill

Create a directory under `my-skills/` with a `SKILL.md`, then re-run `python init-config.py` to link it.
