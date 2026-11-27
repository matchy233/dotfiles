import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest import mock
import uuid

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/.chezmoiscripts/run_after_windows-appearance.py"
PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
ACCENT = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"
DWM = r"Software\Microsoft\Windows\DWM"


@unittest.skipUnless(sys.platform == "win32", "uses the Windows registry")
class WindowsAppearanceTest(unittest.TestCase):
    """Runs the script against a scratch key instead of the real settings."""

    def setUp(self) -> None:
        import winreg

        self.winreg = winreg
        self.script = load_script(SCRIPT)
        self.scratch = f"Software\\DotfilesTest\\{uuid.uuid4()}"
        self.script.PREFIX = self.scratch + "\\"
        self.addCleanup(self.delete_tree, self.scratch)
        self.windows = mock.MagicMock()
        for patcher in (
            mock.patch("ctypes.windll", self.windows),
            mock.patch("time.sleep"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def delete_tree(self, path: str) -> None:
        hive = self.winreg.HKEY_CURRENT_USER
        try:
            with self.winreg.OpenKey(hive, path) as key:
                count = self.winreg.QueryInfoKey(key)[0]
                children = [self.winreg.EnumKey(key, index) for index in range(count)]
        except FileNotFoundError:
            return
        for child in children:
            self.delete_tree(f"{path}\\{child}")
        self.winreg.DeleteKey(hive, path)

    def value(self, key: str, name: str):
        path = f"{self.scratch}\\{key}"
        with self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER, path) as handle:
            return self.winreg.QueryValueEx(handle, name)

    def set_value(self, key: str, name: str, value: int) -> None:
        path = f"{self.scratch}\\{key}"
        with self.winreg.CreateKey(self.winreg.HKEY_CURRENT_USER, path) as handle:
            self.winreg.SetValueEx(handle, name, 0, self.winreg.REG_DWORD, value)

    def run_script(self, *arguments: str) -> str:
        output = io.StringIO()
        with mock.patch("sys.argv", ["script", *arguments]):
            with contextlib.redirect_stdout(output):
                self.script.main()
        return output.getvalue()

    @property
    def announcements(self) -> int:
        return self.windows.user32.SendMessageTimeoutW.call_count

    def test_light_blue_machine_becomes_dark_with_the_purple_accent(self) -> None:
        self.set_value(PERSONALIZE, "AppsUseLightTheme", 1)
        self.set_value(DWM, "ColorizationColor", 0xC40078D4)
        self.set_value(DWM, "EnableAeroPeek", 1)

        self.run_script()

        dword = self.winreg.REG_DWORD
        self.assertEqual(self.value(PERSONALIZE, "AppsUseLightTheme"), (0, dword))
        self.assertEqual(self.value(PERSONALIZE, "SystemUsesLightTheme"), (0, dword))
        self.assertEqual(self.value(PERSONALIZE, "EnableTransparency"), (1, dword))
        self.assertEqual(self.value(PERSONALIZE, "ColorPrevalence"), (0, dword))
        self.assertEqual(self.value(DWM, "ColorPrevalence"), (1, dword))
        self.assertEqual(self.value(DWM, "ColorizationColor"), (0xC4A67DF2, dword))
        # Windows stores this one blue-green-red.
        self.assertEqual(self.value(ACCENT, "AccentColorMenu"), (0xFFF27DA6, dword))
        palette, kind = self.value(ACCENT, "AccentPalette")
        self.assertEqual(kind, self.winreg.REG_BINARY)
        self.assertEqual(len(palette), 32)
        self.assertEqual(
            self.value(r"Control Panel\Desktop", "AutoColorization"), (0, dword)
        )
        self.assertEqual(self.value(DWM, "EnableAeroPeek"), (1, dword))
        self.assertEqual(self.announcements, 1)

    def test_second_apply_stays_quiet(self) -> None:
        self.run_script()

        self.assertEqual(self.run_script(), "")
        self.assertEqual(self.announcements, 1)
        self.assertIn("No changes needed", self.run_script("--diff"))

    def test_value_windows_puts_back_is_written_again(self) -> None:
        def put_back_old_color(*_arguments) -> None:
            if self.announcements == 1:
                self.set_value(DWM, "ColorizationColor", 0xC40078D4)

        self.windows.user32.SendMessageTimeoutW.side_effect = put_back_old_color

        self.assertEqual(self.run_script(), "")

        self.assertEqual(self.value(DWM, "ColorizationColor")[0], 0xC4A67DF2)
        self.assertEqual(self.announcements, 2)

    def test_value_that_never_sticks_is_reported(self) -> None:
        self.windows.user32.SendMessageTimeoutW.side_effect = lambda *_: self.set_value(
            DWM, "ColorizationColor", 0xC40078D4
        )

        self.assertIn("ColorizationColor", self.run_script())

        self.assertEqual(self.announcements, 3)

    def test_preview_lists_changes_without_writing(self) -> None:
        self.set_value(PERSONALIZE, "AppsUseLightTheme", 1)

        output = self.run_script("--diff")

        self.assertIn("AppsUseLightTheme: 1 -> 0", output)
        self.assertEqual(self.value(PERSONALIZE, "AppsUseLightTheme")[0], 1)
        self.assertEqual(self.announcements, 0)

    def test_other_systems_are_left_alone(self) -> None:
        with mock.patch("sys.platform", "linux"):
            self.assertEqual(self.run_script(), "")

        self.assertEqual(self.announcements, 0)


if __name__ == "__main__":
    unittest.main()
