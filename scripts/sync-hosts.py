#!/usr/bin/env python3
"""Pull the dotfiles repo and apply it on every managed device, in parallel.

Run after pushing to main: `python scripts/sync-hosts.py`. The devices are the
entries marked `chezmoi` in the encrypted host list. Exits non-zero if any failed.
"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import subprocess
import sys

HOSTS_FILE = Path(__file__).parents[1] / "home/.encrypted/paseo-hosts.json.age"
TIMEOUT_SECONDS = 120
SSH_UNREACHABLE = 255

# scripts and externals download and install, which can hang a session nobody
# watches. --no-tty makes a conflicting local edit fail instead of prompt.
SYNC = (
    "chezmoi update --apply=false && "
    "chezmoi apply --no-tty --exclude=scripts,externals"
)
LINUX_PATH = 'export PATH="$HOME/.local/bin:$PATH"; '

Host = tuple[str, list[str]]


def command(entry: dict, device: tuple[str, str]) -> list[str]:
    linux = entry["os"] == "linux"
    script = LINUX_PATH + SYNC if linux else SYNC
    if (entry["machine"].lower(), entry["os"]) != device:
        destination = entry["connection"].partition("?")[0]
        options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
        return ["ssh", *options, destination, script]
    shell = ["bash", "-c"] if linux else ["pwsh", "-NoProfile", "-Command"]
    return [*shell, script]


def managed_hosts(entries: list[dict]) -> list[Host]:
    system = "windows" if sys.platform == "win32" else "linux"
    device = (socket.gethostname().lower(), system)
    return [
        (entry["label"], command(entry, device))
        for entry in entries
        if entry.get("chezmoi")
    ]


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=TIMEOUT_SECONDS,
    )


def sync(host: Host) -> tuple[str, str]:
    name, argv = host
    try:
        done = run(argv)
    except subprocess.TimeoutExpired:
        return name, f"timed out after {TIMEOUT_SECONDS}s"
    except FileNotFoundError as error:
        return name, f"cannot start: {error}"
    if done.returncode == 0:
        return name, "ok"
    unreachable = done.returncode == SSH_UNREACHABLE
    reason = "unreachable" if unreachable else f"exit {done.returncode}"
    return name, f"{reason}: {(done.stdout + done.stderr).strip()[-300:]}"


def main() -> int:
    listed = subprocess.run(
        ["chezmoi", "decrypt", str(HOSTS_FILE)], capture_output=True, text=True
    )
    if listed.returncode != 0:
        print(f"cannot decrypt the host list: {listed.stderr.strip()}")
        return 1
    hosts = managed_hosts(json.loads(listed.stdout)["paseoHosts"])
    if not hosts:
        print("no chezmoi-managed host in the host list")
        return 1
    with ThreadPoolExecutor(len(hosts)) as pool:
        results = list(pool.map(sync, hosts))
    for name, outcome in results:
        print(f"{name}: {outcome}")
    return 0 if all(outcome == "ok" for _, outcome in results) else 1


if __name__ == "__main__":
    sys.exit(main())
