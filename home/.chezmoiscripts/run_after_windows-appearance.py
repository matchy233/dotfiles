#!/usr/bin/env python3
"""Apply the shared Windows colors: dark mode, transparency and the accent color.

Wallpaper, cursors and sounds stay as this machine has them.

Run this file with --diff to preview the changes without writing.
"""

import argparse
import ctypes
import sys
import time

# The accent is #A67DF2. The other shades are the ones Windows derived from it, so
# to change the color, pick it in Settings and copy all five color values again.
PALETTE = bytes.fromhex(
    "E9D0F700 CDAFED00 9A77DA00 8761D300 613AC800 402A9800 18116600 88179800"
)
ACCENT_BGR = 0xFFF27DA6
START_BGR = 0xFFC83A61
COLORIZATION = 0xC4A67DF2

SETTINGS: dict[str, dict[str, int | bytes]] = {
    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize": {
        "AppsUseLightTheme": 0,
        "SystemUsesLightTheme": 0,
        "EnableTransparency": 1,
        # Accent on Start and the taskbar.
        "ColorPrevalence": 0,
    },
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent": {
        "AccentPalette": PALETTE,
        "StartColorMenu": START_BGR,
        "AccentColorMenu": ACCENT_BGR,
    },
    r"Software\Microsoft\Windows\DWM": {
        "AccentColor": ACCENT_BGR,
        "ColorizationColor": COLORIZATION,
        "ColorizationAfterglow": COLORIZATION,
        # Accent on title bars and window borders.
        "ColorPrevalence": 1,
        "EnableWindowColorization": 1,
    },
    # Keeps the wallpaper from choosing the accent color.
    r"Control Panel\Desktop": {"AutoColorization": 0},
}
# Tests point this at a scratch key.
PREFIX = ""
ATTEMPTS = 3
SETTLE_SECONDS = 1

Change = tuple[str, str, int | bytes | None, int | bytes]


def read(key: str, name: str) -> int | bytes | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PREFIX + key) as handle:
            return winreg.QueryValueEx(handle, name)[0]
    except FileNotFoundError:
        return None


def write(key: str, name: str, value: int | bytes) -> None:
    import winreg

    kind = winreg.REG_BINARY if isinstance(value, bytes) else winreg.REG_DWORD
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, PREFIX + key) as handle:
        winreg.SetValueEx(handle, name, 0, kind, value)


def pending() -> list[Change]:
    return [
        (key, name, current, wanted)
        for key, values in SETTINGS.items()
        for name, wanted in values.items()
        if (current := read(key, name)) != wanted
    ]


def announce() -> None:
    """Tell running programs to reload their colors."""
    broadcast, setting_change, abort_if_hung = 0xFFFF, 0x001A, 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        broadcast, setting_change, 0, "ImmersiveColorSet", abort_if_hung, 1000, None
    )


def describe(value: int | bytes | None) -> str:
    return value.hex() if isinstance(value, bytes) else str(value)


def preview(changes: list[Change]) -> None:
    for key, name, current, wanted in changes:
        print(f"{key}\\{name}: {describe(current)} -> {describe(wanted)}")
    if not changes:
        print("No changes needed.")


def apply() -> list[Change]:
    """Write the settings until they stick and return any that did not."""
    changes = pending()
    for _ in range(ATTEMPTS):
        if not changes:
            break
        for key, name, _, wanted in changes:
            write(key, name, wanted)
        announce()
        # Writing Explorer\Accent can make another program put the old colors back
        # in DWM, even without the broadcast.
        time.sleep(SETTLE_SECONDS)
        changes = pending()
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", action="store_true", help="preview changes")
    args = parser.parse_args()
    if sys.platform != "win32":
        return

    if args.diff:
        preview(pending())
        return
    for key, name, current, _ in apply():
        print(f"Windows kept {key}\\{name} at {describe(current)}.")


if __name__ == "__main__":
    main()
