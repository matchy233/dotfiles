"""Claude Code PreToolUse hook: fetch x.com / twitter.com links through fxtwitter.

x.com answers automated fetches with HTTP 402. The user approved the
api.fxtwitter.com mirror, which returns JSON including long-form text.
"""

import json
import sys
from urllib.parse import urlsplit

TWITTER_HOSTS = {"x.com", "twitter.com"}
HOST_PREFIXES = ("www.", "mobile.")
MIRROR = "https://api.fxtwitter.com"


def mirror_url(url: str) -> str | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    for prefix in HOST_PREFIXES:
        host = host.removeprefix(prefix)
    if host not in TWITTER_HOSTS:
        return None
    return MIRROR + parts.path


def hook_output(tool_input: dict) -> dict | None:
    new_url = mirror_url(tool_input.get("url", ""))
    if new_url is None:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "x.com blocks fetches; using the user-approved fxtwitter mirror",
            "updatedInput": {**tool_input, "url": new_url},
        }
    }


def main() -> None:
    event = json.load(sys.stdin)
    output = hook_output(event.get("tool_input", {}))
    if output is not None:
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
