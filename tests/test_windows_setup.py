from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.ps1"


class WindowsSetupTest(unittest.TestCase):
    def test_setup_contains_required_preflight_and_migration_steps(self) -> None:
        content = SETUP.read_text(encoding="utf-8")

        for function in [
            "Test-CommandAvailable",
            "Test-SymbolicLinkCapability",
            "Backup-LegacyAgentsRepository",
            "Initialize-PrivateDeepSeekSettings",
            "Invoke-DotfilesSetup",
        ]:
            self.assertIn(f"function {function}", content)

        self.assertRegex(
            content,
            re.compile(r"New-Item\s+`?\s*-ItemType SymbolicLink", re.MULTILINE),
        )
        self.assertIn("Rename-Item", content)
        self.assertNotIn("Move-Item", content)
        self.assertIn('git -C $agentsPath status --short --branch', content)
        self.assertIn('git -C $agentsPath fsck --no-progress', content)
        self.assertIn('git -C $backupPath fsck --no-progress', content)
        self.assertIn("apply --dry-run --verbose", content)
        self.assertIn("ANTHROPIC_AUTH_TOKEN", content)
        self.assertIn("<your-deepseek-api-key>", content)
        self.assertNotIn("Write-Output $token", content)

    def test_dot_sourcing_does_not_change_the_caller_error_preference(self) -> None:
        content = SETUP.read_text(encoding="utf-8")
        setup_function = content.index("function Invoke-DotfilesSetup")
        error_preference = content.index('$ErrorActionPreference = "Stop"')

        self.assertGreater(error_preference, setup_function)

    def test_existing_agents_backup_can_be_reused_after_failed_apply(self) -> None:
        content = SETUP.read_text(encoding="utf-8")

        self.assertIn("Reusing existing agents backup", content)
        self.assertIn("return $backupPath", content)

    def test_setup_parses_when_native_powershell_is_available(self) -> None:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            self.skipTest("native PowerShell is unavailable")

        command = (
            "$errors = $null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{SETUP}', [ref]$null, [ref]$errors); "
            "if ($errors.Count -gt 0) { $errors | ForEach-Object { "
            "Write-Error $_ }; exit 1 }"
        )
        subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
