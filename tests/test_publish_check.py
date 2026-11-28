import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / ".githooks/check_publish.py"
ZERO = "0" * 40

HOSTS = {
    "paseoHosts": [
        {
            "label": "study-pc",
            "formerLabels": ["old study box"],
            "connection": "ssh://sam@study-alias",
            "machine": "study-machine",
        },
        {"label": "lab-server", "connection": "ssh://sjones7@lab-alias:2200"},
    ],
    "privateNames": ["thinkbox"],
}
SSH_CONFIG = """Include ~/.ssh/config.local

Host build-farm *.internal
    HostName build.example.net
    User deploy42

Host *
    User sam
"""


class PublishCheckTest(unittest.TestCase):
    """Pushes real commits from a scratch repository through the check."""

    def setUp(self) -> None:
        self.script = load_script(SCRIPT)
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        (root / ".ssh").mkdir()
        (root / ".ssh" / "config").write_text(SSH_CONFIG, encoding="utf-8")
        (root / "gitconfig").write_text(
            "[user]\n\tname = Sam\n\temail = sam@example.org\n", encoding="utf-8"
        )
        self.decrypt_fails = False
        real_run = self.script.run

        def run(*args: str) -> str:
            if args[0] != "chezmoi":
                return real_run(*args)
            if self.decrypt_fails:
                raise subprocess.CalledProcessError(1, args, stderr="no identity")
            return json.dumps(HOSTS)

        for patcher in (
            mock.patch.dict(
                os.environ,
                {
                    "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
            ),
            mock.patch.object(self.script, "run", run),
            mock.patch.object(self.script.Path, "home", return_value=root),
            mock.patch.object(
                self.script.socket, "gethostname", return_value="DEV-LAPTOP"
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)
        self.git("init", "-q", "-b", "main")
        self.commit("start", {"README.md": "hello\n"})

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    def commit(self, message: str, files: dict[str, str]) -> str:
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def push(self, local: str | None = None) -> tuple[int, str]:
        local = local or self.git("rev-parse", "HEAD")
        line = f"refs/heads/main {local} refs/heads/main {ZERO}\n"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.script.main(["origin", "url"], io.StringIO(line))
        return code, output.getvalue()

    def assert_refused(self, term: str) -> None:
        code, output = self.push()

        self.assertEqual(code, 1, output)
        self.assertIn(term, output)
        self.assertIn(self.git("rev-parse", "--short", "HEAD"), output)

    def assert_allowed(self) -> None:
        self.assertEqual(self.push(), (0, ""))

    def test_text_that_publishes_nothing_private_is_pushed(self) -> None:
        for text in (
            "match any host name or user name",
            "mythinkbox thinkboxes",
            "*.internal and *",
            "Written by Sam <hi@sam.example>",
            "100.64.0.9 100.9.9.9 127.0.0.1",
        ):
            with self.subTest(text):
                self.commit("add a line", {"a.txt": f"{text}\n"})

                self.assert_allowed()

                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_private_names_in_added_lines_are_refused(self) -> None:
        for name in (
            "study-pc",
            "Study-Machine",
            "old study box",
            "study-alias",
            "lab-server",
            "thinkbox",
            "build-farm",
            "build.example.net",
            "dev-laptop",
        ):
            with self.subTest(name):
                self.commit("add a line", {"a.txt": f"reach {name} today\n"})

                self.assert_refused(name)

                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_private_name_in_a_message_path_or_plus_line_is_refused(self) -> None:
        for message, files in (
            ("feat: reach thinkbox", {"a.txt": "ok\n"}),
            ("add a file", {"hosts/thinkbox.txt": "ok\n"}),
            ("add a marker", {"a.txt": "++ thinkbox\n"}),
        ):
            with self.subTest(message):
                self.commit(message, files)

                self.assert_refused("thinkbox")

                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_ssh_users_are_refused_where_they_name_a_login(self) -> None:
        for text in ("ssh://sam@somewhere", "User sam", "deploy42", "sjones7"):
            with self.subTest(text):
                self.commit("add a login", {"a.txt": f"{text}\n"})

                self.assert_refused(text.split("@")[0].removeprefix("ssh://"))

                self.git("reset", "-q", "--hard", "HEAD~1")

    def test_real_tailnet_address_is_refused(self) -> None:
        # Assembled here so the check does not refuse this file.
        address = ".".join(["100", "101", "102", "103"])
        self.commit("add an address", {"a.txt": f"ip {address}\n"})

        self.assert_refused(address)

    def test_encrypted_text_is_not_searched_but_plain_text_beside_it_is(
        self,
    ) -> None:
        armor = (
            "-----BEGIN AGE ENCRYPTED FILE-----\nab+thinkbox+cd\n"
            "-----END AGE ENCRYPTED FILE-----\n"
        )
        self.commit("add a secret", {"s.age": armor})
        self.assert_allowed()

        self.commit("add a note", {"s.age": armor + "note: thinkbox\n"})

        self.assert_refused("thinkbox")

    def test_removing_a_private_name_is_allowed(self) -> None:
        leaked = self.commit("leak", {"a.txt": "thinkbox\n"})
        self.git("update-ref", "refs/remotes/origin/main", leaked)
        self.commit("remove it", {"a.txt": "gone\n"})

        self.assert_allowed()

    def test_every_unpublished_commit_is_checked(self) -> None:
        leaked = self.commit("leak", {"a.txt": "thinkbox\n"})
        self.commit("remove it", {"a.txt": "gone\n"})

        code, output = self.push()

        self.assertEqual(code, 1)
        self.assertIn(leaked[:7], output)

    def test_deleting_a_remote_branch_is_allowed(self) -> None:
        self.commit("leak", {"a.txt": "thinkbox\n"})

        self.assertEqual(self.push(ZERO), (0, ""))

    def test_commit_that_git_cannot_list_stops_the_push(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            self.push("deadbeef" * 5)

    def test_push_is_refused_when_the_name_list_cannot_be_read(self) -> None:
        self.decrypt_fails = True

        code, output = self.push()

        self.assertEqual(code, 1)
        self.assertIn("cannot read the private names", output)
        self.assertIn("no identity", output)


if __name__ == "__main__":
    unittest.main()
