import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
LINKER_PATH = ROOT / "home/dot_agents/link-profile-skills.py"


def load_linker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("link_profile_skills", LINKER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load linker: {LINKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def same(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(
        os.path.realpath(right)
    )


class ProfileSkillLinkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.linker = load_linker()
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        self.shared = self.home / ".agents/skills"
        self.profile = self.home / ".claude.tesla/skills"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def add_shared(self, name: str) -> None:
        skill = self.shared / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(name, encoding="utf-8")

    def link(self) -> None:
        self.linker.link_profile_skills(self.home)

    def test_links_each_shared_skill(self) -> None:
        self.add_shared("alpha")
        self.add_shared("beta")

        self.link()

        for name in ["alpha", "beta"]:
            link = self.profile / name
            self.assertTrue(self.linker._is_link(link), name)
            self.assertTrue(same(link, self.shared / name), name)
            self.assertEqual((link / "SKILL.md").read_text(), name)

    def test_skips_sync_and_hidden_directories(self) -> None:
        self.add_shared("alpha")
        (self.shared / "synced/other-account").mkdir(parents=True)
        (self.shared / ".alpha.chezmoi-new").mkdir()

        self.link()

        self.assertEqual(sorted(p.name for p in self.profile.iterdir()), ["alpha"])

    def test_keeps_profile_owned_and_real_directories(self) -> None:
        self.add_shared("alpha")
        own_sync = self.profile / "synced/this-account"
        own_sync.mkdir(parents=True)
        real = self.profile / "alpha"
        real.mkdir()
        (real / "SKILL.md").write_text("local", encoding="utf-8")

        self.link()

        self.assertTrue(own_sync.is_dir())
        self.assertFalse(self.linker._is_link(real))
        self.assertEqual((real / "SKILL.md").read_text(), "local")

    def test_removes_links_to_deleted_skills_only(self) -> None:
        self.add_shared("alpha")
        self.add_shared("beta")
        self.link()
        outside = self.home / "elsewhere"
        outside.mkdir()
        self.linker.make_directory_link(self.profile / "foreign", outside)

        (self.shared / "beta/SKILL.md").unlink()
        (self.shared / "beta").rmdir()
        self.link()

        self.assertFalse(os.path.lexists(self.profile / "beta"))
        self.assertTrue(self.linker._is_link(self.profile / "alpha"))
        self.assertTrue(self.linker._is_link(self.profile / "foreign"))
        self.assertTrue(outside.is_dir())

    def test_relinks_wrong_target_and_is_idempotent(self) -> None:
        self.add_shared("alpha")
        wrong = self.home / "wrong"
        wrong.mkdir()
        self.profile.mkdir(parents=True)
        self.linker.make_directory_link(self.profile / "alpha", wrong)

        self.link()
        self.link()

        self.assertTrue(same(self.profile / "alpha", self.shared / "alpha"))
        self.assertTrue(wrong.is_dir())

    def test_missing_shared_directory_only_creates_profile_dir(self) -> None:
        self.link()

        self.assertTrue(self.profile.is_dir())
        self.assertEqual(list(self.profile.iterdir()), [])

    def test_loading_linker_does_not_pollute_chezmoi_source(self) -> None:
        self.assertFalse((LINKER_PATH.parent / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
