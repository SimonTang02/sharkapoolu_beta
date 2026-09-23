from __future__ import annotations

import copy
import argparse
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cv.application_keywords import select_keywords, apply_keyword_selection
from cv.bot.bot import render_report, render_tailored_resume, write_bundle
from cv.bot.test_bot import PROFILE


def fixture():
    def entry(i, label, status='supported_by_existing_records'):
        return dict(id=i, english=label, chinese='示例', evidence='Recorded project scope.',
                    example_en='Implemented a documented example.', source_ids=['example'], claim_status=status)
    return {'schema_version': 1, 'sources': {'example': {'path': 'fixture'}}, 'usage_rules': ['Keep scope.'],
            'technical_keywords': [entry('model', 'Behavioral Modeling'), entry('rtl', 'RTL Design'),
                                   entry('uvm', 'UVM', 'pending_confirmation')],
            'collaboration_personality_keywords': [entry('team', 'Teamwork', 'behavior_based_interpretation')],
            'role_presets': [
                {'id': 'architecture', 'role_match_terms': ['gpu architecture'], 'technical_ids': ['model'], 'collaboration_ids': ['team']},
                {'id': 'verification', 'role_match_terms': ['verification'], 'technical_ids': ['rtl', 'uvm'], 'collaboration_ids': ['team']}],
            }


class KeywordIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'keywords.json'
        self.data = fixture()
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data))

    def select(self, title='GPU Architecture', jd='', **kw):
        return select_keywords(title, jd, library_path=self.path, **kw)

    def test_title_beats_verification_heavy_jd(self):
        result = self.select(jd='verification ' * 20)
        self.assertEqual(result['preset'], 'architecture')
        self.assertEqual([x['id'] for x in result['technical']], ['model'])

    def test_pending_skills_and_jd_only_claims_are_excluded(self):
        result = self.select('Verification', 'UVM CUDA 10 years expert')
        self.assertEqual([x['id'] for x in result['technical']], ['rtl'])
        self.assertNotIn('CUDA', json.dumps(result['technical']))

    def test_unknown_role_has_no_unrelated_preset(self):
        result = self.select('Office Assistant', 'No technical requirements')
        self.assertIsNone(result['preset'])
        self.assertEqual(result['technical'], [])

    def test_literal_matches_allow_hyphenated_terms_without_substring_hits(self):
        self.data['technical_keywords'][0]['english'] = 'RISC-V'
        self.save()
        self.assertEqual(len(self.select('Engineer', 'RISC-V experience')['technical']), 1)
        self.assertEqual(self.select('Engineer', 'RISC-VX')['technical'], [])

    def test_manual_skills_and_sensitive_answers_preserved(self):
        profile = {'skills': ['Manual skill'], 'custom_answers': {'sponsorship': 'unconfirmed'},
                   'fields': {'country': 'existing'}, 'safety': {'allow_submit': False}}
        before = copy.deepcopy(profile)
        updated = apply_keyword_selection(profile, self.select())
        self.assertEqual(profile, before)
        for key in before:
            self.assertEqual(updated[key], before[key])
        self.assertIn('collaboration', updated['application_keywords'])
        self.assertNotIn('Teamwork', updated['skills'])

    def test_generated_skills_refresh_but_manual_edits_win(self):
        first = apply_keyword_selection({}, self.select())
        refreshed = apply_keyword_selection(first, self.select('Verification'))
        self.assertEqual(refreshed['skills'], ['RTL Design'])
        first['skills'].append('Manual skill')
        manual = apply_keyword_selection(first, self.select('Verification'))
        self.assertEqual(manual['skills'], ['Behavioral Modeling', 'Manual skill'])

    def test_missing_library_preserves_existing_skills(self):
        self.path.unlink()
        selection = self.select()
        self.assertFalse(selection['available'])
        self.assertEqual(apply_keyword_selection({'skills': ['Existing']}, selection)['skills'], ['Existing'])

    def test_invalid_preset_reference_fails(self):
        self.data['role_presets'][0]['technical_ids'] = ['invented']
        self.save()
        with self.assertRaises(ValueError):
            self.select()

    def test_keyword_without_evidence_fails(self):
        self.data['technical_keywords'][0]['evidence'] = ''
        self.save()
        with self.assertRaises(ValueError):
            self.select()

    def test_library_is_reread_not_cached(self):
        before = self.select()
        self.data['technical_keywords'][0]['example_en'] = 'Updated evidence sentence.'
        self.save()
        after = self.select()
        self.assertNotEqual(before['library_sha256'], after['library_sha256'])
        self.assertEqual(after['technical'][0]['example_en'], 'Updated evidence sentence.')

    def test_cv_bundle_and_report_use_same_selection(self):
        selection = self.select()
        source = self.root / 'source.tex'
        source.write_text(r'''\begin{rSection}{Summary}
Old summary.
\end{rSection}
\begin{rSection}{Technical Skills}
Old technical list.
\end{rSection}
\begin{rSection}{Projects}
Preserve project evidence.
\end{rSection}''')
        report = render_report(PROFILE, 'Example', 'GPU Architecture', '', [], 'fixture', keyword_selection=selection)
        self.assertIn('Keep scope.', report)
        self.assertIn('Teamwork', report)
        with patch('cv.bot.bot.compile_latex', side_effect=lambda tex, build: build / (tex.stem + '.pdf')):
            bundle = write_bundle(PROFILE, 'Example', 'GPU Architecture', '', [], report,
                                  source, self.root / 'bundles', keyword_selection=selection)
        rendered = (bundle / 'resume.tex').read_text()
        self.assertIn('Behavioral Modeling', rendered)
        self.assertNotIn('Old technical list.', rendered)
        self.assertNotIn('Teamwork', rendered)
        self.assertIn('Preserve project evidence.', rendered)
        self.assertIn('Old technical list.', source.read_text())
        manifest = json.loads((bundle / 'manifest.json').read_text())
        self.assertEqual(json.loads(Path(manifest['application_keywords']).read_text()), selection)

    def test_latex_special_characters_are_escaped(self):
        selection = self.select()
        selection['technical'][0]['resume_label'] = 'Modeling & Analysis_1'
        source = r'\begin{rSection}{Summary}Old\end{rSection}\begin{rSection}{Technical Skills}Old\end{rSection}'
        rendered = render_tailored_resume(PROFILE, source, 'Example', [], keyword_selection=selection)
        self.assertIn(r'Modeling \& Analysis\_1', rendered)

    def test_application_prepare_profile_reads_library_and_keeps_answers(self):
        from job_bot.application_bot import cmd_prepare_profile
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.executescript('''
            CREATE TABLE jobs(id INTEGER, title TEXT, description TEXT);
            CREATE TABLE applications(id INTEGER, job_id INTEGER, tailored_resume_path TEXT,
                cover_letter_path TEXT, profile_path TEXT, updated_at TEXT);
            INSERT INTO jobs VALUES(1, 'GPU Architecture', 'Behavioral Modeling');
            INSERT INTO applications(id, job_id) VALUES(1, 1);
        ''')
        master = self.root / 'profile.json'
        master.write_text(json.dumps({
            'schema_version': 1,
            'fields': {},
            'documents': {},
            'custom_answers': {'sponsorship': 'pending'},
            'safety': {
                'allow_sensitive_answers': False,
                'allow_server_draft': False,
                'allow_submit': False,
            },
        }))
        source = self.root / 'source.tex'
        source.write_text('')
        resume = self.root / 'resume.pdf'
        resume.touch()
        cover = self.root / 'cover.pdf'
        cover.touch()
        args = argparse.Namespace(config='unused', application_id=1, base_profile=str(master),
                                  resume=str(resume), cover_letter=str(cover))
        with patch('job_bot.application_bot.load_config', return_value={}), \
             patch('job_bot.application_bot.connect_db', return_value=conn), \
             patch('job_bot.application_bot.add_event'), \
             patch('job_bot.application_bot.ROOT', self.root), \
             patch('job_bot.application_bot.CURRENT_RESUME_TEX', source), \
             patch('cv.application_keywords.APPLICATION_KEYWORDS', self.path):
            cmd_prepare_profile(args)
        saved = Path(conn.execute('SELECT profile_path FROM applications').fetchone()[0])
        profile = json.loads(saved.read_text())
        self.assertEqual(profile['skills'], ['Behavioral Modeling'])
        self.assertEqual(profile['application_keywords']['preset'], 'architecture')
        self.assertEqual(profile['custom_answers'], {'sponsorship': 'pending'})
        self.assertFalse(profile['safety']['allow_submit'])


if __name__ == '__main__':
    unittest.main()
