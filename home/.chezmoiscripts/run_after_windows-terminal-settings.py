#!/usr/bin/env python3
"""Apply the shared Windows Terminal settings.

Covers the color scheme, font, opacity, bell sound and a Shift+Enter binding that
sends an LF for Claude Code. Everything else stays as this machine has it.

Run this file with --diff to preview the settings changes without writing.
"""

import argparse
import copy
import difflib
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ACTION_ID = "User.claudeShiftEnterNewline"
KEYS = "shift+enter"
# Installed by .chezmoidata/fonts.yaml.
FONT_FACE = "Xiaolai Mono Nerd Font"
BELL_SOUND = Path.home() / ".local/share/sounds/Iota +4.5 dB.wav"
LOOK = {"opacity": 70, "useAcrylic": True}
# Termius' "Diwali", defined here so machines without Termius have it too.
SCHEME = {
    "name": "Diwali",
    "background": "#311652",
    "foreground": "#fdf6f6",
    "cursorColor": "#ffa900",
    "selectionBackground": "#986029",
    "black": "#1e0b34",
    "red": "#ad0656",
    "green": "#00b45d",
    "yellow": "#f8d203",
    "blue": "#4548e1",
    "purple": "#e869ea",
    "cyan": "#00d5dd",
    "white": "#fdf6f6",
    "brightBlack": "#cbb3e6",
    "brightRed": "#f02889",
    "brightGreen": "#35ef96",
    "brightYellow": "#ffe769",
    "brightBlue": "#7578ff",
    "brightPurple": "#fc99ff",
    "brightCyan": "#47eef4",
    "brightWhite": "#f8efff",
}


def bind_shift_enter(settings: dict) -> None:
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
    settings.update(actions=actions, keybindings=keybindings)


def drop_overrides(profile: dict, keys: list[str]) -> None:
    for key in keys:
        profile.pop(key, None)
    font = profile.get("font", {})
    font.pop("face", None)
    if not font:
        profile.pop("font", None)


def apply_look(profiles: dict, sound: Path | None) -> None:
    shared = dict(LOOK)
    if sound:
        shared.update(bellStyle="audible", bellSound=[str(sound)])
    defaults = profiles.setdefault("defaults", {})
    defaults.update(shared, colorScheme=SCHEME["name"])
    defaults["font"] = {**defaults.get("font", {}), "face": FONT_FACE}
    for profile in profiles.get("list", []):
        drop_overrides(profile, list(shared))
        # profiles.defaults outranks the scheme WSL ships for Ubuntu, so name it here.
        is_wsl = profile.get("source") == "Microsoft.WSL"
        if is_wsl and profile.get("name", "").startswith("Ubuntu"):
            profile.setdefault("colorScheme", "Ubuntu")


def merge(settings: dict, sound: Path | None) -> dict:
    """Return the settings with the shared values; sound=None keeps the local bell."""
    result = copy.deepcopy(settings)
    bind_shift_enter(result)
    others = [s for s in result.get("schemes", []) if s.get("name") != SCHEME["name"]]
    result["schemes"] = [*others, SCHEME]
    apply_look(result.setdefault("profiles", {}), sound)
    return result


def find_settings() -> Path | None:
    packages = Path(os.environ["LOCALAPPDATA"]) / "Packages"
    found = [
        package / "LocalState" / "settings.json"
        for package in packages.glob("Microsoft.WindowsTerminal_*")
        if package.is_dir()
    ]
    if len(found) > 1:
        sys.exit("Found multiple Windows Terminal Stable package directories.")
    return found[0] if found else None


def preview(path: Path, content: str, updated: str) -> None:
    lines = difflib.unified_diff(
        content.splitlines(),
        updated.splitlines(),
        str(path),
        str(path),
        lineterm="",
    )
    print("\n".join(lines))


def replace_file(path: Path, content: str) -> None:
    path.parent.mkdir(exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary_path = Path(output.name)
        try:
            output.write(content.encode("utf-8"))
            output.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def update(path: Path, diff: bool) -> None:
    content = path.read_bytes().decode("utf-8-sig") if path.exists() else ""
    settings = json.loads(content) if content.strip() else {}
    merged = merge(settings, BELL_SOUND if BELL_SOUND.is_file() else None)
    if merged == settings:
        if diff:
            print(f"No changes needed in {path}.")
        return

    updated = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    if diff:
        preview(path, content, updated)
    else:
        replace_file(path, updated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", action="store_true", help="preview changes")
    args = parser.parse_args()
    if sys.platform != "win32":
        return

    path = find_settings()
    if path:
        update(path, args.diff)
    elif args.diff:
        print("No Windows Terminal Stable package data found.")


if __name__ == "__main__":
    main()
