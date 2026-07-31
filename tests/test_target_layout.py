from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

from tests.platform_support import (
    renders_windows_documents,
    WINDOWS_WITHOUT_SYMBOLIC_LINKS,
)


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(
    WINDOWS_WITHOUT_SYMBOLIC_LINKS,
    "Windows symbolic-link privilege is unavailable",
)
class TargetLayoutTest(unittest.TestCase):
    def apply(self, home: Path) -> None:
        subprocess.run(
            [
                "chezmoi",
                "--source",
                str(ROOT),
                "--destination",
                str(home),
                "--cache",
                str(home / ".cache/chezmoi"),
                "--persistent-state",
                str(home / ".local/state/chezmoi.boltdb"),
                "apply",
                "--exclude=scripts",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_expected_files_and_links_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.apply(home)

            for relative in [
                ".zshrc",
                ".condarc",
                ".dircolors",
                ".agents/AGENTS.md",
                ".agents/codex/config.shared.toml",
                ".agents/install-skills.py",
            ]:
                self.assertTrue((home / relative).is_file(), relative)

            links = {
                ".codex/AGENTS.md": ".agents/AGENTS.md",
                ".codex/agents": ".agents/codex/agents",
                ".claude/CLAUDE.md": ".agents/AGENTS.md",
                ".claude/settings.json": ".agents/claude/settings.json",
                ".claude/skills": ".agents/skills",
            }
            for link_name, target_name in links.items():
                link = home / link_name
                self.assertTrue(link.is_symlink(), link_name)
                self.assertEqual(link.resolve(), (home / target_name).resolve())

    def test_repository_only_files_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.apply(home)

            for relative in ["README.md", "setup.sh", "setup.ps1"]:
                self.assertFalse((home / relative).exists(), relative)

            windows_profiles = [
                home
                / "Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1",
                home / "Documents/PowerShell/Microsoft.PowerShell_profile.ps1",
            ]
            shared_profile = home / ".config/powershell/shared-profile.ps1"
            if renders_windows_documents():
                self.assertTrue(shared_profile.is_file(), shared_profile)
                for profile in windows_profiles:
                    self.assertTrue(profile.is_file(), profile)
            else:
                self.assertFalse((home / "Documents").exists(), "Documents")
                self.assertFalse((home / ".config").exists(), ".config")

    def test_second_apply_preserves_codex_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.apply(home)
            config_path = home / ".codex/config.toml"
            with config_path.open("a", encoding="utf-8") as file:
                file.write(
                    '\n[projects."/device/second-project"]\n'
                    'trust_level = "trusted"\n'
                )

            self.apply(home)

            with config_path.open("rb") as file:
                config = tomllib.load(file)
            self.assertEqual(
                config["projects"]["/device/second-project"]["trust_level"],
                "trusted",
            )

    def test_managed_agent_readme_uses_unified_setup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.apply(home)
            readme = (home / ".agents/README.md").read_text(encoding="utf-8")

            self.assertIn("chezmoi", readme.lower())
            self.assertIn("matchy233/dotfiles", readme)
            self.assertNotIn("matchy233/agents.git", readme)


if __name__ == "__main__":
    unittest.main()
