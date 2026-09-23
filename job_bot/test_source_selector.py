import unittest

from job_bot.source_selector import select_sources


class SourceSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "sources": [
                {"name": "NVIDIA US", "company": "NVIDIA", "type": "workday", "source_category": "us"},
                {"name": "JobsDB HK", "company": "JobsDB", "type": "jobsdb_hk", "source_category": "board", "fetch_via_cdp": True},
                {"name": "Disabled", "company": "Example", "type": "rss", "source_category": "us", "enabled": False},
            ]
        }

    def test_category_and_company_are_intersections(self) -> None:
        selected = select_sources(
            self.config,
            {"include_categories": ["us"], "include_companies": ["nvidia"]},
        )
        self.assertEqual([source["name"] for source in selected], ["NVIDIA US"])

    def test_browser_mode_separates_http_and_cdp(self) -> None:
        self.assertEqual(
            [source["name"] for source in select_sources(self.config, {"browser": "http"})],
            ["NVIDIA US"],
        )
        self.assertEqual(
            [source["name"] for source in select_sources(self.config, {"browser": "cdp"})],
            ["JobsDB HK"],
        )

    def test_disabled_sources_are_never_selected(self) -> None:
        self.assertEqual(select_sources(self.config, {"include_names": ["Disabled"]}), [])

    def test_invalid_browser_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_sources(self.config, {"browser": "magic"})


if __name__ == "__main__":
    unittest.main()
