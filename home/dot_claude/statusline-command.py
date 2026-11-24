#!/usr/bin/env python3
# Claude Code status line in the style of the Codex TUI footer: one line, segments
# joined by a U+2022 bullet, each segment in its own soft color:
#
#   <model> | <cwd> | 5h N% left | weekly N% left | Context N% used
#
# Claude Code pipes a JSON document on stdin. Fields read (all optional):
#   model.display_name                       fallback: model.id
#   workspace.current_dir                    fallback: cwd; $HOME becomes ~; a path longer than
#                                            40 characters is shortened, see shorten_path()
#   rate_limits.five_hour.used_percentage    "5h N% left"; resets_at adds "(resets HH:MM)"
#   rate_limits.seven_day.used_percentage    "weekly N% left"; same for resets_at
#   context_window.used_percentage           "Context N% used"; fallbacks, in order:
#       100 - remaining_percentage, then (current_usage input + cache creation +
#       cache read tokens, else total_input_tokens) / context_window_size
#
# "left" is 100 minus the used percentage. A segment whose data is missing or null
# is left out. Every segment is built inside its own try/except, so unexpected JSON
# cannot make the script fail: it prints whatever segments it can build.
import datetime
import json
import math
import os
import sys
import time

# 256-color foregrounds: soft mid-tone colors that read on dark and light
# backgrounds (Claude Code dims the status line further).
C_MODEL = 140     # soft purple
C_CWD = 68        # soft blue, close to the #3a96dd used for the directory in starship
C_FIVE_HOUR = 73  # soft teal
C_WEEKLY = 114    # soft green
C_CONTEXT = 179   # soft amber
C_MUTED = 245     # gray: separators, reset hints, shortened path prefix

BULLET = "•"


def paint(text, code):
    # Close with "default foreground" (39) instead of "reset all" (0) so an outer
    # style such as dim stays in effect.
    return "\033[38;5;" + str(code) + "m" + text + "\033[39m"


def clean(value):
    # Only strings are accepted. Control characters are dropped so that a path or
    # name from the environment cannot inject terminal escape sequences.
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch.isprintable()).strip()


def pick(mapping, *keys):
    # First non-null value among several candidate key names.
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def number(value):
    # A finite float, or None for null, booleans, non-numbers, NaN and infinity.
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def whole_percent(x):
    # Clamp to 0..100 and round half up.
    return int(min(max(x, 0.0), 100.0) + 0.5)


def epoch_seconds(value):
    # Epoch seconds (or milliseconds, or an ISO 8601 string) -> epoch seconds.
    x = number(value)
    if x is not None:
        return x / 1000.0 if x > 1e11 else x
    if isinstance(value, str):
        text = value.strip()
        if text[-1:] in ("Z", "z"):
            text = text[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(text).timestamp()
    return None


def reset_hint(value):
    # "14:05" if the reset is today, otherwise "Thu 14:05" (local time). None if
    # the value is missing, unparsable or already in the past.
    try:
        ts = epoch_seconds(value)
        if ts is None or ts <= time.time():
            return None
        when = datetime.datetime.fromtimestamp(ts)
        if when.date() == datetime.date.today():
            return when.strftime("%H:%M")
        return when.strftime("%a %H:%M")
    except Exception:
        return None


def segment_model(data):
    model = data.get("model")
    if isinstance(model, dict):
        name = clean(model.get("display_name")) or clean(model.get("id"))
    else:
        name = clean(model)
    return paint(name, C_MODEL) if name else None


# A cwd longer than this many characters (after $HOME became ~) gets shortened.
MAX_PATH = 40


def shorten_path(path):
    # powerlevel10k style, for a path longer than MAX_PATH characters: keep the last
    # two components in full and cut every earlier one to its first character (a
    # leading dot stays, so ".config" becomes ".c"). A leading "~" or "/" is kept.
    # Returns (prefix, tail): the shortened part including its slashes, and the last
    # two components. A path of MAX_PATH characters or fewer comes back as ("", path).
    if len(path) <= MAX_PATH:
        return "", path
    if path.startswith("~/"):
        anchor, rest = "~/", path[2:]
    elif path.startswith("/"):
        anchor, rest = "/", path[1:]
    else:
        anchor, rest = "", path
    names = [name for name in rest.split("/") if name]
    if not names:
        return "", path
    short = [name[:2] if name.startswith(".") else name[:1] for name in names[:-2]]
    return anchor + "".join(part + "/" for part in short), "/".join(names[-2:])


def segment_cwd(data):
    workspace = data.get("workspace")
    cwd = clean(workspace.get("current_dir")) if isinstance(workspace, dict) else ""
    cwd = cwd or clean(data.get("cwd"))
    if not cwd:
        return None
    home = os.path.expanduser("~")
    if home not in ("", "/", "~"):
        if cwd == home:
            cwd = "~"
        elif cwd.startswith(home + "/"):
            cwd = "~" + cwd[len(home):]
    prefix, tail = shorten_path(cwd)
    if prefix:
        return paint(prefix, C_MUTED) + paint(tail, C_CWD)
    return paint(tail, C_CWD)


def segment_limit(data, window_key, label, color):
    limits = data.get("rate_limits")
    window = limits.get(window_key) if isinstance(limits, dict) else None
    used = number(pick(window, "used_percentage", "utilization"))
    if used is None:
        return None
    text = paint("%s %d%% left" % (label, whole_percent(100.0 - used)), color)
    hint = reset_hint(pick(window, "resets_at", "reset_at", "resetsAt"))
    if hint:
        text += " " + paint("(resets " + hint + ")", C_MUTED)
    return text


def context_used(window):
    used = number(pick(window, "used_percentage"))
    if used is not None:
        return used
    remaining = number(pick(window, "remaining_percentage"))
    if remaining is not None:
        return 100.0 - remaining
    size = number(pick(window, "context_window_size"))
    if size is None or size <= 0:
        return None
    tokens = None
    usage = pick(window, "current_usage")
    if isinstance(usage, dict):
        parts = [number(usage.get(key)) for key in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")]
        parts = [p for p in parts if p is not None]
        if parts:
            tokens = sum(parts)
    if tokens is None:
        tokens = number(pick(window, "total_input_tokens"))
    if tokens is None:
        return None
    return tokens / size * 100.0


def segment_context(data):
    used = context_used(data.get("context_window"))
    if used is None:
        return None
    return paint("Context %d%% used" % whole_percent(used), C_CONTEXT)


def read_input():
    try:
        data = json.loads(sys.stdin.buffer.read() or b"{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def render(data):
    builders = (
        segment_model,
        segment_cwd,
        lambda d: segment_limit(d, "five_hour", "5h", C_FIVE_HOUR),
        lambda d: segment_limit(d, "seven_day", "weekly", C_WEEKLY),
        segment_context,
    )
    parts = []
    for build in builders:
        try:
            part = build(data)
        except Exception:
            part = None
        if part:
            parts.append(part)
    return (" " + paint(BULLET, C_MUTED) + " ").join(parts)


def main():
    try:
        line = render(read_input())
        if line:
            sys.stdout.buffer.write((line + "\n").encode("utf-8", "replace"))
            sys.stdout.buffer.flush()
    except Exception:
        pass


if __name__ == "__main__":
    main()
