import copy
import sqlite3
import unittest
from pathlib import Path

from job_bot.bot import load_config
from job_bot.strategy_report import (
    DEFAULT_CONFIG,
    configure_strategy,
    collect,
    foundation_override,
    strategy_score,
    sync_strategy_reviews,
)


class StrategyConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_strategy(load_config(Path(DEFAULT_CONFIG)))

    def test_foundation_override_is_loaded_from_config(self) -> None:
        config = load_config(Path(DEFAULT_CONFIG))
        configure_strategy(config)
        self.assertEqual(foundation_override("DV Intern"), ("verification", 54))

    def test_strategy_score_modifiers_are_tunable(self) -> None:
        config = copy.deepcopy(load_config(Path(DEFAULT_CONFIG)))
        config["strategy"]["score_modifiers"] = [
            {"points": 9, "scope": "title", "pattern": "RTL"}
        ]
        config["strategy"]["stored_score_bonus"] = {"minimum": 70, "points": 0}
        configure_strategy(config)
        self.assertEqual(strategy_score(60, 90, "RTL Engineer", ""), 69)

    def test_review_queue_favors_design_and_preserves_submission_state(self) -> None:
        config = load_config(Path(DEFAULT_CONFIG))
        configure_strategy(config)
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE jobs (
                 id INTEGER PRIMARY KEY, company TEXT, title TEXT, location TEXT,
                 url TEXT, role_kind TEXT, recruitment_category TEXT,
                 description TEXT, status TEXT,
                 fit_score INTEGER, source_name TEXT, first_seen TEXT, is_active INTEGER
               )"""
        )
        conn.execute("CREATE TABLE applications (id INTEGER PRIMARY KEY, job_id INTEGER, status TEXT, submitted_at TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE application_limits (company TEXT, category TEXT, max_applications INTEGER, window_start TEXT, window_end TEXT, enforcement TEXT)")
        rows = [
            (1, "ChipCo", "NPU IP设计工程师", "上海", "https://x/1", "full_time", "2027_campus", "2027届秋招", "new", 0, "Campus", "2026-09-26", 1),
            (2, "ChipCo", "数字芯片验证工程师", "上海", "https://x/2", "full_time", "2027_campus", "2027届秋招", "new", 80, "Campus", "2026-09-26", 1),
            (3, "QuantCo", "Graduate Hardware Engineer", "Chicago, IL", "https://x/3", "full_time", "", "", "new", 80, "Handshake", "2026-09-26", 1),
            (4, "FPGA Co", "FPGA Engineering Intern - Summer 2027", "Needham, MA", "https://x/4", "internship", "", "Masters welcome", "new", 80, "Handshake", "2026-09-26", 1),
            (5, "ChipCo", "数字IC设计工程师", "上海", "https://x/5", "full_time", "2027_campus", "2027届", "applied", 80, "Campus", "2026-09-26", 1),
            (6, "Xiaomi", "NPU芯片设计工程师", "北京", "https://x/6", "full_time", "2027_campus", "2027届", "new", 80, "Campus", "2026-09-26", 1),
            (7, "Xiaomi", "数字芯片设计工程师", "北京", "https://x/7", "full_time", "2027_campus", "2027届", "applied", 80, "Campus", "2026-09-26", 1),
            (8, "FPGA Co", "FPGA Intern - Summer 2027", "Needham, MA", "https://x/8", "internship", "", "Graduation after November 2027", "eligibility_blocked", 80, "Handshake", "2026-09-26", 1),
            (9, "FPGA Co", "FPGA Research Intern", "Needham, MA", "https://x/9", "internship", "", "From September 2026 to March 2027", "new", 80, "Handshake", "2026-09-26", 1),
            (10, "Moore Threads", "GPU Architecture Engineer", "上海", "https://x/10", "full_time", "2027_campus", "2027届", "new", 80, "Campus", "2026-09-26", 1),
            (11, "Moore Threads", "Digital IC Design Engineer", "上海", "https://x/11", "full_time", "2027_campus", "2027届", "new", 80, "Campus", "2026-09-26", 1),
            (12, "Moore Threads", "Hardware Engineer", "上海", "https://x/12", "full_time", "2027_campus", "2027届", "new", 80, "Campus", "2026-09-26", 1),
            (13, "Moore Threads", "ASIC Design Engineer", "上海", "https://x/13", "full_time", "2027_campus", "2027届", "applied", 80, "Campus", "2026-09-26", 1),
        ]
        conn.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.executemany("INSERT INTO applications VALUES (?,?,?,?,?)", [
            (5, 5, "submitted", "2026-09-26", "2026-09-26"),
            (7, 7, "submitted", "2026-09-26", "2026-09-26"),
            (13, 13, "submitted", "2026-09-26", "2026-09-26"),
        ])
        conn.execute("INSERT INTO application_limits VALUES ('Xiaomi','2027_campus',1,'2020-01-01','2030-12-31','hard')")
        conn.execute("INSERT INTO application_limits VALUES ('Moore Threads','2027_campus',3,'2020-01-01','2030-12-31','hard')")
        campus, grad, intern, stats = collect(conn)
        self.assertEqual([x.job_id for x in campus], [10, 11, 1])
        self.assertEqual([x.job_id for x in grad], [3])
        self.assertEqual([x.job_id for x in intern], [4])
        self.assertEqual(campus[-1].foundation, "accelerator_design")
        self.assertEqual(intern[0].foundation, "fpga_design")
        self.assertEqual(stats["verification_held"], 1)
        self.assertEqual(stats["company_limit_held"], 1)
        self.assertEqual(stats["remaining_slots_held"], 1)
        policy_hash = sync_strategy_reviews(conn, config, campus + grad + intern)
        self.assertEqual(len(policy_hash), 64)
        self.assertEqual(conn.execute("SELECT count(*) FROM job_strategy_reviews").fetchone()[0], 5)
        self.assertEqual(conn.execute("SELECT status FROM applications WHERE job_id=5").fetchone()[0], "submitted")


if __name__ == "__main__":
    unittest.main()
