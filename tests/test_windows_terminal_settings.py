import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/.chezmoiscripts/run_after_windows-terminal-settings.py"
SOUND = Path("/home/someone/.local/share/sounds/bell.wav")

LOCAL = {
    "defaultProfile": "{pwsh}",
    "keybindings": [
        {"id": "Terminal.CopyToClipboard", "keys": "ctrl+c"},
        {"id": "Old.Binding", "keys": "shift+enter"},
    ],
    "profiles": {
        "defaults": {"font": {"face": "Sarasa Mono TC", "size": 14}, "opacity": 80},
        "list": [
            {"name": "PowerShell", "guid": "{pwsh}", "opacity": 80},
            {
                "name": "Ubuntu-26.04",
                "source": "Microsoft.WSL",
                "font": {"face": "XiaolaiMono Nerd Font"},
                "hidden": False,
            },
            {
                "name": "Ubuntu-custom",
                "source": "Microsoft.WSL",
                "colorScheme": "Campbell",
                "font": {"face": "Consolas", "size": 9},
                "bellStyle": "none",
            },
        ],
    },
    "schemes": [{"name": "Local", "background": "#000000"}],
}


class WindowsTerminalSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.script = load_script(SCRIPT)

    def profiles(self, settings: dict) -> dict:
        return {profile["name"]: profile for profile in settings["profiles"]["list"]}

    def test_shared_look_and_bell_become_the_defaults(self) -> None:
        result = self.script.merge(LOCAL, SOUND)

        defaults = result["profiles"]["defaults"]
        self.assertEqual(defaults["colorScheme"], "Diwali")
        self.assertEqual(
            defaults["font"], {"face": "Xiaolai Mono Nerd Font", "size": 14}
        )
        self.assertEqual(defaults["opacity"], 70)
        self.assertIs(defaults["useAcrylic"], True)
        self.assertEqual(defaults["bellStyle"], "audible")
        self.assertEqual(defaults["bellSound"], [str(SOUND)])
        schemes = {scheme["name"]: scheme for scheme in result["schemes"]}
        self.assertEqual(schemes["Diwali"]["background"], "#311652")
        self.assertEqual(schemes["Local"]["background"], "#000000")

    def test_profile_overrides_do_not_hide_the_shared_defaults(self) -> None:
        profiles = self.profiles(self.script.merge(LOCAL, SOUND))

        self.assertEqual(
            profiles["PowerShell"], {"name": "PowerShell", "guid": "{pwsh}"}
        )
        self.assertEqual(profiles["Ubuntu-custom"]["font"], {"size": 9})
        self.assertNotIn("bellStyle", profiles["Ubuntu-custom"])
        self.assertNotIn("font", profiles["Ubuntu-26.04"])

    def test_ubuntu_profiles_keep_their_scheme(self) -> None:
        profiles = self.profiles(self.script.merge(LOCAL, SOUND))

        self.assertEqual(profiles["Ubuntu-26.04"]["colorScheme"], "Ubuntu")
        self.assertEqual(profiles["Ubuntu-custom"]["colorScheme"], "Campbell")
        self.assertNotIn("colorScheme", profiles["PowerShell"])

    def test_shift_enter_sends_a_newline_and_other_settings_stay(self) -> None:
        result = self.script.merge(LOCAL, SOUND)

        self.assertEqual(result["defaultProfile"], "{pwsh}")
        self.assertEqual(
            result["keybindings"],
            [
                {"id": "Terminal.CopyToClipboard", "keys": "ctrl+c"},
                {"id": "User.claudeShiftEnterNewline", "keys": "shift+enter"},
            ],
        )
        self.assertEqual(result["actions"][-1]["command"]["input"], "\n")

    def test_only_ubuntu_wsl_profiles_are_given_the_ubuntu_scheme(self) -> None:
        local = {
            "profiles": {
                "list": [
                    {"name": "Debian", "source": "Microsoft.WSL"},
                    {"name": "Ubuntu over ssh"},
                ]
            }
        }

        result = self.script.merge(local, SOUND)

        for profile in result["profiles"]["list"]:
            self.assertNotIn("colorScheme", profile, profile["name"])

    def test_without_the_sound_file_the_local_bell_is_kept(self) -> None:
        local = copy.deepcopy(LOCAL)
        local["profiles"]["defaults"]["bellSound"] = ["C:\\old.wav"]

        result = self.script.merge(local, None)

        self.assertEqual(result["profiles"]["defaults"]["bellSound"], ["C:\\old.wav"])
        self.assertEqual(self.profiles(result)["Ubuntu-custom"]["bellStyle"], "none")

    def test_merging_twice_is_stable_and_leaves_the_input_alone(self) -> None:
        local = copy.deepcopy(LOCAL)

        once = self.script.merge(local, SOUND)

        self.assertEqual(local, LOCAL)
        self.assertEqual(self.script.merge(once, SOUND), once)

    def test_empty_settings_receive_the_shared_values(self) -> None:
        result = self.script.merge({}, SOUND)

        self.assertEqual(result["profiles"]["defaults"]["colorScheme"], "Diwali")


@unittest.skipUnless(sys.platform == "win32", "Windows Terminal runs on Windows")
class WindowsTerminalApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.script = load_script(SCRIPT)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.packages = Path(directory.name) / "Packages"
        self.sound = Path(directory.name) / "bell.wav"
        self.sound.write_bytes(b"wav")
        self.script.BELL_SOUND = self.sound
        patcher = mock.patch.dict("os.environ", {"LOCALAPPDATA": directory.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def settings_path(self, suffix: str = "abc") -> Path:
        package = self.packages / f"Microsoft.WindowsTerminal_{suffix}"
        (package / "LocalState").mkdir(parents=True)
        return package / "LocalState" / "settings.json"

    def run_script(self, *arguments: str) -> str:
        output = io.StringIO()
        with mock.patch("sys.argv", ["script", *arguments]):
            with contextlib.redirect_stdout(output):
                self.script.main()
        return output.getvalue()

    def test_apply_rewrites_the_file_once(self) -> None:
        path = self.settings_path()
        path.write_text('{"defaultProfile": "x"}', encoding="utf-8-sig")

        self.run_script()

        settings = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(settings["defaultProfile"], "x")
        self.assertEqual(
            settings["profiles"]["defaults"]["bellSound"], [str(self.sound)]
        )
        self.assertIn("No changes needed", self.run_script("--diff"))
        written = path.stat().st_mtime_ns
        self.run_script()
        self.assertEqual(path.stat().st_mtime_ns, written)
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_terminal_that_never_started_gets_a_settings_file(self) -> None:
        package = self.packages / "Microsoft.WindowsTerminal_abc"
        package.mkdir(parents=True)

        self.run_script()

        path = package / "LocalState" / "settings.json"
        self.assertIn('"Diwali"', path.read_text(encoding="utf-8"))

    def test_non_ascii_names_are_written_as_they_are(self) -> None:
        path = self.settings_path()
        path.write_text(
            '{"profiles": {"list": [{"name": "终端"}]}}', encoding="utf-8"
        )

        self.run_script()

        self.assertIn("终端", path.read_text(encoding="utf-8"))

    def test_preview_shows_the_change_without_writing(self) -> None:
        path = self.settings_path()

        self.assertIn('"Diwali"', self.run_script("--diff"))
        self.assertFalse(path.exists())

    def test_machine_without_windows_terminal_is_left_alone(self) -> None:
        self.assertEqual(self.run_script(), "")
        self.assertIn("No Windows Terminal", self.run_script("--diff"))
        self.assertFalse(self.packages.exists())

    def test_two_installs_stop_the_apply(self) -> None:
        self.settings_path("one")
        self.settings_path("two")

        with self.assertRaisesRegex(SystemExit, "multiple"):
            self.run_script()


if __name__ == "__main__":
    unittest.main()
