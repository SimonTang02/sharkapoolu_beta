from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from cv.resume_import import import_resume,editable_draft,extract_pdf
from cv.bot.bot import main as cv_main,compile_latex


class ResumeIntakeTests(unittest.TestCase):
    def test_original_bytes_draft_escape_and_provenance_without_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.txt';source.write_text('Example Name\nPython & SQL 50%\n\\input{untrusted}\n中文简历',encoding='utf-8')
            before=source.read_bytes()
            with patch('cv.resume_import.PRIVATE_ROOT',root): output=import_resume(source,root/'private/intake')
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual((output/'original.txt').read_bytes(),before)
            draft=(output/'resume_draft.tex').read_text(encoding='utf-8')
            self.assertIn(r'Python \& SQL 50\%',draft)
            self.assertNotIn(r'\input{untrusted}',draft)
            self.assertIn(r'\usepackage{xeCJK}',draft)
            manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['sha256'],hashlib.sha256(before).hexdigest())
            self.assertFalse(manifest['application_ready'])
            self.assertEqual(json.loads((output/'fact_ledger.json').read_text(encoding='utf-8'))['facts'],[])
            instruction=(output/'AGENT_TASK.md').read_text(encoding='utf-8')
            self.assertIn('docs/candidate-onboarding.md',instruction)
            self.assertIn('docs/manual-database.md',instruction)
            self.assertIn('最终提交由本人',instruction)

    def test_scanned_or_partly_scanned_pdf_is_manual_review_not_empty_fact(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.pdf';source.write_bytes(b'%PDF synthetic')
            with patch('cv.resume_import.PRIVATE_ROOT',root),patch('cv.resume_import.extract_pdf',return_value=['Example education','']): output=import_resume(source,root/'out')
            manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['text_extraction'],'visual_read_or_ocr_required')
            self.assertEqual(manifest['page_count'],2)
            self.assertFalse(manifest['application_ready'])

    def test_existing_output_and_public_output_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.txt';source.write_text('Example')
            current=root/'private/current.tex';current.parent.mkdir();current.write_text('Reviewed existing source')
            with patch('cv.resume_import.PRIVATE_ROOT',root/'private'):
                with self.assertRaises(ValueError): import_resume(source,root/'outside')
                with self.assertRaises(ValueError): import_resume(source,current.parent)
            self.assertEqual(current.read_text(),'Reviewed existing source')

    def test_tex_original_not_executed_or_restructured_automatically(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.tex';source.write_text(r'\documentclass{article}\input{unknown}')
            with patch('cv.resume_import.PRIVATE_ROOT',root): output=import_resume(source,root/'out')
            self.assertEqual((output/'resume_draft.tex').read_bytes(),source.read_bytes())
            self.assertFalse(json.loads((output/'manifest.json').read_text())['application_ready'])

    def test_pdf_optional_component_failure_is_actionable(self):
        with patch.dict('sys.modules',{'pypdf':None}):
            with self.assertRaisesRegex(ValueError,'简历组件'): extract_pdf(Path('synthetic.pdf'))

    def test_real_pdf_text_and_image_only_detection_when_extra_present(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        except ImportError:
            self.skipTest('PDF extra not installed; core tests remain dependency-free')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.pdf';writer=PdfWriter();page=writer.add_blank_page(width=300,height=200)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 20 100 Td (Example Name - Python and SQL) Tj ET')
            page[NameObject('/Contents')]=writer._add_object(content);writer.add_blank_page(width=300,height=200)
            writer.write(path)
            texts=extract_pdf(path)
            self.assertIn('Example Name',texts[0]);self.assertFalse(texts[1].strip())

    def test_cli_uses_candidate_date_for_full_time_bundle(self):
        profile={'expected_graduation_date':'May 2028 (Expected)','candidate_summary':'Reviewed','closing_strength':'Reviewed','evidence_groups':[]}
        argv=['cvbot','--job-description','synthetic-jd.txt','--company','Example','--role','Example Role','--generate-bundle','--role-kind','full_time']
        with patch('sys.argv',argv),patch('cv.bot.bot.Path.read_text',return_value='{}'),patch('cv.bot.bot.json.loads',return_value=profile),patch('cv.bot.bot.select_evidence',return_value=[]),patch('cv.bot.bot.select_keywords',return_value={}),patch('cv.bot.bot.render_report',return_value='Review'),patch('cv.bot.bot.write_bundle',return_value=Path('private_bundle')) as build:
            cv_main()
        self.assertEqual(build.call_args.kwargs['graduation_date'],'May 2028 (Expected)')

    def test_compile_uses_explicit_engine_and_platform_search_separator(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'resume.tex';source.write_text('Synthetic');build=root/'build';build.mkdir();(build/'resume.pdf').write_bytes(b'%PDF synthetic')
            with patch.dict('os.environ',{'JOBBOT_LATEX_ENGINE':'xelatex'}),patch('cv.bot.bot.os.pathsep',';'),patch('cv.bot.bot.subprocess.run',return_value=Mock(returncode=0)) as run:
                compile_latex(source,build)
            self.assertIn('-xelatex',run.call_args.args[0]);self.assertIn(';',run.call_args.kwargs['env']['TEXINPUTS'])
