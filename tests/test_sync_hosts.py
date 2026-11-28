import contextlib
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "scripts/sync-hosts.py"

ENTRIES = [
    {"label": "shared", "connection": "ssh://me@shared"},
    {
        "label": "desk",
        "connection": "ssh://Me@desk-alias",
        "machine": "Desk",
        "os": "windows",
        "chezmoi": True,
    },
    {
        "label": "desk-wsl",
        "connection": "ssh://me@desk-wsl-alias?daemonPort=7000",
        "machine": "desk",
        "os": "linux",
        "chezmoi": True,
    },
    {
        "label": "work",
        "connection": "ssh://me@work-alias",
        "machine": "work",
        "os": "windows",
    },
]


class SyncHostsTest(unittest.TestCase):
    """Runs the script with the chezmoi and ssh commands replaced."""

    def setUp(self) -> None:
        self.script = load_script(SCRIPT)
        self.commands: list[list[str]] = []
        self.results: dict[str, object] = {}
        self.decrypt_code = 0

    def fake_run(self, command, **options):
        command = list(command)
        if command[:2] == ["chezmoi", "decrypt"]:
            self.assertEqual(
                Path(command[2]), ROOT / "home/.encrypted/paseo-hosts.json.age"
            )
            self.assertTrue(options["capture_output"] and options["text"])
            return subprocess.CompletedProcess(
                command,
                self.decrypt_code,
                json.dumps({"paseoHosts": ENTRIES}),
                "no identity",
            )
        self.assertTrue(options["capture_output"])
        self.assertEqual(options["stdin"], subprocess.DEVNULL)
        self.assertGreater(options["timeout"], 0)
        self.commands.append(command)
        for part, result in self.results.items():
            if part in " ".join(command):
                if isinstance(result, BaseException):
                    raise result
                return subprocess.CompletedProcess(command, result, "", "went wrong")
        return subprocess.CompletedProcess(command, 0, "", "")

    def sync(self, hostname="desk", platform="win32") -> tuple[int, str]:
        output = io.StringIO()
        with (
            mock.patch.object(self.script.subprocess, "run", self.fake_run),
            mock.patch.object(
                self.script.socket, "gethostname", return_value=hostname.upper()
            ),
            mock.patch.object(self.script.sys, "platform", platform),
            contextlib.redirect_stdout(output),
        ):
            code = self.script.main()
        return code, output.getvalue()

    def command_for(self, destination: str) -> list[str]:
        return next(command for command in self.commands if destination in command)

    def test_only_devices_marked_as_chezmoi_managed_are_synced(self) -> None:
        code, output = self.sync()

        self.assertEqual(code, 0)
        self.assertEqual(sorted(output.splitlines()), ["desk-wsl: ok", "desk: ok"])
        self.assertEqual(len(self.commands), 2)

    def test_this_windows_device_is_synced_without_ssh(self) -> None:
        self.sync()

        local = [command for command in self.commands if command[0] != "ssh"]
        self.assertEqual(local, [["pwsh", "-NoProfile", "-Command", self.script.SYNC]])

    def test_this_linux_device_is_synced_through_bash(self) -> None:
        self.sync(platform="linux")

        self.assertIn(
            ["bash", "-c", self.script.LINUX_PATH + self.script.SYNC], self.commands
        )
        self.assertEqual(
            self.command_for("ssh://Me@desk-alias")[-1], self.script.SYNC
        )

    def test_remote_linux_device_gets_its_user_path_and_never_prompts(self) -> None:
        self.sync()

        command = self.command_for("ssh://me@desk-wsl-alias")
        self.assertEqual(command[0], "ssh")
        self.assertIn("BatchMode=yes", command)
        self.assertEqual(command[-1], self.script.LINUX_PATH + self.script.SYNC)

    def test_sync_pulls_then_applies_only_files_without_a_prompt(self) -> None:
        self.assertEqual(
            self.script.SYNC,
            "chezmoi update --apply=false && "
            "chezmoi apply --no-tty --exclude=scripts,externals",
        )

    def test_each_kind_of_failure_is_named_and_fails_the_run(self) -> None:
        for result, expected in (
            (1, "desk-wsl: exit 1: went wrong"),
            (255, "desk-wsl: unreachable: went wrong"),
            (subprocess.TimeoutExpired("ssh", 120), "desk-wsl: timed out after 120s"),
            (FileNotFoundError("no ssh"), "desk-wsl: cannot start: no ssh"),
        ):
            with self.subTest(expected):
                self.results = {"desk-wsl-alias": result}

                code, output = self.sync()

                self.assertEqual(code, 1)
                self.assertIn(expected, output)
                self.assertIn("desk: ok", output)

    def test_nothing_is_synced_when_the_host_list_cannot_be_read(self) -> None:
        self.decrypt_code = 1

        code, output = self.sync()

        self.assertEqual(code, 1)
        self.assertIn("cannot decrypt the host list: no identity", output)
        self.assertEqual(self.commands, [])

    def test_list_without_managed_devices_is_a_failure(self) -> None:
        with mock.patch.dict(ENTRIES[1], {"chezmoi": False}):
            with mock.patch.dict(ENTRIES[2], {"chezmoi": False}):
                code, output = self.sync()

        self.assertEqual(code, 1)
        self.assertIn("no chezmoi-managed host", output)


if __name__ == "__main__":
    unittest.main()
