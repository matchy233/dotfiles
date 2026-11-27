#!/usr/bin/env python3
"""Install the shared fonts for the current Windows user.

Reads the font list (.chezmoidata/fonts.yaml) as JSON on stdin. A font that is
already installed is never replaced.
"""

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

ARCHIVE_SUFFIXES = (".7z", ".zip")
REGISTRY_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
# ALL APPLICATION PACKAGES and ALL RESTRICTED APPLICATION PACKAGES.
PACKAGED_APP_SIDS = ("*S-1-15-2-1", "*S-1-15-2-2")


def missing_files(font: dict, present: set[str]) -> list[str]:
    if any(name.lower() in present for name in font.get("satisfied_by", [])):
        return []
    return [name for name in font["files"] if name.lower() not in present]


def download(url: str, sha256: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "font-installer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    with destination.open("rb") as downloaded:
        actual = hashlib.file_digest(downloaded, "sha256").hexdigest()
    if actual != sha256:
        raise ValueError(f"sha256 mismatch for {url}: got {actual}")


def fetch(font: dict, names: list[str], workdir: Path) -> dict[str, Path]:
    suffix = Path(urlsplit(font["url"]).path).suffix.lower()
    payload = workdir / f"download{suffix}"
    download(font["url"], font["sha256"], payload)
    if suffix not in ARCHIVE_SUFFIXES:
        return {names[0]: payload}

    extracted = workdir / "extracted"
    extracted.mkdir()
    # Windows' bsdtar reads 7z and zip; a GNU tar earlier on PATH reads neither.
    tar = Path(os.environ["SystemRoot"]) / "System32/tar.exe"
    subprocess.run([tar, "-xf", payload, "-C", extracted], check=True)
    found = {path.name: path for path in extracted.rglob("*") if path.is_file()}
    return {name: found[name] for name in names}


def place(source: Path, destination: Path, register: Callable[[Path], None]) -> None:
    staging = destination.with_name(destination.name + ".partial")
    shutil.copyfile(source, staging)
    # The file gets its final name last: a run cut off earlier is redone in full,
    # because only the final name counts as installed.
    register(destination)
    staging.replace(destination)


def install(
    fonts: list[dict],
    user_dir: Path,
    system_dir: Path,
    register: Callable[[Path], None],
) -> list[str]:
    present = {
        path.name.lower()
        for directory in (user_dir, system_dir)
        if directory.is_dir()
        for path in directory.iterdir()
    }
    installed = []
    for font in fonts:
        names = missing_files(font, present)
        if not names:
            continue
        print(f"Downloading {font['url']}", flush=True)
        user_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as workdir:
            for name, source in fetch(font, names, Path(workdir)).items():
                place(source, user_dir / name, register)
                installed.append(name)
    return installed


def register_for_user(path: Path) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
        value = f"{path.stem} (TrueType)"
        winreg.SetValueEx(key, value, 0, winreg.REG_SZ, str(path))


def allow_packaged_apps(font_dir: Path) -> None:
    """Let Store apps such as Windows Terminal read per-user fonts."""
    font_dir.mkdir(parents=True, exist_ok=True)
    grants = [f"{sid}:(OI)(CI)(RX)" for sid in PACKAGED_APP_SIDS]
    subprocess.run(
        ["icacls", font_dir, "/grant", *grants],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def activate(paths: list[Path]) -> None:
    """Make new fonts usable without signing out."""
    for path in paths:
        ctypes.windll.gdi32.AddFontResourceW(str(path))
    broadcast, font_change, abort_if_hung = 0xFFFF, 0x001D, 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        broadcast, font_change, 0, 0, abort_if_hung, 1000, None
    )


def main() -> None:
    fonts = json.load(sys.stdin)
    user_dir = Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Windows/Fonts"
    system_dir = Path(os.environ["SystemRoot"]) / "Fonts"
    allow_packaged_apps(user_dir)
    installed = install(fonts, user_dir, system_dir, register_for_user)
    if installed:
        activate([user_dir / name for name in installed])
    print(f"Fonts installed: {len(installed)}")


if __name__ == "__main__":
    main()
