"""Candidate-free, offline regression tests for narrow EDA retrieval scoring."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from job_bot.bot import JobPosting, score_job


def fixture_config() -> dict:
    return {
        "scoring": {
            "algorithm": "foundation_v2",
            "foundation_secondary_bonus": 0,
            "foundation_groups": [
                {
                    "name": "EDA and logic synthesis",
                    "base_score": 70,
                    "body_only_adjustment": -8,
                    "min_body_hits": 2,
                    "keywords": ["EDA", "electronic design automation", "logic synthesis"],
                },
                {
                    "name": "digital RTL design",
                    "base_score": 72,
                    "body_only_adjustment": -8,
                    "min_body_hits": 2,
                    "keywords": ["RTL", "Verilog", "digital design"],
                },
            ],
            "modifiers": [
                {"name": "software-first role", "points": -45, "scope": "title",
                 "keywords": ["software", "infrastructure", "软件"]},
                {"name": "internship", "points": 8, "scope": "title",
                 "keywords": ["intern", "实习"]},
                {"name": "seniority mismatch", "points": -45, "scope": "title",
                 "keywords": ["senior", "principal"]},
                {"name": "non-design function", "points": -70, "scope": "title",
                 "keywords": ["sales", "support"]},
            ],
        }
    }


def posting(title: str, description: str, company: str = "Example Company") -> JobPosting:
    return JobPosting("synthetic fixture", company, title, "https://example.invalid/job",
                      description=description)


CORE_DESCRIPTION = (
    "Our team develops IC design and verification solutions including Conformal LEC. "
    "Implement C++ algorithms for logic synthesis and simulation engines."
)


class EDAScoringTests(unittest.TestCase):
    def test_core_tool_algorithm_families_receive_narrow_exception(self) -> None:
        cases = [
            ("Software Engineering Intern",
             "Research and develop new technology for speeding up large transistor circuit "
             "simulation in Spectre FX (FastSPICE). Program in C/C++.", 70),
            ("Software Engineer II",
             "Join the Innovus team. Design, implement, and optimize algorithms for physical "
             "synthesis, placement, and routing engines. Develop C++ software.", 62),
            ("Software Engineer for SPICE",
             "Develop mathematical and probabilistic algorithms for simulation engines and "
             "numerical methods for EDA technologies. Implement in Python and C++.", 62),
            ("Software Intern",
             "Research and develop on-chip parasitic modeling with machine learning. "
             "Strong algorithms and C/C++ implementation skills.", 70),
            ("Software Engineer II", CORE_DESCRIPTION, 62),
            ("Algorithm Software Engineer",
             "Develop SAT solving algorithms for electronic design automation. "
             "Implement numerical methods and solver algorithms in C++.", 62),
        ]
        for title, description, minimum in cases:
            with self.subTest(title=title, description=description[:35]):
                score, reason = score_job(posting(title, description), fixture_config())
                self.assertGreaterEqual(score, minimum)
                self.assertIn("Evidence: EDA tool/algorithm development", reason)
                self.assertIn("Exception: software-first role", reason)
                self.assertNotIn("software, -45", reason)

    def test_mesh_and_cae_are_lower_confidence_than_core_tools(self) -> None:
        cases = [
            "Responsibilities\nDevelop new features according to product specifications.\n"
            "Basic Qualifications\nC/C++ development and algorithms.\n"
            "Preferred Qualifications\nMesh related algorithm and EDA application development.",
            "Research and develop approaches for geometry modeling and mesh generation. "
            "Algorithms and C++/Python. Exposure to EDA and CAE applications.",
        ]
        core_score, _ = score_job(posting("Software Engineer", CORE_DESCRIPTION), fixture_config())
        for description in cases:
            with self.subTest(description=description[:35]):
                score, reason = score_job(posting("Software Engineer", description), fixture_config())
                self.assertEqual(score, core_score - 8)
                self.assertIn("Evidence: EDA/CAE algorithm development", reason)
                self.assertIn("Exception: software-first role", reason)

    def test_incidental_eda_mentions_do_not_qualify(self) -> None:
        cases = [
            "Develop C++ web services for accounts that use EDA and logic synthesis tools.",
            "Develop C++ algorithms for distributed caches. Our customers use Innovus and EDA.",
            "Use SPICE and Innovus to design circuits. Maintain Python application code.",
            "We make EDA tools. Develop Python dashboards and application monitoring.",
            "The company develops EDA tools and simulation engines. Build a C++ dashboard.",
            "C++ and EDA knowledge required. Integrate a software library with Innovus.",
            "Develop ML recommender algorithms in Python. Experience with EDA tools is a plus.",
            "Develop C++ recommendation algorithms\nUse SPICE circuit simulation tools\n",
        ]
        for description in cases:
            with self.subTest(description=description):
                _, reason = score_job(posting("Software Engineer", description), fixture_config())
                self.assertNotIn("Evidence: EDA", reason)
                self.assertNotIn("Exception:", reason)

    def test_qa_dv_fae_and_generic_infrastructure_titles_are_not_exempt(self) -> None:
        titles = [
            "Software QA Engineer", "Software Test Engineer", "Software SDET Engineer",
            "Software Design Verification Intern", "Software DV Intern", "Software PV Intern",
            "Software Product Validation Engineer", "Software Customer Support Engineer",
            "Software Applications Engineer", "Software FAE Engineer", "EDA Software Sales",
            "Embedded Software Engineer", "Firmware Software Engineer", "Web Software Engineer",
            "Cloud Software Engineer", "DevOps Software Engineer", "Full-stack Software Engineer",
            "Front-end Software Engineer", "Back-end Software Engineer", "软件测试工程师",
        ]
        for title in titles:
            with self.subTest(title=title):
                _, reason = score_job(posting(title, CORE_DESCRIPTION), fixture_config())
                self.assertNotIn("Evidence: EDA", reason)
                self.assertNotIn("Exception:", reason)

    def test_hidden_qa_duties_do_not_pass_a_generic_software_title(self) -> None:
        cases = [
            "Develop C++ regression tests for Innovus simulation engines and EDA tools.",
            "Design test harnesses for SPICE simulation engines. C++ and EDA algorithms.",
            "Implement testbench algorithms for Conformal verification. C++ and EDA.",
            "Develop tutorial examples for EDA circuit simulation engines in Python.",
            "Join the QA team. Our team develops IC design and verification solutions "
            "including Conformal. Use C++ to produce regression tests.",
        ]
        for description in cases:
            with self.subTest(description=description):
                _, reason = score_job(posting("Software Engineer", description), fixture_config())
                self.assertNotIn("Exception:", reason)

    def test_qualification_only_tool_development_is_insufficient(self) -> None:
        for heading in ["Requirements:", "Requirements", "Position Requirements:",
                        "Basic Qualifications", "Required Qualifications"]:
            with self.subTest(heading=heading):
                description = (
                    "Maintain customer web accounts.\n" + heading + "\n"
                    "Experience developing algorithms for EDA simulation engines in C++.")
                _, reason = score_job(posting("Software Engineer", description), fixture_config())
                self.assertNotIn("Exception:", reason)

    def test_negated_ownership_is_not_development_evidence(self) -> None:
        cases = [
            "Do not develop algorithms for EDA simulation engines. Use C++ for reporting.",
            "Use rather than develop numerical methods for SPICE simulation engines. C++.",
            "We do not research and develop technology for speeding up SPICE circuit. C++.",
            "Do not develop new features according to mesh product specifications. "
            "C++ algorithms for EDA mesh applications.",
        ]
        for description in cases:
            with self.subTest(description=description):
                _, reason = score_job(posting("Software Engineer", description), fixture_config())
                self.assertNotIn("Exception:", reason)

    def test_incomplete_jd_and_vendor_name_alone_are_insufficient(self) -> None:
        for description in ["", "SPICE", "EDA and logic synthesis.",
                            "Join the Conformal AI solution team. C++ preferred."]:
            with self.subTest(description=description):
                _, reason = score_job(posting("Software Engineer", description, "Cadence"), fixture_config())
                self.assertNotIn("Exception:", reason)

    def test_company_identity_does_not_control_the_exception(self) -> None:
        result = score_job(posting("Software Engineer", CORE_DESCRIPTION), fixture_config())
        self.assertEqual(result, score_job(posting("Software Engineer", CORE_DESCRIPTION, ""), fixture_config()))

    def test_html_case_and_whitespace_are_normalized(self) -> None:
        description = "<p>Our team DEVELOPS IC design and verification solutions: CONFORMAL.</p><p>C++.</p>"
        score, reason = score_job(posting("SOFTWARE Engineer", description), fixture_config())
        self.assertEqual(score, 62)
        self.assertIn("Exception:", reason)

    def test_seniority_and_other_negative_policy_remain_effective(self) -> None:
        config = fixture_config()
        junior, _ = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        senior, reason = score_job(posting("Senior Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(senior, junior - 45)
        self.assertIn("Modifier: seniority mismatch", reason)
        config["scoring"]["modifiers"].append(
            {"name": "explicit campaign exclusion", "scope": "title", "points": -100,
             "keywords": ["software"]})
        score, reason = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(score, 0)
        self.assertIn("Modifier: explicit campaign exclusion", reason)

    def test_only_named_negative_software_modifier_is_exempt(self) -> None:
        config = fixture_config()
        config["scoring"]["modifiers"][0]["name"] = "another software rule"
        score, reason = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(score, 17)
        self.assertNotIn("Exception:", reason)
        config["scoring"]["modifiers"][0].update(name="software-first role", points=3)
        score, reason = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(score, 65)
        self.assertIn("Modifier: software-first role", reason)

    def test_no_eda_foundation_means_no_policy_exception(self) -> None:
        config = fixture_config()
        config["scoring"]["foundation_groups"] = config["scoring"]["foundation_groups"][1:]
        score, reason = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(score, 0)
        self.assertNotIn("Exception:", reason)

    def test_foundation_weights_and_custom_minimum_remain_configured(self) -> None:
        config = fixture_config()
        config["scoring"]["foundation_groups"][0].update(base_score=40, min_body_hits=5)
        score, _ = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(score, 32)

    def test_non_eda_rtl_and_generic_swe_scores_stay_unchanged(self) -> None:
        config = fixture_config()
        score, reason = score_job(posting("RTL Design Engineer", "Implement digital design in Verilog."), config)
        self.assertEqual(score, 72)
        self.assertNotIn("Exception:", reason)
        score, reason = score_job(posting("Software Engineer", "Use EDA and logic synthesis tools."), config)
        self.assertEqual(score, 17)
        self.assertNotIn("Exception:", reason)

    def test_weighted_keyword_compatibility_path_is_not_changed(self) -> None:
        config = {"scoring": {"algorithm": "weighted_keywords_v1", "keyword_groups": [
            {"name": "EDA", "keywords": ["EDA"], "weight": 12}]}}
        with patch("job_bot.bot.eda_development_evidence", side_effect=AssertionError("unexpected classifier")):
            score, reason = score_job(posting("Software Engineer", "Develop EDA algorithms in C++."), config)
        self.assertEqual(score, 12)
        self.assertIn("Matched: EDA", reason)

    def test_scoring_is_pure_and_does_not_mutate_policy(self) -> None:
        config = fixture_config()
        original = copy.deepcopy(config)
        with patch("job_bot.bot.connect_database", side_effect=AssertionError("database access")), \
             patch("job_bot.bot.urllib.request.urlopen", side_effect=AssertionError("network access")):
            score, _ = score_job(posting("Software Engineer", CORE_DESCRIPTION), config)
        self.assertEqual(score, 62)
        self.assertEqual(config, original)


if __name__ == "__main__":
    unittest.main()
