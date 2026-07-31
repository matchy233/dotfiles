import json
from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SourceConfigTest(unittest.TestCase):
    def test_json_files_parse(self) -> None:
        for path in (ROOT / "home/dot_agents").rglob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))

    def test_toml_files_parse(self) -> None:
        for path in (ROOT / "home/dot_agents").rglob("*.toml"):
            with path.open("rb") as file:
                tomllib.load(file)

    def test_shared_codex_config_has_no_projects(self) -> None:
        path = ROOT / "home/dot_agents/codex/config.shared.toml"
        with path.open("rb") as file:
            config = tomllib.load(file)
        self.assertNotIn("projects", config)

    def test_shell_entrypoints_load_local_overrides_last(self) -> None:
        zshrc = (ROOT / "home/dot_zshrc").read_text(encoding="utf-8")
        self.assertIn("$HOME/.zshrc.local", zshrc)
        self.assertTrue(zshrc.rstrip().endswith('source "$HOME/.zshrc.local"\nfi'))

        shared = ROOT / "home/dot_config/powershell/shared-profile.ps1"
        self.assertTrue(shared.is_file(), shared)

        profiles = [
            ROOT
            / "home/readonly_Documents/WindowsPowerShell"
            / "empty_Microsoft.PowerShell_profile.ps1",
            ROOT
            / "home/readonly_Documents/PowerShell"
            / "empty_Microsoft.PowerShell_profile.ps1",
        ]
        for profile in profiles:
            content = profile.read_text(encoding="utf-8")
            shared_index = content.index("shared-profile.ps1")
            local_index = content.index("local-profile.ps1")
            self.assertLess(shared_index, local_index, profile)

    def test_shared_source_has_no_absolute_linux_home_paths(self) -> None:
        absolute_home = re.compile(r"/home/[A-Za-z0-9._-]+")
        for path in (ROOT / "home").rglob("*"):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            self.assertIsNone(absolute_home.search(content), path)

    def test_google_cloud_environment_is_device_local(self) -> None:
        shared_profile = (
            ROOT / "home/dot_config/powershell/shared-profile.ps1"
        ).read_text(encoding="utf-8")

        self.assertNotIn("GOOGLE_CLOUD_PROJECT", shared_profile)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", shared_profile)

    def test_local_only_source_paths_are_gitignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        for path in [
            "home/dot_zshrc.local",
            "home/dot_config/powershell/local-profile.ps1",
            "home/dot_agents/claude/cc-deepseek.settings.json",
        ]:
            self.assertIn(path, gitignore)


if __name__ == "__main__":
    unittest.main()
