#!/usr/bin/env python3

import json
from pathlib import Path
import shutil
import subprocess


def is_this_device(host, device):
    return bool(host.get("tailnet")) and (host["machine"].lower(), host["os"]) == device


def wanted_hosts(data):
    device = (data["chezmoi"]["hostname"].lower(), data["chezmoi"]["os"])
    hosts = data["paseoHosts"]
    in_tailnet = any(is_this_device(host, device) for host in hosts)
    return [
        host
        for host in hosts
        if not is_this_device(host, device) and (in_tailnet or not host.get("tailnet"))
    ]


def find_registered(host, registered):
    for label in [host["label"], *host.get("formerLabels", [])]:
        for entry in registered:
            if entry["label"] == label:
                return entry
    return None


def with_connections(listing, stored):
    connections = {entry["registrationId"]: entry.get("connection") for entry in stored}
    return [{**entry, "connection": connections.get(entry["registrationId"])} for entry in listing]


def plan(wanted, registered):
    actions = []
    for host in wanted:
        label, connection = host["label"], host["connection"]
        entry = find_registered(host, registered)
        if entry is None:
            actions.append(("add", label, connection))
        elif (entry["label"], entry.get("connection")) != (label, connection):
            actions.append(("update", entry["registrationId"], label, connection))
    return actions


def apply(actions, run):
    for action in actions:
        if action[0] == "add":
            _, label, connection = action
            code, output = run("host", "add", connection, "--label", label)
        else:
            _, registration_id, label, connection = action
            code, output = run(
                "host", "update", registration_id, "--label", label, "--connection", connection
            )
        verb = "ok" if code == 0 else "failed"
        print(f"paseo-hosts: {action[0]} {label}: {verb}", output.strip() if code else "")


def main():
    exe = shutil.which("paseo")
    if exe is None:
        print("paseo-hosts: paseo CLI not found, skipping")
        return

    def run(*args):
        done = subprocess.run([exe, *args], capture_output=True, text=True, timeout=120)
        return done.returncode, done.stderr

    chezmoi = subprocess.run(
        ["chezmoi", "data", "--format", "json"], capture_output=True, text=True, check=True
    )
    listing = subprocess.run([exe, "host", "ls", "--json"], capture_output=True, text=True)
    if listing.returncode != 0:
        print("paseo-hosts: daemon not reachable, skipping:", listing.stderr.strip())
        return
    # `paseo host ls` omits the connection string, so read it from the daemon home's hosts.json.
    stored_file = Path.home() / ".paseo" / "hosts.json"
    stored = json.loads(stored_file.read_text(encoding="utf-8")) if stored_file.exists() else []
    registered = with_connections(json.loads(listing.stdout), stored)
    apply(plan(wanted_hosts(json.loads(chezmoi.stdout)), registered), run)


if __name__ == "__main__":
    main()
