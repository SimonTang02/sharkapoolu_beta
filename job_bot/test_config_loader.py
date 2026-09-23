import json
import tempfile
import unittest
from pathlib import Path

from job_bot.config_loader import (
    ConfigError,
    apply_patches,
    deep_merge,
    load_composed_config,
    validate_config,
)


class ConfigLoaderTests(unittest.TestCase):
    def test_deep_merge_replaces_lists_and_merges_objects(self) -> None:
        result = deep_merge(
            {"scan": {"workers": 2, "retry": 1}, "sources": [1]},
            {"scan": {"workers": 8}, "sources": [2]},
        )
        self.assertEqual(result["scan"], {"workers": 8, "retry": 1})
        self.assertEqual(result["sources"], [2])

    def test_relative_includes_and_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runtime.json").write_text(
                json.dumps({"scan": {"workers": 4, "retry": 2}}), encoding="utf-8"
            )
            (root / "main.json").write_text(
                json.dumps({"includes": ["runtime.json"], "scan": {"workers": 8}}),
                encoding="utf-8",
            )
            result = load_composed_config(root / "main.json")
            self.assertEqual(result["scan"], {"workers": 8, "retry": 2})

    def test_include_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.json").write_text('{"includes":["b.json"]}', encoding="utf-8")
            (root / "b.json").write_text('{"includes":["a.json"]}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_composed_config(root / "a.json")

    def test_named_list_patch_can_tune_weight_and_keywords(self) -> None:
        config = {
            "scoring": {
                "foundation_groups": [
                    {"name": "digital", "base_score": 70, "keywords": ["RTL"]}
                ]
            }
        }
        result = apply_patches(
            config,
            [
                {
                    "path": "scoring.foundation_groups",
                    "match": {"name": "digital"},
                    "set": {
                        "base_score": 76,
                        "keywords": {"$append": ["SystemVerilog"], "$remove": ["RTL"]},
                    },
                }
            ],
        )
        group = result["scoring"]["foundation_groups"][0]
        self.assertEqual(group["base_score"], 76)
        self.assertEqual(group["keywords"], ["SystemVerilog"])

    def test_patch_must_match_exactly_one_item(self) -> None:
        with self.assertRaises(ConfigError):
            apply_patches(
                {"sources": [{"name": "one"}]},
                [{"path": "sources", "match": {"name": "missing"}, "set": {"enabled": False}}],
            )

    def test_submit_enabled_config_is_rejected(self) -> None:
        config = {
            "sources": [],
            "portals": {"adapters": []},
            "field_mappings": {"safety": {"allow_submit": True}},
        }
        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_invalid_weekly_reporting_config_is_rejected(self) -> None:
        config = {
            "sources": [],
            "portals": {"adapters": []},
            "field_mappings": {"safety": {"allow_submit": False}},
            "reporting": {"weekly": {"max_items_per_section": 0}},
        }
        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_invalid_workflow_module_is_rejected(self) -> None:
        config = {
            "sources": [],
            "portals": {"adapters": []},
            "field_mappings": {"safety": {"allow_submit": False}},
            "scoring": {
                "algorithm": "weighted_keywords_v1",
                "bands": {"high": 75, "relevant": 60, "adjacent": 45},
            },
            "workflows": {"bad": {"modules": ["submit_everything"]}},
        }
        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_invalid_source_tuning_value_is_rejected(self) -> None:
        config = {
            "sources": [{"name": "bad pagination", "max_pages": 0}],
            "portals": {"adapters": []},
            "field_mappings": {"safety": {"allow_submit": False}},
            "scoring": {
                "algorithm": "weighted_keywords_v1",
                "bands": {"high": 75, "relevant": 60, "adjacent": 45},
            },
            "workflows": {},
        }
        with self.assertRaises(ConfigError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
