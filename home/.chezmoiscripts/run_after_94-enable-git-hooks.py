#!/usr/bin/env python3
"""Make this clone run the git hooks tracked in .githooks."""

import os
import subprocess


def main() -> None:
    source = os.environ.get("CHEZMOI_SOURCE_DIR")
    if source is None:
        return
    done = subprocess.run(
        ["git", "-C", source, "config", "--local", "core.hooksPath", ".githooks"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        print("git-hooks: not enabled:", done.stderr.strip())


if __name__ == "__main__":
    main()
