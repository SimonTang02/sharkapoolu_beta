import unittest
from pathlib import Path

from job_bot.run_modules import effective_config_hash, merge_selector, module_command


class ModuleRunnerTests(unittest.TestCase):
    def test_config_hash_is_order_independent(self) -> None:
        self.assertEqual(effective_config_hash({"a": 1, "b": 2}), effective_config_hash({"b": 2, "a": 1}))

    def test_cli_selector_overrides_only_explicit_values(self) -> None:
        result = merge_selector(
            {"browser": "http", "include_categories": ["official"]},
            {"browser": "any", "include_names": ["One"]},
        )
        self.assertEqual(result["browser"], "any")
        self.assertEqual(result["include_names"], ["One"])

    def test_missing_cli_selector_keeps_workflow_value(self) -> None:
        result = merge_selector(
            {"browser": "cdp"},
            {"browser": None, "include_names": []},
        )
        self.assertEqual(result, {"browser": "cdp"})

    def test_scan_command_expands_selector_to_exact_source_names(self) -> None:
        config = {
            "sources": [
                {"name": "HTTP", "type": "rss"},
                {"name": "Browser", "type": "moka_cdp"},
            ]
        }
        command = module_command(
            "scan",
            config_path=Path("config.json"),
            selector={"browser": "http"},
            config=config,
            max_workers=3,
        )
        self.assertIn("HTTP", command)
        self.assertNotIn("Browser", command)
        self.assertEqual(command[-2:], ["--max-workers", "3"])

    def test_digest_is_an_independent_module(self) -> None:
        command = module_command(
            "digest",
            config_path=Path("config.json"),
            selector={},
            config={},
            max_workers=None,
        )
        self.assertEqual(command[-3:], ["digest", "--config", "config.json"])


if __name__ == "__main__":
    unittest.main()
