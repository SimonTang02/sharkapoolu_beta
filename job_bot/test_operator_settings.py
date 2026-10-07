from __future__ import annotations
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

from private_paths import PROJECT_ROOT
from job_bot.operator_settings import compile_settings, validate_settings, require_module, region_allowed
from job_bot.easy_cli import main, agent_packet
from job_bot.bot import connect_db, scan, JobPosting, render_digest
from job_bot.operator_browser import checked_endpoint, ApplicationMonitor
from application_bot.operator_review import review_template, validate_review, evidence_hash
from application_bot.operator_execution import execute_preparation
from application_bot.dispatcher import DispatchPlan


def template():
    return json.loads((PROJECT_ROOT / 'examples/easy_settings_template.json').read_text(encoding='utf-8'))


class OperatorSettingsTests(unittest.TestCase):
    def test_switches_disable_selected_transport_and_parent_overrides_children(self):
        data=template()
        data['02_功能模块']['job_bot']=False
        data['03_浏览器与采集']['CDP浏览器']=True
        config=compile_settings({'sources':[{'name':'HTTP','type':'rss','enabled':True}, {'name':'Browser','type':'moka_cdp','enabled':True}]},data)
        self.assertTrue(all(not s['enabled'] for s in config['sources']))
        self.assertFalse(config['operator_controls']['browser_enabled'])
        with self.assertRaises(ValueError): require_module(config,'scan')
        require_module(config,'assist')
        self.assertFalse(config['application_browser']['auto_submit'])
        self.assertFalse(config['field_mappings']['safety']['allow_submit'])

    def test_strict_errors_block_typo_bool_count_and_submit(self):
        for group,key,value in [('01_使用模式','自动最终提交',True),('04_审查与额度','投递前审查轮数',True),('04_审查与额度','投递前审查轮数',0),('02_功能模块','扫描职立',True)]:
            with self.subTest(key=key,value=value):
                data=template();data[group][key]=value
                with self.assertRaises(ValueError): validate_settings(data)

    def test_legacy_config_unchanged_and_input_not_mutated(self):
        base={'sources':[{'name':'Test','type':'rss','enabled':True,'sync_active':True}]}
        before=copy.deepcopy(base)
        config=compile_settings(base,template())
        self.assertEqual(base,before)
        self.assertFalse(config['sources'][0]['sync_active'])
        require_module(base,'fill')
        self.assertTrue(region_allowed('Singapore',base))
        self.assertFalse(region_allowed('Singapore',config))
        self.assertTrue(region_allowed('Hong Kong, China',config))
        self.assertTrue(region_allowed('Multiple unknown locations',config))

    def test_regional_scan_preserves_previous_active_jobs_and_digest_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            config=compile_settings({'database':{'path':str(Path(directory)/'jobs.sqlite3')},
                'sources':[{'name':'Fixture','type':'rss','sync_active':True}], 'digest':{'min_score':0}},template())
            conn=connect_db(config)
            conn.execute("INSERT INTO jobs(title,url,source_name,location,is_active) VALUES ('Old','https://example.org/old','Fixture','Singapore',1)")
            conn.commit();conn.close()
            postings=[JobPosting(source_name='Fixture',company='Example',title='Local',url='https://example.org/us',location='United States'),
                      JobPosting(source_name='Fixture',company='Example',title='Excluded',url='https://example.org/sg',location='Singapore')]
            with patch('job_bot.bot.fetch_source_with_retry',return_value=postings):
                result=scan(config)
            self.assertEqual(result['seen'],1)
            conn=connect_db(config)
            self.assertEqual(conn.execute('SELECT is_active FROM jobs WHERE title="Old"').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT count(*) FROM jobs').fetchone()[0],2)
            conn.close()
            _,body=render_digest(config,24,all_active=True)
            self.assertIn('Local',body);self.assertNotIn('Old',body)

    def test_disabled_scan_never_opens_database(self):
        data=template();data['01_使用模式']['总开关']=False
        config=compile_settings({},data)
        with patch('job_bot.bot.connect_db') as connect:
            with self.assertRaises(ValueError): scan(config)
            connect.assert_not_called()

    def test_plan_never_writes_or_executes_even_with_execute(self):
        with patch('sys.argv',['jobbot-settings','plan','--execute']),patch('job_bot.easy_cli.load_settings',return_value=template()),patch('job_bot.easy_cli.prepare_config',return_value=compile_settings({},template())),patch('job_bot.easy_cli.write_private') as write,patch('job_bot.easy_cli.subprocess.run') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(),0)
            write.assert_not_called();run.assert_not_called()

    def test_nonexecute_run_only_plans(self):
        with patch('sys.argv',['jobbot-settings','run','--task','scan']),patch('job_bot.easy_cli.load_settings',return_value=template()),patch('job_bot.easy_cli.prepare_config',return_value=compile_settings({},template())),patch('job_bot.easy_cli.write_private') as write,patch('job_bot.easy_cli.subprocess.run') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(),0)
            write.assert_not_called();run.assert_not_called()

    def test_cdp_requires_local_endpoint(self):
        config={'application_browser':{'windows_cdp':{'url':'http://example.org:9222'}}}
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError): checked_endpoint(config)
            config['application_browser']['windows_cdp']['url']='http://127.0.0.1:9222'
            self.assertEqual(checked_endpoint(config),'http://127.0.0.1:9222')

    def test_monitor_only_inspects_registered_application(self):
        monitor=object.__new__(ApplicationMonitor)
        unrelated=Mock();unrelated.evaluate.return_value='personal';unrelated.locator.side_effect=AssertionError('must not inspect')
        page=Mock();page.evaluate.return_value='jobbot-application-7';page.url='https://example.org/login';page.title.return_value='Login'
        page.locator.return_value.inner_text.return_value='Enter verification code'
        page.locator.return_value.count.return_value=1
        monitor.browser=Mock();monitor.browser.contexts=[Mock(pages=[unrelated,page])]
        self.assertEqual(monitor.interruption(7),'challenge_required')
        unrelated.locator.assert_not_called()


class ReviewAndExecutionTests(unittest.TestCase):
    def test_review_requires_actual_rounds_evidence_and_current_hashes(self):
        with tempfile.TemporaryDirectory() as directory,patch('application_bot.operator_review.PRIVATE_ROOT',Path(directory)):
            root=Path(directory);pdf=root/'reviewed.pdf';pdf.write_bytes(b'%PDF synthetic')
            path=root/'review.json';data=review_template(7,3)
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): validate_review(7,3,path)
            for row in data['rounds']:
                row.update(reviewer='Example Reviewer',reviewed_at='2026-01-01T12:00:00Z')
                for key in ('qualification','fields','attachments'):
                    row[key].update(passed=True,note='Actual review evidence',evidence=[{'path':str(pdf),'sha256':evidence_hash(str(pdf))}])
            path.write_text(json.dumps(data));validate_review(7,3,path)
            with self.assertRaises(ValueError): validate_review(8,3,path)
            with self.assertRaises(ValueError): validate_review(7,4,path)
            pdf.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'已变化'): validate_review(7,3,path)

    def test_review_rejects_external_file_even_with_hash(self):
        with tempfile.TemporaryDirectory() as directory,patch('application_bot.operator_review.PRIVATE_ROOT',Path(directory)/'private'):
            file=Path(directory)/'outside.pdf';file.write_bytes(b'synthetic')
            with self.assertRaises(ValueError): evidence_hash(str(file))

    def plan(self):
        return DispatchPlan(7,'Example','Role','example','queued','example',None,'ready',False,3,[sys.executable,'-c','pass'])

    def test_checkpoint_before_start_never_runs_adapter(self):
        monitor=Mock();monitor.interruption.return_value='challenge_required'
        plan=self.plan()
        with patch('application_bot.operator_execution.subprocess.Popen') as start:
            execute_preparation(plan,{'operator_controls':{'adapter_retries':0}},monitor,PROJECT_ROOT)
            start.assert_not_called()
        self.assertEqual(plan.state,'challenge_required')

    def test_quick_interruption_kills_adapter_not_browser(self):
        plan=self.plan();process=Mock();process.poll.side_effect=[None,0]
        process.communicate.side_effect=[subprocess.TimeoutExpired('synthetic',1),('','')]
        monitor=Mock();monitor.interruption.side_effect=[None,'challenge_required']
        with patch('application_bot.operator_execution.subprocess.Popen',return_value=process),patch('application_bot.operator_execution.os.name','posix'),patch('application_bot.operator_execution.os.killpg',create=True) as kill:
            execute_preparation(plan,{'operator_controls':{'adapter_retries':0}},monitor,PROJECT_ROOT)
            kill.assert_called_once()
        self.assertEqual(plan.result_code,125);monitor.close.assert_not_called()

    def test_retry_budget_and_success_never_imply_submission(self):
        plan=self.plan();monitor=Mock();monitor.interruption.return_value=None
        first=Mock(returncode=1);first.poll.return_value=1
        second=Mock(returncode=0);second.poll.return_value=0
        with patch('application_bot.operator_execution.subprocess.Popen',side_effect=[first,second]) as start:
            execute_preparation(plan,{'operator_controls':{'adapter_retries':1}},monitor,PROJECT_ROOT)
            self.assertEqual(start.call_count,2)
        self.assertEqual(plan.state,'adapter_prepared_not_submitted')

    def test_private_agent_packet_preserves_existing_review_and_guides_new_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=compile_settings({'database':{'path':str(root/'jobs.sqlite3')}},template())
            conn=connect_db(config)
            conn.execute("INSERT INTO jobs(id,title,url,company,location) VALUES (1,'Example Role','https://example.org/1','Example','United States')")
            conn.execute("INSERT INTO applications(id,job_id,status) VALUES (7,1,'queued')")
            conn.commit();conn.close()
            existing=root/'output/operator_reviews/application_7.json';existing.parent.mkdir(parents=True);existing.write_text('existing evidence')
            with patch('job_bot.easy_cli.PRIVATE_ROOT',root),patch('job_bot.easy_cli.APPLICATION_OUTPUT',root/'output'),patch('application_bot.operator_review.APPLICATION_OUTPUT',root/'output'):
                path=agent_packet(config,'assist',[7])
                self.assertIn('AGENTS.md',path.read_text(encoding='utf-8'));self.assertIn('3 轮',path.read_text(encoding='utf-8'))
                self.assertEqual(existing.read_text(encoding='utf-8'),'existing evidence')
                self.assertEqual(json.loads((path.parent/'targets.json').read_text(encoding='utf-8'))[0]['id'],7)
                self.assertEqual(path.stat().st_mode & 0o777,0o600)

class DispatcherPolicyTests(unittest.TestCase):
    def run_dispatch(self, mode, review_ok=True, finished=False):
        from application_bot.dispatcher import main as dispatch
        data=template();data['01_使用模式']['模式']=mode
        data['02_功能模块']['自动填写']=True
        config=compile_settings({},data)
        plans=[DispatchPlan(appid,'Example','Role','example','submitted' if finished else 'queued','example',None,'ready',False,180,['synthetic-adapter']) for appid in (7,8)]
        conn=Mock();conn.execute.return_value.fetchone.return_value=('United States',)
        calls=[]
        def execute(plan,*args):
            calls.append(plan.application_id)
            plan.state='challenge_required';plan.result_code=125
        with tempfile.TemporaryDirectory() as directory,patch('sys.argv',['dispatch','--application-id','7','--application-id','8','--execute']),patch('application_bot.dispatcher.load_config',return_value=config),patch('application_bot.dispatcher.connect_db',return_value=conn),patch('application_bot.dispatcher.application_rows',return_value=[{'id':7},{'id':8}]),patch('application_bot.dispatcher.check_application_limit',return_value=None),patch('application_bot.dispatcher.build_plans',return_value=plans),patch('application_bot.dispatcher.APPLICATION_OUTPUT',Path(directory)),patch('application_bot.operator_review.validate_application_review',side_effect=None if review_ok else ValueError('实际审查未完成')),patch('job_bot.operator_browser.ApplicationMonitor') as monitor,patch('application_bot.operator_execution.execute_preparation',side_effect=execute),contextlib.redirect_stdout(io.StringIO()):
            result=dispatch()
            if review_ok and not finished: monitor.return_value.close.assert_called_once()
            else: monitor.assert_not_called()
        return result,plans,calls

    def test_quick_mode_skips_interrupted_job_and_continues(self):
        result,plans,calls=self.run_dispatch('快速填写')
        self.assertEqual(result,1);self.assertEqual(calls,[7,8])
        self.assertTrue(all(plan.timeout_seconds==45 for plan in plans))

    def test_full_mode_stops_batch_on_checkpoint(self):
        result,plans,calls=self.run_dispatch('完整填写')
        self.assertEqual(result,1);self.assertEqual(calls,[7])
        self.assertEqual(plans[1].state,'batch_stopped_for_manual_checkpoint')
        self.assertIsNone(plans[1].command)

    def test_review_failure_never_opens_browser_or_adapter(self):
        result,plans,calls=self.run_dispatch('快速填写',review_ok=False)
        self.assertEqual(result,1);self.assertFalse(calls)
        self.assertTrue(all(plan.state=='review_required' for plan in plans))

    def test_submitted_jobs_never_reexecuted(self):
        result,plans,calls=self.run_dispatch('快速填写',finished=True)
        self.assertEqual(result,0);self.assertFalse(calls)
        self.assertTrue(all(plan.state=='already_finished' for plan in plans))

class BoundReviewTests(unittest.TestCase):
    def test_current_profile_actual_attachments_and_job_are_bound_to_review(self):
        from application_bot.operator_review import validate_application_review, job_fingerprint
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'out';out.mkdir()
            master=root/'master.json';evidence=root/'evidence.json';profile=root/'bound.json';pdf=root/'actual.pdf';wrong=root/'other.pdf'
            master.write_text('{}');evidence.write_text('{}');pdf.write_bytes(b'%PDF synthetic actual');wrong.write_bytes(b'%PDF synthetic other')
            profile.write_text(json.dumps({'documents':{'resume_path':str(pdf)}}))
            conn=connect_db({'database':{'path':str(root/'jobs.sqlite3')}})
            conn.execute("INSERT INTO jobs(id,title,url,description) VALUES (1,'Example','https://example.org/job','Synthetic qualification')")
            conn.execute("INSERT INTO applications(id,job_id,status,profile_path) VALUES (7,1,'queued',?)",(str(profile),));conn.commit()
            with patch('application_bot.operator_review.PRIVATE_ROOT',root),patch('application_bot.operator_review.APPLICATION_OUTPUT',out),patch('application_bot.operator_review.APPLICATION_PROFILE',master),patch('application_bot.operator_review.EVIDENCE_PROFILE',evidence):
                from application_bot.operator_review import review_path
                record=review_template(7,1);record['job_fingerprint']=job_fingerprint('https://example.org/job','Synthetic qualification')
                row=record['rounds'][0];row.update(reviewer='Example Reviewer',reviewed_at='2026-01-01T12:00:00Z')
                for key,files in {'qualification':[master,evidence], 'fields':[profile], 'attachments':[wrong]}.items():
                    row[key].update(passed=True,note='Synthetic reviewed evidence',evidence=[{'path':str(file),'sha256':evidence_hash(str(file))} for file in files])
                path=review_path(7);path.parent.mkdir();path.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError,'实际附件'): validate_application_review(conn,7,1)
                row['attachments']['evidence']=[{'path':str(pdf),'sha256':evidence_hash(str(pdf))}]
                path.write_text(json.dumps(record));validate_application_review(conn,7,1)
                conn.execute("UPDATE jobs SET description='Changed requirement'")
                with self.assertRaisesRegex(ValueError,'JD或URL已变化'): validate_application_review(conn,7,1)
            conn.close()

    def test_monitor_missing_registered_page_is_a_manual_checkpoint(self):
        monitor=object.__new__(ApplicationMonitor);monitor.browser=Mock(contexts=[])
        self.assertEqual(monitor.interruption(7),'application_tab_required')
