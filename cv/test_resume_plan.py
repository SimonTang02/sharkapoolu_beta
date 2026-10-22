"""Regression cases for fact corrections, role selection and stale attachments."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cv.resume_plan import length_policy, plan_resume, render_plan, verify_bundle, verify_attachment_bundle
from cv.bot.bot import latex_escape, write_bundle


def fixture():
    facts = []
    texts = {'summary': 'Engineering student with reviewed academic projects.',
             'skills': 'Python; SystemVerilog',
             'rtl': 'Implemented an academic pipeline and tested hazard handling.',
             'memory': 'Compared memory model latency and energy in a team study.',
             'scope': 'Contributed benchmark scripts, with a limited code contribution.'}
    for ident, text in texts.items():
        facts.append({'id': ident, 'value': text, 'status': 'user_confirmed',
                      'source_id': 'report', 'confirmation': {'date': '2026-01-01', 'source': 'candidate'}})
    ledger = {'source_documents': [{'id': 'report', 'sha256': 'a'*64}], 'facts': facts}
    profile = {'identity': {'display_name': 'Alex Example', 'headline_name': 'Alex Example', 'email': 'alex@example.test'},
               'candidate_summary': 'OLD SUMMARY', 'closing_strength': 'OLD CLOSING',
               'tailored_summaries': {'default': 'Reviewed summary'}, 'evidence_groups': [],
               'resume_content': {'version': 1, 'summary_fact_ids': ['summary'], 'skill_fact_ids': ['skills'],
                   'projects': [
                       {'id': 'cpu', 'title': 'Academic processor', 'dates': '2025',
                        'keywords': ['RTL'], 'fact_ids': ['rtl', 'scope']},
                       {'id': 'mem', 'title': 'Memory models', 'dates': '2025',
                        'keywords': ['memory'], 'fact_ids': ['memory', 'scope']}]}}
    return profile, ledger


SOURCE = r'''Alex Example alex@example.test
\begin{rSection}{Summary}Old summary\end{rSection}
\begin{rSection}{Technical Skills}Old skills\end{rSection}
\begin{rSection}{Projects}OLD PROJECT CLAIM\end{rSection}
\begin{rSection}{Research Experience}DUPLICATE OLD RESEARCH\end{rSection}
'''


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.profile, self.ledger = fixture()
        self.policy = length_policy({}, 'Example')

    def plan(self, role='RTL Engineer', jd='RTL memory'):
        return plan_resume(self.profile, self.ledger, role, jd, self.policy)

    def test_job_changes_core_project_order(self):
        rtl, memory = self.plan(), self.plan('Memory Engineer')
        self.assertEqual(rtl['projects'][0]['id'], 'cpu')
        self.assertEqual(memory['projects'][0]['id'], 'mem')
        self.assertNotEqual(rtl['job_sha256'], memory['job_sha256'])

    def test_facts_deduplicated_and_old_research_removed(self):
        plan = self.plan()
        text = render_plan(SOURCE, plan, latex_escape)
        self.assertEqual(text.count('Contributed benchmark scripts'), 1)
        self.assertNotIn('OLD PROJECT CLAIM', text)
        self.assertNotIn('DUPLICATE OLD RESEARCH', text)
        self.assertEqual(plan['content_review'], 'pending')

    def test_conflicting_missing_and_unconfirmed_facts_block_generation(self):
        for change in ({'status': 'unresolved'}, {'superseded_by': 'new-fact'},
                       {'source_id': 'unknown'}, {'confirmation': {}}):
            with self.subTest(change=change):
                profile, ledger = fixture()
                ledger['facts'][-1].update(change)
                with self.assertRaises(ValueError):
                    plan_resume(profile, ledger, 'RTL', 'memory', self.policy)

    def test_new_confirmation_changes_plan_and_letter_statements(self):
        old = self.plan()
        self.ledger['facts'][-1]['value'] = 'Wrote benchmark scripts only.'
        new = self.plan()
        self.assertNotEqual(old['fact_ledger_sha256'], new['fact_ledger_sha256'])
        self.assertIn('Wrote benchmark scripts only.', render_plan(SOURCE, new, latex_escape))
        self.assertNotIn('limited code contribution', render_plan(SOURCE, new, latex_escape))

    def test_no_unrelated_project_fallback(self):
        with self.assertRaisesRegex(ValueError, 'No evidenced project'):
            self.plan('Sales Engineer', 'customer relationship')

    def test_company_guidance_requires_scope_source_and_check_date(self):
        rule = {'preferred_pages': 1, 'url': 'https://careers.example.test/resumes',
                'kind': 'official early-career recommendation', 'checked_on': '2026-01-01'}
        application = {'career_preferences': {'resume_language_policy': {
            'preferred_pages': 2, 'company_specific_length_guidance': {'Example': rule}}}}
        self.assertEqual(length_policy(application, 'Example')['preferred_pages'], 1)
        self.assertEqual(length_policy(application, 'Other')['preferred_pages'], 2)
        rule.pop('checked_on')
        with self.assertRaises(ValueError):
            length_policy(application, 'Example')

    def test_legacy_one_page_limit_remains_usable(self):
        application = {'career_preferences': {'resume_language_policy': {'max_pages_preferred': 1}}}
        self.assertEqual(length_policy(application, 'Example')['preferred_pages'], 1)

    def test_page_preference_changes_content_budget_without_padding(self):
        self.ledger['facts'][2]['value'] = ' '.join(['Reviewed'] * 200)
        self.ledger['facts'][3]['value'] = ' '.join(['Recorded'] * 200)
        two = self.plan()
        self.policy = length_policy({'career_preferences': {'resume_language_policy': {'preferred_pages': 1}}}, 'Example')
        one = self.plan()
        self.assertGreater(len(two['projects']), len(one['projects']))
        self.assertNotIn('new invented achievement', render_plan(SOURCE, one, latex_escape))

    def test_malformed_optional_configuration_is_actionable(self):
        for content in (None, [], {'version': 1, 'projects': [None]}):
            self.profile['resume_content'] = content
            with self.assertRaises(ValueError):
                self.plan()


class BundleTests(unittest.TestCase):
    def test_resume_letter_freshness_and_original_preservation(self):
        profile, ledger = fixture()
        def compile_stub(tex, build):
            build.mkdir(parents=True, exist_ok=True)
            pdf = build / (tex.stem + '.pdf')
            pdf.write_bytes(b'%PDF synthetic boundary fixture')
            (build/'resume.log').write_text('Output written on resume.pdf (2 pages, 10 bytes).')
            return pdf
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, ledger_path = root/'source.tex', root/'ledger.json'
            source.write_text(SOURCE)
            ledger_path.write_text(json.dumps(ledger))
            with patch('cv.bot.bot.compile_latex', side_effect=compile_stub), patch.dict('sys.modules', {'pypdf': None}):
                bundle = write_bundle(profile, 'Example', 'RTL', 'RTL memory', [], 'stale packet',
                                      source, root/'bundles', fact_ledger=ledger,
                                      input_paths=[ledger_path], keyword_selection={'available': False})
                manifest = bundle/'manifest.json'
                self.assertTrue(verify_bundle(manifest)['fresh'])
                self.assertEqual(verify_attachment_bundle(bundle/'build/resume.pdf'), manifest)
                self.assertEqual(verify_bundle(manifest)['content_review'], 'pending')
                self.assertIn('limited code contribution', (bundle/'cover_letter.tex').read_text())
                self.assertNotIn('OLD SUMMARY', (bundle/'cover_letter.tex').read_text())
                before = (bundle/'resume.tex').read_bytes()
                with self.assertRaises(FileExistsError):
                    write_bundle(profile, 'Example', 'RTL', 'RTL memory', [], '', source,
                                 root/'bundles', fact_ledger=ledger, keyword_selection={'available': False})
                self.assertEqual((bundle/'resume.tex').read_bytes(), before)
                self.assertEqual(source.read_text(), SOURCE)
                ledger['facts'][2]['value'] = 'Corrected scope.'
                ledger_path.write_text(json.dumps(ledger))
                with self.assertRaisesRegex(ValueError, 'changed'):
                    verify_bundle(manifest)
                with self.assertRaises(ValueError):
                    verify_attachment_bundle(bundle/'build/resume.pdf')

    def test_actual_pdf_identity_page_count_and_layout_rejections(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest('PDF extra not installed; core generation keeps PDF identity unknown')
        profile, ledger = fixture()
        for case in ('valid', 'wrong_identity', 'too_many_pages', 'missing_glyph'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root=Path(folder); source=root/'source.tex'; source.write_text(SOURCE)
                def compile_stub(tex, build):
                    build.mkdir(parents=True, exist_ok=True)
                    writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
                    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
                    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
                    stream=DecodedStreamObject()
                    name=b'Wrong Person' if case=='wrong_identity' else b'Alex Example alex@example.test'
                    stream.set_data(b'BT /F1 12 Tf 20 100 Td ('+name+b') Tj ET')
                    page[NameObject('/Contents')]=writer._add_object(stream)
                    if case=='too_many_pages':
                        writer.add_blank_page(width=600,height=800);writer.add_blank_page(width=600,height=800)
                    pdf=build/(tex.stem+'.pdf');writer.write(pdf)
                    (build/'resume.log').write_text('Missing character: example' if case=='missing_glyph' else '')
                    return pdf
                with patch('cv.bot.bot.compile_latex', side_effect=compile_stub):
                    if case=='valid':
                        bundle=write_bundle(profile,'Example','RTL','RTL memory',[],'',source,root/'bundles',fact_ledger=ledger,keyword_selection={'available':False})
                        result=json.loads((bundle/'manifest.json').read_text())
                        self.assertTrue(result['pdf_identity_validation'])
                        self.assertEqual(result['layout_review']['page_count'],1)
                    else:
                        with self.assertRaises(ValueError):
                            write_bundle(profile,'Example','RTL','RTL memory',[],'',source,root/'bundles',fact_ledger=ledger,keyword_selection={'available':False})

    def test_pdf_change_invalidates_bundle(self):
        # Reuse the integration setup with a minimal versioned manifest.
        from cv.resume_plan import file_hash
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); pdf = root/'resume.pdf'; pdf.write_bytes(b'original')
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'pipeline_version': 2, 'input_files': [],
                'output_files': [{'path': str(pdf), 'sha256': file_hash(pdf)}],
                'content_review': 'pending', 'candidate_review': 'pending',
                'layout_review': {'rendered_pdf_review': 'pending'}}))
            self.assertTrue(verify_bundle(manifest)['fresh'])
            pdf.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verify_bundle(manifest)
