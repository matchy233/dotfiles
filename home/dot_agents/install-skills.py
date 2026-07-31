#!/usr/bin/env python3

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional


Runner = Callable[..., Any]


def _load_skill_names(lock_path: Path) -> List[str]:
    data: Dict[str, Any] = json.loads(lock_path.read_text(encoding="utf-8"))
    skills = data.get("skills")
    if not isinstance(skills, dict):
        raise RuntimeError(f"invalid skills lock: {lock_path}")

    names = sorted(skills)
    for name in names:
        if not isinstance(name, str) or Path(name).name != name or name in {"", "."}:
            raise RuntimeError(f"invalid skill name in lock: {name!r}")
    return names


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _replace_directory(source: Path, target: Path) -> None:
    incoming = target.parent / f".{target.name}.chezmoi-new"
    backup = target.parent / f".{target.name}.chezmoi-old"
    _remove_path(incoming)
    _remove_path(backup)
    shutil.copytree(source, incoming, symlinks=True)

    had_target = target.exists() or target.is_symlink()
    if had_target:
        target.rename(backup)
    try:
        incoming.rename(target)
    except Exception:
        if had_target:
            backup.rename(target)
        raise
    finally:
        _remove_path(incoming)
    _remove_path(backup)


def install_skills(
    home: Path,
    npx_path: Optional[str] = None,
    runner: Runner = subprocess.run,
) -> None:
    lock_path = home / ".agents/skills-lock.json"
    names = _load_skill_names(lock_path)
    npx = npx_path or shutil.which("npx")
    if npx is None:
        raise SystemExit("npx is required to install agent skills")

    with tempfile.TemporaryDirectory(prefix="agent-skills-") as directory:
        stage = Path(directory)
        shutil.copy2(lock_path, stage / "skills-lock.json")
        runner(
            [npx, "--yes", "skills", "experimental_install"],
            cwd=stage,
            check=True,
        )

        staged_skills = stage / ".agents/skills"
        missing = [name for name in names if not (staged_skills / name).is_dir()]
        if missing:
            missing_list = ", ".join(missing)
            raise RuntimeError(f"installer did not stage declared skills: {missing_list}")

        destination = home / ".agents/skills"
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            _replace_directory(staged_skills / name, destination / name)


if __name__ == "__main__":
    install_skills(Path.home())
