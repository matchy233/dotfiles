#!/usr/bin/env python3
"""Bind Shift+Enter to an LF in Windows Terminal for Claude Code.

Run this file with --diff to preview the settings changes without writing.
"""

import argparse
import difflib
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ACTION_ID = "User.claudeShiftEnterNewline"
KEYS = "shift+enter"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", action="store_true", help="preview changes")
    args = parser.parse_args()
    if sys.platform != "win32":
        return

    packages = Path(os.environ["LOCALAPPDATA"]) / "Packages"
    settings_paths = [
        package / "LocalState" / "settings.json"
        for package in packages.glob("Microsoft.WindowsTerminal_*")
        if package.is_dir()
    ]
    if not settings_paths:
        if args.diff:
            print("No Windows Terminal Stable package data found.")
        return
    if len(settings_paths) != 1:
        parser.exit(1, "Found multiple Windows Terminal Stable package directories.\n")

    path = settings_paths[0]
    try:
        content = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        content = ""
    settings = json.loads(content) if content.strip() else {}

    actions = [
        action
        for action in settings.get("actions", [])
        if action.get("id") != ACTION_ID
    ]
    actions.append({"id": ACTION_ID, "command": {"action": "sendInput", "input": "\n"}})
    keybindings = [
        binding
        for binding in settings.get("keybindings", [])
        if binding.get("id") != ACTION_ID and binding.get("keys") != KEYS
    ]
    keybindings.append({"id": ACTION_ID, "keys": KEYS})
    if actions == settings.get("actions") and keybindings == settings.get(
        "keybindings"
    ):
        if args.diff:
            print(f"No changes needed in {path}.")
        return

    settings.update(actions=actions, keybindings=keybindings)
    updated = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
    if args.diff:
        lines = difflib.unified_diff(
            content.splitlines(),
            updated.splitlines(),
            str(path),
            str(path),
            lineterm="",
        )
        print("\n".join(lines))
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary_path = Path(output.name)
        try:
            output.write(updated.encode("utf-8"))
            output.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
