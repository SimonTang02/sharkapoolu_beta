import json
from pathlib import Path
import tempfile
import unittest

from job_bot.campus_employment_report import estimate_income, render_campus_employment


class CampusIncomeTests(unittest.TestCase):
    def test_average_month_and_range(self):
        self.assertEqual(estimate_income([18, 20], [10, 15]),
                         {"monthly_hours": [43.3, 65.0], "monthly_gross_usd": [780.0, 1300.0]})

    def test_missing_or_invalid_pay_is_not_zero_or_invented(self):
        for pay in (None, [20, 10], [-1, 20], [float('nan'), 20], [True, 20]):
            self.assertIsNone(estimate_income(pay, [10, 15])["monthly_gross_usd"])
        self.assertIsNone(estimate_income([15, 15], None)["monthly_hours"])

    def test_live_jobs_are_included_but_unpaid_research_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'penn_channels').mkdir()
            (root / 'penn_channels/campus_refresh.json').write_text(json.dumps({
                'checked_at': '2026-09-18',
                'coverage': [{'name': 'Workday', 'result': '需要重新登录'}]}))
            (root / 'penn_channels/latest.json').write_text(json.dumps({
                'opportunities': [
                    {'title': 'Student assistant', 'url': 'https://example.com/job', 'kind': 'campus_job', 'hourly_usd': [18, 18], 'weekly_hours': [5, 10]},
                    {'title': 'Unverified research', 'url': 'https://example.com/research', 'kind': 'research_lead'}]}))
            lines, payload = render_campus_employment({'penn_channels': {'campus_employment': {'enabled': True}}}, root)
            text = '\n'.join(lines)
            self.assertIn('$390.00–780.00', text)
            self.assertNotIn('Unverified research', text)
            self.assertEqual(len(payload['leads']), 1)
            self.assertIn('假设，非岗位报价', text)
            self.assertIn('需要重新登录', text)
            self.assertEqual(payload['refresh']['checked_at'], '2026-09-18')


if __name__ == '__main__':
    unittest.main()
