# dotfiles

One [chezmoi](https://www.chezmoi.io/) source for ordinary dotfiles and shared
AI agent configuration. The repository manages `~/.agents` directly and links
Claude Code and Codex to the shared files they need.

## What Is Managed

- Shell files: `~/.zshrc`, `~/.condarc`, and `~/.dircolors`.
- Optional device-local shell overrides that remain outside Git.
- Shared agent instructions: `~/.agents/AGENTS.md`.
- Shared and custom skills: `~/.agents/skills/`.
- Claude Code settings and links below `~/.claude/`.
- Codex shared defaults, custom agent profiles, and links below `~/.codex/`.
- Windows PowerShell 5.1 and PowerShell 7 profiles that load shared settings.

Repository files such as this README and the setup scripts live outside the
`home/` source root, so chezmoi does not copy them into `$HOME`.

## New Machine

Install chezmoi, Git, Node.js, and `npx`, then initialize without applying:

```sh
chezmoi init git@github.com:matchy233/dotfiles.git
chezmoi diff
chezmoi apply --dry-run --verbose
```

On Windows, run the repository bootstrap from PowerShell after `chezmoi init`:

```powershell
$sourceDir = chezmoi source-path
& (Join-Path (Split-Path -Parent $sourceDir) "setup.ps1")
```

The script creates and removes a real symbolic link before previewing changes.
If that fails, enable Windows Developer Mode and rerun it. When a legacy
`~/.agents` Git checkout exists, the script shows `git status`, runs `git fsck`,
and asks before renaming it within `$HOME`. It never recursively moves the
checkout. If apply fails after the rename, rerunning the script validates and
reuses the existing backup.

Review the diff before applying. A normal apply also runs the skill installer,
which downloads the versions declared in `~/.agents/skills-lock.json`:

```sh
chezmoi apply
```

To apply files without running the installer:

```sh
chezmoi apply --exclude=scripts
```

Private Claude settings are intentionally absent. After the first apply,
create them from the managed example and add credentials locally:

```sh
cp ~/.agents/claude/cc-deepseek.settings.example.json \
  ~/.agents/claude/cc-deepseek.settings.json
chmod 600 ~/.agents/claude/cc-deepseek.settings.json
```

Do not add the private file to this repository.

The Windows bootstrap restores this file from a legacy agents backup when
available. Otherwise it copies the example and warns when the token is absent
or still set to `<your-deepseek-api-key>`; it never prints the token.

## Local Shell Overrides

Chezmoi replaces the synchronized shell entrypoints on apply. Put settings
that belong only to one device in files that are not managed by chezmoi:

```text
~/.zshrc.local
~/.config/powershell/local-profile.ps1
```

The managed entrypoints load these files last, so local aliases, environment
variables, and functions can override shared defaults. Before the first apply
on an existing device, move device-only settings out of `.zshrc` or a
PowerShell profile and into the corresponding local file.

Google Cloud settings are device-local. Configure them in
`~/.config/powershell/local-profile.ps1`, for example:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = `
    "$HOME\.config\google-cloud\vertexai-service-account.json"
$env:GOOGLE_CLOUD_PROJECT = "<your-google-cloud-project-id>"
```

On Windows, both profile entrypoints load the same managed fragment:

```text
~/.config/powershell/shared-profile.ps1
```

`Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1` targets Windows
PowerShell 5.1. `Documents/PowerShell/Microsoft.PowerShell_profile.ps1` targets
PowerShell 7.

## Daily Workflow

Edit source state, inspect the computed destination, then commit:

```sh
chezmoi cd
# edit files below home/
chezmoi diff
chezmoi apply --dry-run --verbose
git status
git add <paths>
git commit
git push
```

If a program changed a managed destination and that live version should win,
inspect it and capture only that target:

```sh
chezmoi diff ~/.zshrc
chezmoi re-add ~/.zshrc
```

On another device, pull without applying first:

```sh
chezmoi update --apply=false
chezmoi diff
chezmoi apply --dry-run --verbose
chezmoi apply
```

## Codex Configuration

Codex writes project trust into `~/.codex/config.toml`. Chezmoi therefore uses
a `modify_` template instead of replacing the whole file:

- Shared defaults live in `home/dot_agents/codex/config.shared.toml`.
- Device-local `[projects]` entries remain in `~/.codex/config.toml`.
- Shared config is merged over existing shared keys during apply.
- A test rejects any `[projects]` table added to the shared source.

Edit the shared file for settings that should follow every device. Let Codex
manage project trust locally; never copy those absolute paths into Git.

## Skills

Custom skills are ordinary source files under
`home/dot_agents/skills/<name>/`. Third-party skills are declared in
`home/dot_agents/skills-lock.json`.

When the lock changes, `run_onchange_after_90-install-agent-skills.py` runs:

```sh
npx --yes skills experimental_install
```

The script stages the install in a temporary directory, validates that every
declared skill exists, and then replaces only declared skill directories under
`~/.agents/skills`. Undeclared local skills are left in place.

To add a third-party skill, update a temporary copy with the CLI and move the
generated version 3 lock back into the source. This keeps the CLI-generated
`computedHash` instead of writing it manually. For example:

```sh
tmpdir="$(mktemp -d)"
cp home/dot_agents/skills-lock.json "$tmpdir/skills-lock.json"
(cd "$tmpdir" && npx --yes skills add matchy233/skills \
  --skill chezmoi --agent codex claude-code --copy -y)
cp "$tmpdir/skills-lock.json" home/dot_agents/skills-lock.json
```

Review the lock diff and run the tests before committing it.

## Layout

```text
.
|-- .chezmoiroot                  # selects home/ as source state
|-- README.md                     # repository documentation, not a target
|-- setup.sh
|-- setup.ps1
`-- home/
    |-- dot_agents/               # becomes ~/.agents
    |-- dot_claude/               # shared Claude Code links
    |-- dot_codex/                # shared Codex links and modify template
    |-- dot_zshrc
    |-- dot_condarc
    `-- dot_dircolors
```

The `skills` directory is deliberately not `exact_`; installers and local
tools may add entries without chezmoi scheduling their removal.

## Verification

Run the repository checks from the source directory:

```sh
python3 -m unittest discover -s tests -v
git diff --check
chezmoi managed
```

For a real-home change, also review `chezmoi diff` and
`chezmoi apply --dry-run --verbose` before applying.

## Rollback

Revert the relevant source commit, preview the resulting destination diff, and
apply it only after review:

```sh
chezmoi cd
git log --oneline
git revert <commit>
chezmoi diff
chezmoi apply --dry-run --verbose
```

During the initial migration from the archived `matchy233/agents` checkout,
keep a timestamped backup of the old `~/.agents` directory until Codex, Claude
Code, OpenCode, and Pi have all been checked.
