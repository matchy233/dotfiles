import importlib.util
import json
from pathlib import Path
import tempfile
from types import ModuleType
from typing import Any, List
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "home/dot_agents/install-skills.py"


def load_installer() -> ModuleType:
    if not INSTALLER_PATH.is_file():
        raise AssertionError(f"missing installer: {INSTALLER_PATH}")
    spec = importlib.util.spec_from_file_location("install_skills", INSTALLER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load installer: {INSTALLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillInstallerTest(unittest.TestCase):
    def write_lock(self, home: Path, names: List[str]) -> None:
        lock_path = home / ".agents/skills-lock.json"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text(
            json.dumps(
                {
                    "version": 3,
                    "skills": {
                        name: {
                            "source": "owner/repository",
                            "sourceType": "github",
                            "skillPath": f"skills/{name}/SKILL.md",
                            "computedHash": "test-hash",
                        }
                        for name in names
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_missing_npx_exits_before_installing(self) -> None:
        installer = load_installer()
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.write_lock(home, ["alpha"])

            with mock.patch.object(installer.shutil, "which", return_value=None):
                with self.assertRaisesRegex(SystemExit, "npx"):
                    installer.install_skills(home)

            self.assertFalse((home / ".agents/skills").exists())

    def test_installs_declared_skills_and_preserves_undeclared(self) -> None:
        installer = load_installer()
        calls: List[Any] = []

        def fake_runner(command: List[str], **kwargs: Any) -> None:
            calls.append((command, kwargs))
            stage = Path(kwargs["cwd"])
            staged_lock = json.loads(
                (stage / "skills-lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(set(staged_lock["skills"]), {"alpha", "beta"})
            for name in staged_lock["skills"]:
                skill = stage / ".agents/skills" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(name, encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.write_lock(home, ["alpha", "beta"])
            skills = home / ".agents/skills"
            (skills / "alpha").mkdir(parents=True)
            (skills / "alpha/obsolete.txt").write_text("old", encoding="utf-8")
            (skills / "local").mkdir()
            (skills / "local/SKILL.md").write_text("local", encoding="utf-8")

            installer.install_skills(
                home,
                npx_path="/fake/npx",
                runner=fake_runner,
            )

            self.assertEqual(len(calls), 1)
            command, kwargs = calls[0]
            self.assertEqual(
                command,
                ["/fake/npx", "--yes", "skills", "experimental_install"],
            )
            self.assertTrue(kwargs["check"])
            self.assertEqual((skills / "alpha/SKILL.md").read_text(), "alpha")
            self.assertFalse((skills / "alpha/obsolete.txt").exists())
            self.assertEqual((skills / "beta/SKILL.md").read_text(), "beta")
            self.assertEqual((skills / "local/SKILL.md").read_text(), "local")

    def test_incomplete_staging_does_not_replace_existing_skills(self) -> None:
        installer = load_installer()

        def fake_runner(command: List[str], **kwargs: Any) -> None:
            stage = Path(kwargs["cwd"])
            skill = stage / ".agents/skills/alpha"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("new", encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.write_lock(home, ["alpha", "beta"])
            existing = home / ".agents/skills/alpha/SKILL.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("old", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "beta"):
                installer.install_skills(
                    home,
                    npx_path="/fake/npx",
                    runner=fake_runner,
                )

            self.assertEqual(existing.read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
