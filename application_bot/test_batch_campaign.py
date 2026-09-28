from __future__ import annotations

import unittest
import sqlite3

from application_bot.batch_campaign import (
    Candidate,
    direction_priority,
    load_explicit_candidates,
    normalized_role_key,
)


class BatchCampaignTests(unittest.TestCase):
    def test_preference_order(self) -> None:
        self.assertEqual(direction_priority("Foundation: digital RTL design"), 0)
        self.assertEqual(direction_priority("Foundation: CPU and computer architecture"), 0)
        self.assertEqual(direction_priority("Foundation: RTL and silicon verification"), 3)
        self.assertEqual(direction_priority("Foundation: physical design and DFT"), 2)

    def test_normalized_duplicate_key(self) -> None:
        base = dict(
            job_id=1,
            company="Example",
            title="Digital IC Design Engineer",
            location="Shanghai, China",
            url="https://example.com/1",
            role_kind="full_time",
            score=80,
            score_reason="Foundation: digital RTL design",
            platform="example",
        )
        first = Candidate(**base)
        second = Candidate(**{**base, "job_id": 2, "title": "Digital-IC Design Engineer"})
        self.assertEqual(normalized_role_key(first), normalized_role_key(second))

    def test_explicit_candidates_preserve_reviewed_order(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE jobs(
              id INTEGER PRIMARY KEY, company TEXT, title TEXT, location TEXT,
              url TEXT, role_kind TEXT, fit_score INTEGER, score_reason TEXT,
              platform TEXT, is_active INTEGER
            )
            """
        )
        conn.executemany(
            "INSERT INTO jobs VALUES (?, ?, ?, '', ?, 'internship', 80, '', 'workday', 1)",
            [(1, "A", "One", "https://a/1"), (2, "B", "Two", "https://b/2")],
        )
        selected = load_explicit_candidates(conn, [2, 1])
        self.assertEqual([item.job_id for item in selected], [2, 1])

    def test_explicit_candidates_reject_inactive_job(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE jobs(
              id INTEGER PRIMARY KEY, company TEXT, title TEXT, location TEXT,
              url TEXT, role_kind TEXT, fit_score INTEGER, score_reason TEXT,
              platform TEXT, is_active INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO jobs VALUES (1, 'A', 'One', '', 'https://a/1', 'full_time', 80, '', 'x', 0)"
        )
        with self.assertRaises(ValueError):
            load_explicit_candidates(conn, [1])


if __name__ == "__main__":
    unittest.main()
