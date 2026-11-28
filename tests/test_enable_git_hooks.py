import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/.chezmoiscripts/run_after_94-enable-git-hooks.py"


class EnableGitHooksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.script = load_script(SCRIPT)
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name) / "repo"
        self.source = self.repo / "home"
        self.source.mkdir(parents=True)

    def run_script(self, source: Path | None) -> str:
        environment = dict(os.environ)
        environment.pop("CHEZMOI_SOURCE_DIR", None)
        if source:
            environment["CHEZMOI_SOURCE_DIR"] = str(source)
        environment["GIT_CEILING_DIRECTORIES"] = str(self.repo.parent)
        output = io.StringIO()
        with mock.patch.dict(os.environ, environment, clear=True):
            with contextlib.redirect_stdout(output):
                self.script.main()
        return output.getvalue()

    def hooks_path(self) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo), "config", "--local", "core.hooksPath"],
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_clone_uses_the_tracked_hooks_after_every_apply(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

        self.assertEqual(self.run_script(self.source), "")
        self.assertEqual(self.run_script(self.source), "")

        self.assertEqual(self.hooks_path(), ".githooks")

    def test_source_that_is_not_a_clone_is_reported(self) -> None:
        output = self.run_script(self.source)

        self.assertIn("git-hooks: not enabled", output)

    def test_nothing_happens_outside_chezmoi(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

        self.assertEqual(self.run_script(None), "")

        self.assertEqual(self.hooks_path(), "")


if __name__ == "__main__":
    unittest.main()
