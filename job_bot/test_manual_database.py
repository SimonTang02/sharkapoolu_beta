from __future__ import annotations
import contextlib
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from job_bot.bot import connect_db,score_job,JobPosting
from job_bot.manual_database import import_rows,read_rows,validate_rows,main,JOB_COLUMNS,APP_COLUMNS
from job_bot.shared_database import ensure_ssh_platform
from job_bot.private_config import validate_credentials


def job(url='https://example.org/job'):
    return dict(zip(JOB_COLUMNS,['Example Company','Python Intern',url,'United States','manual','internship','Python and SQL project role','0001','','']))


def application(status='queued'):
    return dict(zip(APP_COLUMNS,['https://example.org/job',status,'true' if status=='submitted' else '','', '', 'Candidate explicitly confirmed synthetic successful submission' if status=='submitted' else '', 'Synthetic note']))


class ManualDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config={'database':{'path':str(self.root/'jobs.sqlite3')},'scoring':{'algorithm':'weighted_keywords_v1','keyword_groups':[{'name':'Python','weight':50,'keywords':['Python']}]}}
    def tearDown(self): self.temp.cleanup()

    def test_manual_creation_repeat_preserves_record_ids_and_existing_job(self):
        result=import_rows(self.config,[job()],[application()])
        self.assertEqual(result['jobs_created'],1);self.assertEqual(result['applications_created'],1)
        edited=job();edited['description']='Wrong replacement text'
        import_rows(self.config,[edited],[application('draft')])
        conn=connect_db(self.config)
        self.assertEqual(conn.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
        self.assertEqual(conn.execute('SELECT description,fit_score FROM jobs').fetchone()[1],50)
        self.assertEqual(conn.execute('SELECT status FROM applications').fetchone()[0],'queued')
        conn.close()

    def test_confirmed_submission_requires_both_evidence_and_explicit_option(self):
        with self.assertRaises(ValueError): import_rows(self.config,[job()],[application('submitted')])
        self.assertFalse((self.root/'jobs.sqlite3').exists())
        row=application('submitted');row['confirmation_evidence']=''
        with self.assertRaises(ValueError): validate_rows([], [row],True)
        import_rows(self.config,[job()],[application()])
        counts=import_rows(self.config,[],[application('submitted')],True)
        self.assertEqual(counts['submissions_recorded'],1)
        import_rows(self.config,[],[application('draft')])
        conn=connect_db(self.config)
        self.assertEqual(conn.execute('SELECT status FROM applications').fetchone()[0],'submitted')
        self.assertIn('recording_time',conn.execute('SELECT details_json FROM application_events ORDER BY id DESC').fetchone()[0])
        conn.close()

    def test_missing_reference_rolls_back_all_new_jobs(self):
        with self.assertRaises(ValueError): import_rows(self.config,[job('https://example.org/other')],[application()])
        conn=connect_db(self.config);self.assertEqual(conn.execute('SELECT count(*) FROM jobs').fetchone()[0],0);conn.close()

    def test_duplicate_application_ids_abort_instead_of_guessing(self):
        import_rows(self.config,[job()],[application()]);conn=connect_db(self.config)
        conn.execute("INSERT INTO applications(job_id,status) VALUES (1,'draft')");conn.commit();conn.close()
        with self.assertRaises(ValueError): import_rows(self.config,[],[application('submitted')],True)

    def test_csv_bom_multiline_and_missing_columns(self):
        path=self.root/'jobs.csv'
        path.write_text(','.join(JOB_COLUMNS)+'\nExample,Python Intern,https://example.org/job,,,unknown,"First line, comma\nSecond line",0001,,\n',encoding='utf-8-sig')
        rows=read_rows(path,JOB_COLUMNS);self.assertEqual(rows[0]['external_id'],'0001');self.assertIn('\n',rows[0]['description'])
        path.write_text('company,title\nExample,Role\n')
        with self.assertRaises(ValueError): read_rows(path,JOB_COLUMNS)

    def test_default_preview_never_connects_or_creates_database(self):
        path=self.root/'jobs.csv';path.write_text(','.join(JOB_COLUMNS)+'\n'+','.join(job().values())+'\n')
        with patch('sys.argv',['import-manual','--jobs',str(path)]),patch('job_bot.manual_database.load_config',return_value=self.config),patch('job_bot.manual_database.connect_db') as connect,patch('job_bot.manual_database.APPLICATION_OUTPUT',self.root/'out'),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(),0);connect.assert_not_called()
        self.assertFalse((self.root/'jobs.sqlite3').exists())

    def test_unsafe_urls_negative_scores_and_ambiguous_time_rejected(self):
        for url in ('javascript:alert(1)','http://example.org/job','https://user:pass@example.org/job'):
            with self.assertRaises(ValueError): validate_rows([job(url)],[])
        row=application('submitted');row['submitted_at']='2026-10-06T12:00:00'
        with self.assertRaises(ValueError): validate_rows([], [row],True)
        config={'scoring':{'algorithm':'weighted_keywords_v1','keyword_groups':[{'name':'Python','weight':10,'keywords':['Python']},{'name':'Senior','weight':-45,'keywords':['Senior'],'bonus_only':True}]}}
        value,_=score_job(JobPosting('Synthetic','Example','Senior Python','https://example.org'),config)
        self.assertEqual(value,0)

    def test_native_windows_ssh_rpc_guard_is_actionable(self):
        with patch('job_bot.shared_database.os.name','nt'):
            with self.assertRaisesRegex(sqlite3.OperationalError,'WSL'): ensure_ssh_platform()

    def test_relative_private_database_follows_relocated_private_root(self):
        from job_bot.bot import db_path
        with patch('job_bot.bot.DATABASE_DIR',self.root/'relocated/database'),patch('job_bot.bot.ROOT',self.root/'site-packages'):
            resolved=db_path({'database':{'path':'private_data/database/example.sqlite3'}})
            self.assertEqual(resolved,self.root/'relocated/database/example.sqlite3')
            with self.assertRaises(ValueError): db_path({'database':{'path':'private_data/database/../../outside.sqlite3'}})
            self.assertEqual(db_path({'database':{'path':str(self.root/'fixture.sqlite3')}}),self.root/'fixture.sqlite3')

    def test_windows_permissions_not_mistaken_for_verified_posix_security(self):
        path=self.root/'credentials.env';path.write_text('OPTION=\n');path.chmod(0o600)
        with patch('job_bot.private_config.os.name','nt'): issues=validate_credentials(path)
        self.assertTrue(any('NTFS' in row.message for row in issues))
        self.assertFalse(any(row.level=='ERROR' for row in issues))
