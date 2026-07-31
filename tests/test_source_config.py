import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SourceConfigTest(unittest.TestCase):
    def test_json_files_parse(self) -> None:
        for path in (ROOT / "home/dot_agents").rglob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))

    def test_toml_files_parse(self) -> None:
        for path in (ROOT / "home/dot_agents").rglob("*.toml"):
            with path.open("rb") as file:
                tomllib.load(file)

    def test_shared_codex_config_has_no_projects(self) -> None:
        path = ROOT / "home/dot_agents/codex/config.shared.toml"
        with path.open("rb") as file:
            config = tomllib.load(file)
        self.assertNotIn("projects", config)


if __name__ == "__main__":
    unittest.main()
