import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

from tests.script_loading import load_script


ROOT = Path(__file__).absolute().parents[1]
SCRIPT = ROOT / "home/dot_local/bin/install-fonts.py"


class FontInstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.installer = load_script(SCRIPT)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.upstream = root / "upstream"
        self.user_fonts = root / "user"
        self.system_fonts = root / "system"
        self.upstream.mkdir()
        self.system_fonts.mkdir()
        self.registered: list[Path] = []

    def entry(self, source: str, content: bytes, files: list[str], **extra) -> dict:
        path = self.upstream / source
        path.write_bytes(content)
        return {
            "url": path.as_uri(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "files": files,
            **extra,
        }

    def install(self, fonts: list[dict]) -> list[str]:
        return self.installer.install(
            fonts, self.user_fonts, self.system_fonts, self.registered.append
        )

    def test_missing_font_is_downloaded_under_its_target_name_and_registered(self) -> None:
        entry = self.entry("asset.ttf", b"glyphs", ["My Font.ttf"])

        self.assertEqual(self.install([entry]), ["My Font.ttf"])

        installed = self.user_fonts / "My Font.ttf"
        self.assertEqual(installed.read_bytes(), b"glyphs")
        self.assertEqual(self.registered, [installed])
        self.assertEqual(list(self.user_fonts.iterdir()), [installed])

    def test_second_run_changes_nothing(self) -> None:
        entry = self.entry("asset.ttf", b"glyphs", ["a.ttf"])
        self.install([entry])
        self.registered.clear()

        self.assertEqual(self.install([entry]), [])
        self.assertEqual(self.registered, [])

    def test_installed_fonts_are_not_downloaded_again(self) -> None:
        (self.system_fonts / "System.TTF").write_bytes(b"older build")
        entries = [
            {"url": "file:///does/not/exist", "sha256": "0", "files": ["system.ttf"]},
            {
                "url": "file:///does/not/exist",
                "sha256": "0",
                "files": ["static.ttf"],
                "satisfied_by": ["System.ttf"],
            },
        ]

        self.assertEqual(self.install(entries), [])

    def test_wrong_hash_installs_nothing(self) -> None:
        entry = self.entry("asset.ttf", b"glyphs", ["a.ttf"])
        entry["sha256"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "sha256"):
            self.install([entry])

        self.assertFalse((self.user_fonts / "a.ttf").exists())
        self.assertEqual(self.registered, [])

    def test_several_fonts_go_into_a_font_directory_that_did_not_exist(self) -> None:
        self.user_fonts = self.user_fonts / "Microsoft" / "Fonts"
        entries = [
            self.entry("a.ttf", b"a", ["a.ttf"]),
            self.entry("b.ttf", b"b", ["b.ttf"]),
        ]

        self.assertEqual(self.install(entries), ["a.ttf", "b.ttf"])

    @unittest.skipUnless(os.name == "nt", "archives are extracted with Windows tar.exe")
    def test_broken_archive_stops_the_install(self) -> None:
        entry = self.entry("broken.zip", b"not an archive", ["a.ttf"])

        with self.assertRaises(subprocess.CalledProcessError):
            self.install([entry])

        self.assertEqual(self.registered, [])

    @unittest.skipUnless(os.name == "nt", "registers fonts for a Windows user")
    def test_run_installs_for_the_current_user_and_activates_the_fonts(self) -> None:
        entry = self.entry("asset.ttf", b"glyphs", ["ci-only-font.ttf"])
        local = self.user_fonts
        registry, windows = mock.MagicMock(), mock.MagicMock()

        with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(local)}):
            with mock.patch.dict("sys.modules", {"winreg": registry}):
                with mock.patch("ctypes.windll", windows):
                    for _ in range(2):
                        stdin = io.StringIO(json.dumps([entry]))
                        with mock.patch("sys.stdin", stdin):
                            self.installer.main()

        installed = local / "Microsoft/Windows/Fonts/ci-only-font.ttf"
        self.assertEqual(installed.read_bytes(), b"glyphs")
        self.assertEqual(
            registry.SetValueEx.call_args.args[1:],
            ("ci-only-font (TrueType)", 0, registry.REG_SZ, str(installed)),
        )
        windows.gdi32.AddFontResourceW.assert_called_once_with(str(installed))
        windows.user32.SendMessageTimeoutW.assert_called_once()
        acl = subprocess.run(
            ["icacls", installed], check=True, capture_output=True
        ).stdout.upper()
        self.assertIn(b"APPLICATION PACKAGES", acl)

    @unittest.skipUnless(os.name == "nt", "archives are extracted with Windows tar.exe")
    def test_only_missing_listed_files_are_taken_from_an_archive(self) -> None:
        archive = self.upstream / "build.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("nested/Mono Regular.ttf", b"regular")
            output.writestr("nested/Mono Bold.ttf", b"bold")
            output.writestr("nested/Unused.ttf", b"unused")
        entry = {
            "url": archive.as_uri(),
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "files": ["Mono Regular.ttf", "Mono Bold.ttf"],
        }
        (self.system_fonts / "Mono Bold.ttf").write_bytes(b"older build")

        self.assertEqual(self.install([entry]), ["Mono Regular.ttf"])

        self.assertEqual(
            (self.user_fonts / "Mono Regular.ttf").read_bytes(), b"regular"
        )
        self.assertEqual(
            [path.name for path in self.user_fonts.iterdir()], ["Mono Regular.ttf"]
        )


if __name__ == "__main__":
    unittest.main()
