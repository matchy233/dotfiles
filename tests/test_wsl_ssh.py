import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/.chezmoiscripts/run_after_92-setup-wsl-ssh.py"
KEY = "ssh-ed25519 AAAAC3Nza-test-key user@windows"


def wsl_list(*names):
    return ("\r\n".join(names) + "\r\n").encode("utf-16")


class DistroListTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def test_docker_desktop_distros_are_not_development_environments(self):
        raw = wsl_list("Ubuntu-26.04", "docker-desktop", "docker-desktop-data", "Debian")

        self.assertEqual(self.script.parse_distros(raw), ["Ubuntu-26.04", "Debian"])

    def test_empty_output_means_no_distro(self):
        self.assertEqual(self.script.parse_distros(b""), [])


class PortAssignmentTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def test_new_distros_take_ports_from_2222_in_order(self):
        ports = self.script.assign_ports(["Ubuntu-26.04", "Debian"], {})

        self.assertEqual(ports, {"Ubuntu-26.04": 2222, "Debian": 2223})

    def test_an_assigned_port_never_changes_when_distros_come_and_go(self):
        before = {"Ubuntu-26.04": 2222, "Debian": 2223}

        after = self.script.assign_ports(["Ubuntu-26.04", "Arch"], before)

        self.assertEqual(after["Ubuntu-26.04"], 2222)
        self.assertEqual(after["Debian"], 2223)
        self.assertEqual(after["Arch"], 2224)


class AliasTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def test_alias_is_host_wsl_and_the_distro_name(self):
        aliases = self.script.alias_names("Desk-PC", ["Ubuntu-26.04"])

        self.assertEqual(aliases, {"Ubuntu-26.04": "desk-pc-wsl-ubuntu-26.04"})

    def test_distros_that_normalize_to_one_name_are_numbered(self):
        aliases = self.script.alias_names("box", ["Ubuntu_Dev", "ubuntu-dev"])

        self.assertEqual(
            aliases,
            {"Ubuntu_Dev": "box-wsl-ubuntu-dev", "ubuntu-dev": "box-wsl-ubuntu-dev-2"},
        )

    def test_a_third_collision_gets_the_next_number(self):
        aliases = self.script.alias_names("box", ["a_b", "a-b", "a b"])

        self.assertEqual(
            list(aliases.values()),
            ["box-wsl-a-b", "box-wsl-a-b-2", "box-wsl-a-b-3"],
        )


class ListenAddressTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    IP_OUTPUT = (
        "1: lo    inet 127.0.0.1/8 scope host lo\n"
        "5: eth0    inet 100.64.0.1/32 brd 100.64.0.1 scope global eth0\n"
    )

    def test_tailscale_address_is_added_when_the_distro_owns_it(self):
        self.assertEqual(
            self.script.listen_addresses("100.64.0.1", self.IP_OUTPUT),
            ["127.0.0.1", "100.64.0.1"],
        )

    def test_a_tailscale_address_the_distro_lacks_is_left_out(self):
        self.assertEqual(self.script.listen_addresses("100.9.9.9", self.IP_OUTPUT), ["127.0.0.1"])

    def test_without_tailscale_only_loopback_listens(self):
        self.assertEqual(self.script.listen_addresses(None, self.IP_OUTPUT), ["127.0.0.1"])


class RenderedFilesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)

    def test_ssh_config_points_each_alias_at_loopback_and_its_port(self):
        text = self.script.ssh_config(
            [
                {"alias": "box-wsl-ubuntu", "port": 2222, "user": "alice"},
                {"alias": "box-wsl-debian", "port": 2223, "user": "dev"},
            ]
        )

        self.assertIn("Host box-wsl-ubuntu\n\tHostName 127.0.0.1\n\tPort 2222\n\tUser alice\n", text)
        self.assertIn("Host box-wsl-debian\n\tHostName 127.0.0.1\n\tPort 2223\n\tUser dev\n", text)

    def test_provision_script_carries_the_listeners_user_and_key(self):
        text = self.script.provision_script(2222, ["127.0.0.1", "100.64.0.1"], "alice", KEY)

        self.assertIn("ListenStream=127.0.0.1:2222", text)
        self.assertIn("ListenStream=100.64.0.1:2222", text)
        self.assertIn("ListenAddress 127.0.0.1", text)
        self.assertIn("Port 2222", text)
        self.assertIn(KEY, text)
        self.assertIn("alice", text)

    def test_provision_script_resets_listeners_left_by_earlier_overrides(self):
        text = self.script.provision_script(2222, ["127.0.0.1"], "alice", KEY)

        self.assertIn("ListenStream=\nListenStream=127.0.0.1:2222", text)

    def test_socket_activation_drops_the_sshd_dropin_before_restarting(self):
        text = self.script.provision_script(2222, ["127.0.0.1"], "alice", KEY)
        socket_branch = text.split("\nelse\n")[0]
        removal = f"rm -f {self.script.SSHD_DROPIN}\n"

        self.assertIn(removal, socket_branch)
        self.assertLess(socket_branch.index(removal), socket_branch.index("systemctl restart ssh.socket"))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script(SCRIPT)
        self.commands = []
        self.provisioned = []
        self.tailscale = (0, "100.64.0.1\n")
        self.provision = (0, b"")
        self.ssh_code = 0

    def fake_run(self, args, **kwargs):
        self.assertTrue(kwargs.get("capture_output"))
        self.commands.append(list(args))
        text = " ".join(args)
        wants_text = args[0] == "tailscale" or "id -un" in text or "ip -4" in text
        self.assertEqual(bool(kwargs.get("text")), wants_text)
        if args[:2] == ["wsl", "-l"]:
            return mock.Mock(returncode=0, stdout=wsl_list("Ubuntu-26.04", "docker-desktop"), stderr=b"")
        if args[0] == "tailscale":
            return mock.Mock(returncode=self.tailscale[0], stdout=self.tailscale[1], stderr="")
        if "id -un" in text:
            return mock.Mock(returncode=0, stdout="alice\n", stderr="")
        if "ip -4" in text:
            return mock.Mock(returncode=0, stdout="5: eth0    inet 100.64.0.1/32\n", stderr="")
        if "bash -s" in text:
            self.provisioned.append(kwargs["input"])
            return mock.Mock(returncode=self.provision[0], stdout=self.provision[1], stderr=b"")
        return mock.Mock(returncode=self.ssh_code, stdout=b"", stderr=b"")

    def execute(self, home, platform="win32", which="C:/wsl.exe"):
        ssh_dir = Path(home) / ".ssh"
        ssh_dir.mkdir(exist_ok=True)
        (ssh_dir / "id_ed25519.pub").write_text(KEY + "\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out, \
             mock.patch.object(self.script.sys, "platform", platform), \
             mock.patch.object(self.script.shutil, "which", return_value=which), \
             mock.patch.object(self.script.Path, "home", return_value=Path(home)), \
             mock.patch.object(self.script.socket, "gethostname", return_value="DEMO-BOX"), \
             mock.patch.object(self.script.subprocess, "run", side_effect=self.fake_run):
            self.script.main()
        return out.getvalue()

    def run_main(self, **options):
        with tempfile.TemporaryDirectory() as home:
            output = self.execute(home, **options)
            config = Path(home) / ".ssh" / "config.wsl"
            ports = Path(home) / ".local" / "state" / "chezmoi" / "wsl-ssh-ports.json"
            return (
                output,
                config.read_text(encoding="utf-8") if config.exists() else None,
                json.loads(ports.read_text(encoding="utf-8")) if ports.exists() else None,
            )

    def test_other_platforms_do_nothing(self):
        output, config, _ = self.run_main(platform="linux")

        self.assertEqual(self.commands, [])
        self.assertIsNone(config)

    def test_missing_wsl_is_reported_and_skipped(self):
        output, config, _ = self.run_main(which=None)

        self.assertIn("WSL not installed", output)
        self.assertIsNone(config)

    def test_a_distro_is_provisioned_aliased_and_its_port_remembered(self):
        _, config, ports = self.run_main()

        self.assertEqual(len(self.provisioned), 1)
        self.assertIsInstance(self.provisioned[0], bytes)
        self.assertNotIn(b"\r", self.provisioned[0])
        self.assertIn(b"ListenStream=100.64.0.1:2222", self.provisioned[0])
        self.assertIn("Host demo-box-wsl-ubuntu-26.04\n\tHostName 127.0.0.1\n\tPort 2222\n\tUser alice", config)
        self.assertEqual(ports, {"Ubuntu-26.04": 2222})

    def test_docker_desktop_is_never_provisioned(self):
        self.run_main()

        self.assertFalse(any("docker-desktop" in " ".join(command) for command in self.commands if "-d" in command))

    def test_without_a_working_tailscale_only_loopback_listens(self):
        for broken in [(1, ""), (0, "")]:
            with self.subTest(tailscale=broken):
                self.tailscale = broken
                self.provisioned.clear()

                self.run_main()

                self.assertIn(b"ListenStream=127.0.0.1:2222", self.provisioned[0])
                self.assertNotIn(b"100.64.0.1", self.provisioned[0])

    def test_failed_provisioning_is_reported_and_no_alias_is_written(self):
        self.provision = (5, b"systemd is not running in this distro\n")

        output, config, _ = self.run_main()

        self.assertIn("provisioning failed: systemd is not running in this distro", output)
        self.assertNotIn("Host ", config)

    def test_the_ssh_check_result_is_reported(self):
        for code, verdict in [(0, "ubuntu-26.04: ok"), (255, "ubuntu-26.04: ssh failed")]:
            with self.subTest(code=code):
                self.ssh_code = code

                output, _, _ = self.run_main()

                self.assertIn(verdict, output)

    def test_a_second_run_keeps_the_remembered_port(self):
        with tempfile.TemporaryDirectory() as home:
            self.execute(home)
            self.execute(home)
            state = Path(home) / ".local" / "state" / "chezmoi" / "wsl-ssh-ports.json"

            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"Ubuntu-26.04": 2222})


if __name__ == "__main__":
    unittest.main()
