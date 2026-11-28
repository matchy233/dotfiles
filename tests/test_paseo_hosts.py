import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/.chezmoiscripts/run_after_93-register-paseo-hosts.py"

HOSTS = [
    {"label": "alpha", "connection": "ssh://user@alpha"},
    {
        "label": "desk",
        "connection": "ssh://user@desk",
        "tailnet": True,
        "machine": "Desk",
        "os": "windows",
    },
    {
        "label": "desk-wsl",
        "connection": "ssh://user@desk-wsl?daemonPort=7000",
        "tailnet": True,
        "machine": "desk",
        "os": "linux",
        "formerLabels": ["desk WSL"],
    },
    {
        "label": "lab",
        "connection": "ssh://me@lab",
        "tailnet": True,
        "machine": "lab",
        "os": "windows",
    },
]


def labels(hosts):
    return [host["label"] for host in hosts]


class WantedHostsTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def wanted(self, hostname, os_name):
        data = {"chezmoi": {"hostname": hostname, "os": os_name}, "paseoHosts": HOSTS}
        return labels(self.script.wanted_hosts(data))

    def test_tailnet_device_registers_the_others_but_not_itself(self):
        self.assertEqual(self.wanted("DESK", "windows"), ["alpha", "desk-wsl", "lab"])

    def test_wsl_and_windows_on_one_hostname_are_different_devices(self):
        self.assertEqual(self.wanted("desk", "linux"), ["alpha", "desk", "lab"])

    def test_device_outside_the_tailnet_only_gets_the_shared_remotes(self):
        self.assertEqual(self.wanted("laptop", "linux"), ["alpha"])


REGISTERED = [
    {"registrationId": "hst_1", "label": "alpha", "connection": "ssh://user@alpha"},
    {"registrationId": "hst_2", "label": "desk WSL", "connection": "ssh://user@old-wsl-alias?daemonPort=7000"},
    {"registrationId": "hst_3", "label": "other", "connection": "ssh://x@other"},
]


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def test_new_host_is_added(self):
        wanted = [HOSTS[1]]
        self.assertEqual(
            self.script.plan(wanted, REGISTERED),
            [("add", "desk", "ssh://user@desk")],
        )

    def test_matching_host_needs_nothing(self):
        self.assertEqual(self.script.plan([HOSTS[0]], REGISTERED), [])

    def test_changed_connection_is_updated_in_place(self):
        moved = {"label": "alpha", "connection": "ssh://user@alpha-new"}
        self.assertEqual(
            self.script.plan([moved], REGISTERED),
            [("update", "hst_1", "alpha", "ssh://user@alpha-new")],
        )

    def test_former_label_is_renamed_not_duplicated(self):
        self.assertEqual(
            self.script.plan([HOSTS[2]], REGISTERED),
            [("update", "hst_2", "desk-wsl", "ssh://user@desk-wsl?daemonPort=7000")],
        )


class StoredConnectionTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def test_registrations_get_their_connection_from_the_stored_file(self):
        listing = [
            {"registrationId": "hst_1", "label": "a"},
            {"registrationId": "hst_2", "label": "b"},
        ]
        stored = [{"registrationId": "hst_1", "connection": "ssh://x@a"}]

        merged = self.script.with_connections(listing, stored)

        self.assertEqual([entry.get("connection") for entry in merged], ["ssh://x@a", None])

    def test_unknown_connection_is_rewritten_rather_than_trusted(self):
        known = [{"registrationId": "hst_1", "label": "alpha"}]
        self.assertEqual(
            self.script.plan([HOSTS[0]], known),
            [("update", "hst_1", "alpha", "ssh://user@alpha")],
        )


class MainTest(unittest.TestCase):
    CHEZMOI = {"chezmoi": {"hostname": "laptop", "os": "linux", "sourceDir": "/src/home"}}

    def setUp(self):
        self.script = load_script(SCRIPT)
        self.calls = []
        self.chezmoi_code = 0
        self.decrypt_code = 0

    def fake_run(self, listing_code, listing, args, **kwargs):
        self.assertTrue(kwargs.get("capture_output") and kwargs.get("text"))
        self.calls.append(args[1:] if args[0].endswith("paseo") else args)
        if args[:2] == ["chezmoi", "decrypt"]:
            hosts = json.dumps({"paseoHosts": [HOSTS[0]]})
            return mock.Mock(returncode=self.decrypt_code, stdout=hosts, stderr="no key")
        if args[0] == "chezmoi":
            return mock.Mock(returncode=self.chezmoi_code, stdout=json.dumps(self.CHEZMOI), stderr="no data")
        if args[1:3] == ["host", "ls"]:
            return mock.Mock(returncode=listing_code, stdout=json.dumps(listing), stderr="down")
        return mock.Mock(returncode=0, stdout="", stderr="")

    def run_main(self, paseo, listing_code=0, listing=(), stored=()):
        with tempfile.TemporaryDirectory() as home, contextlib.redirect_stdout(io.StringIO()) as out:
            if stored:
                (Path(home) / ".paseo").mkdir()
                (Path(home) / ".paseo" / "hosts.json").write_text(json.dumps(stored), encoding="utf-8")
            with mock.patch.object(self.script.shutil, "which", return_value=paseo),                  mock.patch.object(self.script.Path, "home", return_value=Path(home)),                  mock.patch.object(
                     self.script.subprocess,
                     "run",
                     side_effect=lambda args, **kw: self.fake_run(listing_code, list(listing), args, **kw),
                 ):
                self.script.main()
        return out.getvalue()

    def registrations_changed(self):
        return [call for call in self.calls if call[0] == "host" and call[1] in ("add", "update")]

    def test_missing_paseo_cli_is_skipped(self):
        output = self.run_main(paseo=None)

        self.assertIn("not found", output)
        self.assertEqual(self.calls, [])

    def test_unreachable_daemon_changes_nothing(self):
        output = self.run_main(paseo="/bin/paseo", listing_code=1)

        self.assertIn("daemon not reachable", output)
        self.assertEqual(self.registrations_changed(), [])

    def test_unreadable_chezmoi_input_changes_nothing(self):
        failures = {
            "chezmoi data failed": (1, 0),
            "cannot decrypt the host list, skipping: no key": (0, 1),
        }
        for message, (self.chezmoi_code, self.decrypt_code) in failures.items():
            with self.subTest(message):
                output = self.run_main(paseo="/bin/paseo")

                self.assertIn(message, output)
                self.assertEqual(self.registrations_changed(), [])

    def test_host_list_comes_from_the_encrypted_file_in_the_source(self):
        self.run_main(paseo="/bin/paseo")

        encrypted = Path("/src/home") / ".encrypted" / "paseo-hosts.json.age"
        self.assertIn(["chezmoi", "decrypt", str(encrypted)], self.calls)

    def test_missing_host_is_added_through_the_cli(self):
        self.run_main(paseo="/bin/paseo")

        self.assertIn(
            ["host", "add", "ssh://user@alpha", "--label", "alpha"],
            [list(call) for call in self.calls],
        )

    def test_connection_recorded_in_hosts_json_prevents_an_update(self):
        listing = [{"registrationId": "hst_1", "label": "alpha"}]
        stored = [{"registrationId": "hst_1", "connection": "ssh://user@alpha"}]

        self.run_main(paseo="/bin/paseo", listing=listing, stored=stored)

        self.assertEqual(self.registrations_changed(), [])


class ApplyTest(unittest.TestCase):
    def test_actions_become_paseo_host_commands(self):
        script = load_script(SCRIPT)
        calls = []

        def run(*args):
            calls.append(args)
            return 0, ""

        script.apply(
            [
                ("add", "desk", "ssh://user@desk"),
                ("update", "hst_2", "desk-wsl", "ssh://user@desk-wsl"),
            ],
            run,
        )

        self.assertEqual(
            calls,
            [
                ("host", "add", "ssh://user@desk", "--label", "desk"),
                ("host", "update", "hst_2", "--label", "desk-wsl", "--connection", "ssh://user@desk-wsl"),
            ],
        )

    def test_failed_command_is_reported_and_does_not_stop_the_rest(self):
        script = load_script(SCRIPT)
        calls = []

        def run(*args):
            calls.append(args)
            return (1, "boom\n") if len(calls) == 1 else (0, "")

        with contextlib.redirect_stdout(io.StringIO()) as out:
            script.apply(
                [("add", "one", "ssh://a@one"), ("add", "two", "ssh://a@two")],
                run,
            )

        self.assertEqual(len(calls), 2)
        self.assertIn("add one: failed boom", out.getvalue())
        self.assertIn("add two: ok", out.getvalue())


if __name__ == "__main__":
    unittest.main()
