"""Refuse a push that would publish a device name, ssh login or tailnet address.

The names come from the encrypted host list and ~/.ssh, so none are written here.
git passes the remote name as the first argument and one
`<local ref> <local sha> <remote ref> <remote sha>` line per ref on stdin.
"""

import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from typing import TextIO

HOSTS_FILE = "home/.encrypted/paseo-hosts.json.age"
SSH_FILES = ("config", "config.local", "config.wsl")
PUBLIC_HOSTS = {"127.0.0.1", "localhost", "github.com"}
# 100.64.0.0/24 is left for made-up addresses in tests.
TAILNET = re.compile(
    r"\b100\.(?!64\.0\.)(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b"
)
CONNECTION = re.compile(r"ssh://(?:(?P<user>[^@/]+)@)?(?P<host>[^:/?]+)")
ARMOR = re.compile(r"-----(BEGIN|END) AGE ENCRYPTED FILE-----|[A-Za-z0-9+/]+={0,2}")

Terms = tuple[set[str], set[str]]


def run(*args: str) -> str:
    return subprocess.run(
        list(args),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=120,
    ).stdout


def host_list_terms(data: dict) -> Terms:
    names, users = set(data.get("privateNames", [])), set()
    for host in data["paseoHosts"]:
        names.update([host["label"], *host.get("formerLabels", [])])
        names.update(filter(None, [host.get("machine")]))
        found = CONNECTION.match(host["connection"])
        if found:
            names.add(found["host"])
            users.update(filter(None, [found["user"]]))
    return names, users


def ssh_config_terms(text: str) -> Terms:
    names, users = set(), set()
    for line in text.splitlines():
        words = line.replace("=", " ").split()
        if not words:
            continue
        key, values = words[0].lower(), words[1:]
        if key in ("host", "hostname"):
            names.update(value for value in values if not set("*?!%") & set(value))
        elif key == "user":
            users.update(values)
    return names, users


def private_terms(root: Path) -> Terms:
    listed = json.loads(run("chezmoi", "decrypt", str(root / HOSTS_FILE)))
    names, users = host_list_terms(listed)
    for name in SSH_FILES:
        path = Path.home() / ".ssh" / name
        if path.exists():
            more_names, more_users = ssh_config_terms(path.read_text(encoding="utf-8"))
            names |= more_names
            users |= more_users
    names.add(socket.gethostname())
    return names - PUBLIC_HOSTS, users


def whole(term: str) -> str:
    return rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"


def patterns(terms: Terms, author: str) -> list[re.Pattern[str]]:
    names, users = terms
    found = [TAILNET]
    found += [re.compile(whole(name), re.IGNORECASE) for name in sorted(names)]
    for user in sorted(users):
        login = re.escape(user)
        pattern = rf"(?<![\w.-]){login}@|\bUser[ \t]+{login}\b"
        # A login that begins the public author name cannot be hidden on its own.
        if not author.lower().startswith(user.lower()):
            pattern += "|" + whole(user)
        found.append(re.compile(pattern))
    return found


def added_lines(commit: str) -> list[tuple[str, str]]:
    """Return (path, line) for every line the commit adds."""
    patch = run(
        "git",
        "show",
        "--format=",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        "--diff-merges=first-parent",
        commit,
    )
    lines, path, in_hunk = [], "", False
    for line in patch.split("\n"):
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif not in_hunk and line.startswith("+++ "):
            path = line[4:].removeprefix("b/").rstrip("\t")
        elif in_hunk and line.startswith("+"):
            lines.append((path, line[1:]))
    return lines


def published_text(commit: str) -> list[tuple[str, str]]:
    """Return (place, text) for everything the commit would make public."""
    message = run("git", "log", "-1", "--format=%B", commit)
    paths = run("git", "show", "--format=", "--name-only", commit).splitlines()
    content = [
        (path, line)
        for path, line in added_lines(commit)
        if not (path.endswith(".age") and ARMOR.fullmatch(line))
    ]
    return [
        ("commit message", message),
        *(("file name", path) for path in paths),
        *content,
    ]


def findings(commit: str, wanted: list[re.Pattern[str]]) -> list[str]:
    short = run("git", "rev-parse", "--short", commit).strip()
    return sorted(
        {
            f"{short} {place}: {match.group()}"
            for place, text in published_text(commit)
            for pattern in wanted
            for match in pattern.finditer(text)
        }
    )


def outgoing(remote: str, updates: TextIO) -> list[str]:
    commits: list[str] = []
    for update in updates:
        local = update.split()[1]
        if set(local) != {"0"}:
            listed = run("git", "rev-list", local, "--not", f"--remotes={remote}")
            commits += listed.split()
    return list(dict.fromkeys(commits))


def main(argv: list[str], updates: TextIO) -> int:
    commits = outgoing(argv[0], updates)
    if not commits:
        return 0
    try:
        root = Path(run("git", "rev-parse", "--show-toplevel").strip())
        terms = private_terms(root)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        detail = getattr(error, "stderr", None) or error
        print(f"pre-push: cannot read the private names, refusing to push: {detail}")
        return 1
    wanted = patterns(terms, run("git", "config", "user.name").strip())
    problems = [line for commit in commits for line in findings(commit, wanted)]
    for line in problems:
        print(f"pre-push: {line}")
    if problems:
        print("pre-push: this repository is public; remove these and push again.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin))
