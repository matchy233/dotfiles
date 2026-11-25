import json
from pathlib import Path
import subprocess
import sys
import unittest


# absolute(), not resolve(): mutator runs tests through symlinks, and the
# hook under test must be the one next to this checkout of the test.
ROOT = Path(__file__).absolute().parents[1]
HOOK = ROOT / "home/dot_claude/hooks/fxtwitter-webfetch.py"
SETTINGS = ROOT / "home/dot_agents/claude/settings.json"


def run_hook(payload: dict) -> str:
    result = subprocess.run(
        [sys.executable, "-I", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def webfetch(url: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "WebFetch",
        "tool_input": {"url": url, "prompt": "summarize"},
    }


class FxtwitterHookTest(unittest.TestCase):
    def rewritten_input(self, url: str) -> dict:
        output = json.loads(run_hook(webfetch(url)))["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "allow")
        return output["updatedInput"]

    def test_x_status_link_goes_to_fxtwitter_api(self) -> None:
        updated = self.rewritten_input("https://x.com/someone/status/123?s=20&t=abc")
        self.assertEqual(updated["url"], "https://api.fxtwitter.com/someone/status/123")
        self.assertEqual(updated["prompt"], "summarize")

    def test_twitter_hosts_are_rewritten(self) -> None:
        for host in ["twitter.com", "www.twitter.com", "mobile.twitter.com", "www.x.com", "mobile.x.com"]:
            with self.subTest(host=host):
                updated = self.rewritten_input(f"http://{host}/a/status/9")
                self.assertEqual(updated["url"], "https://api.fxtwitter.com/a/status/9")

    def test_other_urls_pass_through_untouched(self) -> None:
        for url in [
            "https://example.com/x.com/status/1",
            "https://notx.com/a/status/1",
            "https://api.fxtwitter.com/a/status/1",
        ]:
            with self.subTest(url=url):
                self.assertEqual(run_hook(webfetch(url)), "")

    def test_settings_register_hook_for_webfetch(self) -> None:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        entries = settings["hooks"]["PreToolUse"]
        commands = [
            hook["command"]
            for entry in entries
            if entry["matcher"] == "WebFetch"
            for hook in entry["hooks"]
        ]
        self.assertIn("python3 -I ~/.claude/hooks/fxtwitter-webfetch.py", commands)


if __name__ == "__main__":
    unittest.main()
