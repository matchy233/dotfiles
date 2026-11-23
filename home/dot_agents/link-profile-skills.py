#!/usr/bin/env python3
"""Link shared skills into Claude Code profiles that use a custom config dir.

Claude Code reads skills from ``$CLAUDE_CONFIG_DIR/skills``. The default
profile links that whole directory to ``~/.agents/skills``. Extra profiles
cannot do the same, because each profile's claude.ai sync writes its own
``skills/synced`` directory there. Each shared skill gets its own link instead.
"""

import os
from pathlib import Path
from typing import Callable, Iterable, List, Set

PROFILE_DIRS = (".claude.tesla",)
# Written by Claude Code's account sync; never shared between profiles.
PROFILE_OWNED = {"synced"}

LinkMaker = Callable[[Path, Path], None]


def _shared_skill_names(shared: Path) -> List[str]:
    if not shared.is_dir():
        return []
    return sorted(
        entry.name
        for entry in shared.iterdir()
        if entry.is_dir()
        and not entry.name.startswith(".")
        and entry.name not in PROFILE_OWNED
    )


def _is_junction(path: Path) -> bool:
    # Path.is_junction exists only on Python 3.12+; older Pythons are not on
    # Windows hosts that would have created junctions here anyway.
    check = getattr(path, "is_junction", None)
    return bool(check and check())


def _is_link(path: Path) -> bool:
    return path.is_symlink() or _is_junction(path)


def _same(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(
        os.path.realpath(right)
    )


def _raw_target(link: Path) -> Path:
    # Read the stored target rather than resolving the link, so a link whose
    # skill was deleted can still be recognised as one of ours.
    raw = os.readlink(link)
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    target = Path(raw)
    return target if target.is_absolute() else link.parent / target


def _points_to(link: Path, target: Path) -> bool:
    return _same(_raw_target(link), target)


def _points_into(link: Path, directory: Path) -> bool:
    return _same(_raw_target(link).parent, directory)


def _remove_link(path: Path) -> None:
    # Removes only the link. On Windows, CPython's unlink deletes directory
    # symlinks and junctions without touching the target's contents.
    path.unlink()


def make_directory_link(link: Path, target: Path) -> None:
    relative = os.path.relpath(target, link.parent)
    try:
        link.symlink_to(relative, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # Symlinks need Developer Mode or elevation; junctions do not.
        import _winapi

        _winapi.CreateJunction(str(target.resolve()), str(link))


def link_profile_skills(
    home: Path,
    profiles: Iterable[str] = PROFILE_DIRS,
    make_link: LinkMaker = make_directory_link,
) -> None:
    shared = home / ".agents/skills"
    names = _shared_skill_names(shared)
    wanted: Set[str] = set(names)

    for profile in profiles:
        skills = home / profile / "skills"
        skills.mkdir(parents=True, exist_ok=True)

        for name in names:
            link = skills / name
            target = shared / name
            if _is_link(link):
                if _points_to(link, target):
                    continue
                _remove_link(link)
            elif link.exists():
                print(f"skip {link}: a real directory is in the way")
                continue
            make_link(link, target)

        for entry in skills.iterdir():
            if (
                entry.name not in wanted
                and _is_link(entry)
                and _points_into(entry, shared)
            ):
                _remove_link(entry)


if __name__ == "__main__":
    link_profile_skills(Path.home())
