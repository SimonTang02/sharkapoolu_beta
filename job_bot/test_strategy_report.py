import copy
import unittest
from pathlib import Path

from job_bot.bot import load_config
from job_bot.strategy_report import (
    DEFAULT_CONFIG,
    configure_strategy,
    foundation_override,
    strategy_score,
)


class StrategyConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_strategy(load_config(Path(DEFAULT_CONFIG)))

    def test_foundation_override_is_loaded_from_config(self) -> None:
        config = load_config(Path(DEFAULT_CONFIG))
        configure_strategy(config)
        self.assertEqual(foundation_override("DV Intern"), ("verification", 84))

    def test_strategy_score_modifiers_are_tunable(self) -> None:
        config = copy.deepcopy(load_config(Path(DEFAULT_CONFIG)))
        config["strategy"]["score_modifiers"] = [
            {"points": 9, "scope": "title", "pattern": "RTL"}
        ]
        config["strategy"]["stored_score_bonus"] = {"minimum": 70, "points": 0}
        configure_strategy(config)
        self.assertEqual(strategy_score(60, 90, "RTL Engineer", ""), 69)


if __name__ == "__main__":
    unittest.main()
