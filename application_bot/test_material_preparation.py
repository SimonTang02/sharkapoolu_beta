"""Synthetic regressions for private-path and confirmed-date preparation."""
from __future__ import annotations

import contextlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from application_bot import batch_campaign
from cv.bot.bot import render_tailored_resume


class MaterialPreparationTests(unittest.TestCase):
    def test_registered_profile_is_the_generated_private_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "private" / "outputs" / "application_bot"
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "manifest.json").write_text(json.dumps({
                "resume_pdf": str(bundle / "resume.pdf"),
                "cover_letter_pdf": str(bundle / "cover_letter.pdf"),
            }), encoding="utf-8")
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            self.addCleanup(conn.close)
            conn.executescript("""
                CREATE TABLE applications(id INTEGER, job_id INTEGER,
                    tailored_resume_path TEXT, cover_letter_path TEXT,
                    profile_path TEXT, status TEXT, updated_at TEXT);
                CREATE TABLE application_campaign_jobs(campaign_id INTEGER,
                    job_id INTEGER, application_id INTEGER, status TEXT,
                    material_bundle TEXT, last_error TEXT);
                CREATE TABLE application_campaigns(id INTEGER,
                    status TEXT, updated_at TEXT);
                INSERT INTO applications VALUES(7,1,NULL,NULL,NULL,'queued',NULL);
                INSERT INTO application_campaign_jobs VALUES(9,1,7,'selected',NULL,NULL);
                INSERT INTO application_campaigns VALUES(9,'selected',NULL);
            """)
            master = {"fields": {}, "documents": {}, "safety": {"allow_submit": False}}
            writer = Mock(return_value=bundle)

            def descriptions(_):
                db = sqlite3.connect(":memory:")
                db.execute("CREATE TABLE jobs(id INTEGER, description TEXT)")
                db.execute("INSERT INTO jobs VALUES(1,'Synthetic description')")
                db.executescript("""
                    CREATE TABLE applications(id INTEGER, job_id INTEGER, status TEXT);
                    CREATE TABLE application_campaign_jobs(campaign_id INTEGER, job_id INTEGER, application_id INTEGER, status TEXT);
                    CREATE TABLE application_campaigns(id INTEGER, status TEXT);
                    INSERT INTO applications VALUES(7,1,'queued');
                    INSERT INTO application_campaign_jobs VALUES(9,1,7,'selected');
                    INSERT INTO application_campaigns VALUES(9,'selected');
                """)
                return db

            replacements = {
                "APPLICATION_OUTPUT": output,
                "APPLICATION_PROFILE": Mock(read_text=Mock(return_value=json.dumps(master))),
                "EVIDENCE_PROFILE": Mock(read_text=Mock(return_value="{}")),
                "CURRENT_RESUME_TEX": Mock(read_text=Mock(return_value="Synthetic resume")),
                "DEFAULT_BUNDLES": root / "bundles",
                "connect_database": descriptions,
                "select_evidence": Mock(return_value=[]),
                "select_keywords": Mock(return_value={}),
                "render_report": Mock(return_value="Synthetic review"),
                "write_bundle": writer,
                "apply_keyword_selection": lambda p, _: p,
                "hydrate_known_resume_contacts": lambda p, _: p,
                "add_event": Mock(),
            }
            candidate = batch_campaign.Candidate(
                1, "Example", "Example Engineer", "Example City",
                "https://example.com/job/1", "full_time", 80, "", "example",
            )
            with contextlib.ExitStack() as stack:
                for name, value in replacements.items():
                    stack.enter_context(patch.object(batch_campaign, name, value))
                batch_campaign.prepare_materials(conn, 9, [candidate], workers=1)
            row = conn.execute("SELECT * FROM applications WHERE id=7").fetchone()
            registered = Path(row["profile_path"])
            self.assertEqual(registered, output / "applications" / "7" / "profile.json")
            self.assertTrue(registered.is_file())
            self.assertFalse(json.loads(registered.read_text())["safety"]["allow_submit"])
            self.assertEqual(row["status"], "queued")
            # Role category must never override the candidate's confirmed date.
            self.assertNotIn("graduation_date", writer.call_args.kwargs)

    def test_evidence_graduation_date_is_not_replaced_with_a_role_default(self):
        evidence = {
            "graduation_school": "Example University",
            "expected_graduation_date": "Nov 2031 (Expected)",
            "tailored_summaries": {"default": "Synthetic summary."},
        }
        source = (
            "\\begin{rSection}{Education}\n"
            "{\\bf Example University} \\hfill {\\em Jan 2030 -- Sep 2032 (Expected)} \\\\\n"
            "\\end{rSection}\n"
            "\\begin{rSection}{Summary}\nOld summary.\n\\end{rSection}\n"
        )
        rendered = render_tailored_resume(evidence, source, "Example Engineer", [])
        self.assertIn("Nov 2031 (Expected)", rendered)
        self.assertNotIn("Sep 2032 (Expected)", rendered)


if __name__ == "__main__":
    unittest.main()
