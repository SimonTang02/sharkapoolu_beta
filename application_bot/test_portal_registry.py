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


if __name__ == "__main__":
    unittest.main()
