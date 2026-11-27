from pathlib import Path
import unittest

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/.chezmoiscripts/run_after_92-register-paseo-hosts.py"

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


if __name__ == "__main__":
    unittest.main()
