from pathlib import Path
import stat
import subprocess
import tempfile
import tomllib
import unittest

from tests.platform_support import (
    uses_posix_file_modes,
    WINDOWS_WITHOUT_SYMBOLIC_LINKS,
)


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(
    WINDOWS_WITHOUT_SYMBOLIC_LINKS,
    "Windows symbolic-link privilege is unavailable",
)
class CodexConfigMergeTest(unittest.TestCase):
    def test_shared_values_are_merged_without_losing_local_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config_path = home / ".codex/config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                '[projects."/device/local/project"]\n'
                'trust_level = "trusted"\n',
                encoding="utf-8",
            )

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

            with config_path.open("rb") as file:
                config = tomllib.load(file)

            self.assertEqual(config["model"], "gpt-5.6-sol")
            self.assertEqual(config["model_reasoning_effort"], "medium")
            self.assertEqual(
                config["projects"]["/device/local/project"]["trust_level"],
                "trusted",
            )
            self.assertTrue(config["tui"]["status_line_use_colors"])
            if uses_posix_file_modes():
                self.assertEqual(stat.S_IMODE(config_path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
