import json
import unittest
from pathlib import Path

from application_bot.portal_registry import (
    adapter_command,
    resolve_adapter,
    resolve_adapter_by_url,
    resolve_company_profile,
)


CONFIG = {
    "portals": {
        "company_profiles": [{
            "id": "nvidia_workday", "priority": 10, "adapter": "workday",
            "company_patterns": ["^NVIDIA$"], "rules": {"tenant": "nvidia"},
        }],
        "adapters": [
            {
                "id": "amd",
                "priority": 100,
                "company_patterns": ["^AMD$"],
                "host_suffixes": ["careers.amd.com"],
                "script": "application_bot/amd_icims.py",
                "env_option": "--env",
            },
            {
                "id": "workday",
                "priority": 50,
                "platforms": ["workday"],
                "host_suffixes": ["myworkdayjobs.com"],
                "script": "application_bot/cli.py",
                "subcommand": "workday-preview",
                "env_option": "--env-file",
                "timeout_seconds": 420,
            },
        ]
    }
}


class PortalRegistryTests(unittest.TestCase):
    def test_company_specific_adapter_wins(self) -> None:
        adapter = resolve_adapter(
            CONFIG,
            company="AMD",
            platform="jibe",
            url="https://careers.amd.com/careers-home/jobs/123",
        )
        self.assertEqual(adapter.id, "amd")

    def test_workday_is_selected_by_platform_and_host(self) -> None:
        adapter = resolve_adapter(
            CONFIG,
            company="NVIDIA",
            platform="workday",
            url="https://nvidia.wd5.myworkdayjobs.com/site/job/1",
        )
        self.assertEqual(adapter.id, "workday")
        self.assertEqual(adapter.timeout_seconds, 420)

    def test_command_is_argument_vector_not_shell_text(self) -> None:
        adapter = resolve_adapter(
            CONFIG,
            company="NVIDIA",
            platform="workday",
            url="https://nvidia.wd5.myworkdayjobs.com/site/job/1",
        )
        command = adapter_command(
            adapter,
            application_id=7,
            config_path=Path("config.json"),
            env_path=Path("passport.env"),
        )
        self.assertIn("workday-preview", command)
        self.assertIn("7", command)
        self.assertIn("--env-file", command)

    def test_url_only_resolution_supports_open_tab_audit(self) -> None:
        adapter = resolve_adapter_by_url(
            CONFIG, "https://nvidia.wd5.myworkdayjobs.com/site/userHome"
        )
        self.assertEqual(adapter.id, "workday")

    def test_company_profile_layers_over_shared_adapter(self) -> None:
        profile = resolve_company_profile(
            CONFIG, company="NVIDIA", adapter_id="workday"
        )
        self.assertEqual(profile["id"], "nvidia_workday")
        self.assertEqual(profile["rules"]["tenant"], "nvidia")


class ConfiguredStandardAtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.config = json.loads(
            (cls.root / "job_bot" / "config" / "portals.json").read_text(encoding="utf-8")
        )

    def test_standard_ats_adapters_and_profiles_are_registered(self) -> None:
        cases = [
            (
                "Cirrus Logic",
                "lever",
                "https://jobs.eu.lever.co/cirrus/639a7c66-76c4-4c22-9b9f-43af17595103",
                "lever",
                "application_bot/lever.py",
                "cirrus_lever",
            ),
            (
                "Astera Labs",
                "greenhouse",
                "https://job-boards.greenhouse.io/asteraearlycareer2027/jobs/4731399005",
                "greenhouse",
                "application_bot/greenhouse.py",
                "astera_greenhouse",
            ),
            (
                "Etched",
                "ashby",
                "https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d",
                "ashby",
                "application_bot/ashby.py",
                "etched_ashby",
            ),
        ]
        for company, platform, url, adapter_id, script, profile_id in cases:
            adapter = resolve_adapter(self.config, company=company, platform=platform, url=url)
            self.assertIsNotNone(adapter, company)
            self.assertEqual(adapter.id, adapter_id)
            self.assertEqual(adapter.script, script)
            self.assertFalse(adapter.supports_draft)
            self.assertEqual(adapter.session_probe.get("kind"), "application_url")
            self.assertTrue((self.root / script).is_file())
            profile = resolve_company_profile(self.config, company=company, adapter_id=adapter_id)
            self.assertEqual(profile.get("id"), profile_id)

    def test_new_adapter_command_uses_its_script_and_env(self) -> None:
        adapter = resolve_adapter(
            self.config,
            company="Etched",
            platform="ashby",
            url="https://jobs.ashbyhq.com/etched/5f1f5739-3b58-467c-b351-ff183c94d96d",
        )
        command = adapter_command(
            adapter,
            application_id=11,
            config_path=Path("config.json"),
            env_path=Path("passport.env"),
        )
        self.assertIn("application_bot/ashby.py", command[1])
        self.assertIn("--env", command)
        self.assertIn("11", command)
        self.assertIn("--application-id", command)


if __name__ == "__main__":
    unittest.main()
