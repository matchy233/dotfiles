# Shared agent configuration

This directory is generated from
[`matchy233/dotfiles`](https://github.com/matchy233/dotfiles) by chezmoi. It is
not a separate Git checkout.

- `AGENTS.md` contains instructions shared by compatible agent CLIs.
- `codex/config.shared.toml` contains only cross-device Codex defaults.
- `codex/agents/` contains custom Codex agent profiles.
- `claude/` contains shared Claude Code settings and a credential-free example.
- `skills/` contains custom and installed skills shared by multiple CLIs.
- `skills-lock.json` declares reproducible third-party skill versions.

Edit the chezmoi source rather than files in this generated directory:

```sh
chezmoi cd
chezmoi diff
```

Codex project trust remains device-local in `~/.codex/config.toml`. Private
Claude credentials belong in `~/.agents/claude/cc-deepseek.settings.json`,
which chezmoi does not manage.
