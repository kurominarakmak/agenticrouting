import contextlib
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import app


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'README.md').write_text('Disposable test repository')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'fixture'], check=True)
        self.fake = self.root / 'codex-fixture'
        self.fake.write_text('''#!%s
import sys,subprocess,time
from pathlib import Path
args=sys.argv[1:]; root=Path(__file__).parent
mode=(root/'mode').read_text() if (root/'mode').exists() else 'ok'
if args[:2]==['login','status']:
 print('Logged in using API key' if mode=='api' else 'Logged in using ChatGPT');sys.exit(0)
if args[0]=='sandbox':
 sys.exit(subprocess.call(args[args.index('--')+1:]))
prompt=sys.stdin.read()
(root/'started').write_text(str(__import__('os').getpid()))
if mode=='slow':
 while not (root/'release').exists():time.sleep(.1)
if mode=='fail':sys.exit(7)
Path('greeting.py').write_text("def greet(name): return 'Hello, '+(name or 'friend')+'!'\\n")
Path(args[args.index('-o')+1]).write_text('Fixture claims success')
''' % sys.executable)
        self.fake.chmod(0o700)
        self.verify = self.root / 'verify.py'
        self.verify.write_text("import runpy\ngreet=runpy.run_path('greeting.py')['greet']\nassert greet('Ada')=='Hello, Ada!'\nassert greet('')=='Hello, friend!'\nprint('Acceptance passed')\n")
        config = json.loads((app.ROOT / 'config.json').read_text())
        config['codex'] = str(self.fake)
        config['enabled_harnesses'] = ['codex-chatgpt']
        config['knowledge_roots'] = {}
        config['timeout'] = 15
        config['repositories'] = {'demo': {'path': str(self.repo), 'verify': [sys.executable, str(self.verify)]}}
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps(config))
        self.token = app.setup(self.config, self.state)
        self.processes = []
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        app.Handler.token = self.token
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        (self.root / 'release').touch()
        for p in self.processes:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, method, path, data=None, auth=True, origin=None, host=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if auth:headers['Authorization'] = 'Bearer ' + self.token
        if origin:headers['Origin'] = origin
        if host:headers['Host'] = host
        conn.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse(); body = json.loads(response.read()); code=response.status
        conn.close()
        return code, body

    def start_worker(self, once=True):
        argv = [sys.executable, str(app.ROOT / 'app.py'), 'worker', '--config', str(self.config), '--state', str(self.state)]
        if once:argv += ['--once']
        p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(p)
        return p

    def wait_started(self):
        for _ in range(100):
            if (self.root/'started').exists():return
            time.sleep(.05)
        self.fail('Worker did not start child')

    def task(self, task_id):
        with app.db() as conn:return app.KB.get_task(conn, task_id)

    def test_simple_chat_and_missing_market_do_not_call_frontier(self):
        with patch.object(app, 'local_call', side_effect=AssertionError('No inference expected')):
            code, x = self.request('POST', '/api/chat', {'text': 'How many legs does a dog have?'})
            self.assertEqual(code,200);self.assertIn('four',x['answer']);self.assertNotIn('task_id',x)
            code, x = self.request('POST', '/api/chat', {'text': 'Check NVDA latest price using Webull'})
            self.assertEqual(code,200);self.assertIn('No authorized',x['answer'])
        self.assertEqual(app.snapshot()['tasks'], [])

    def test_complex_request_skips_local_attempt(self):
        with patch.object(app, 'local_call', side_effect=AssertionError('No local attempt')):
            result=app.submit('Develop a mean reversion strategy and backtest out-of-sample')
        self.assertEqual(result['route']['reasoning'],'deep')
        self.assertEqual(result['route']['quota'],'unknown')
        self.assertEqual(self.task(result['task_id']).status,'ready')

    def test_explicit_polite_coding_request_escalates(self):
        with patch.object(app, 'local_call', side_effect=AssertionError('No inference needed')):
            self.assertEqual(app.route('Can you implement a greeting function?')['mode'], 'job')
            self.assertEqual(app.route('What is a git worktree?')['mode'], 'chat')

    def test_question_about_backtesting_stays_local(self):
        with patch.object(app,'local_call',return_value='{"mode":"chat"}'):
            self.assertEqual(app.route('How should I backtest a strategy?')['mode'],'chat')

    def test_background_disconnect_and_verified_output(self):
        code, job = self.request('POST','/api/chat',{'text':'Implement a greeting function'})
        self.assertEqual(code,200)
        # The HTTP connection is already closed before the independent worker starts.
        worker=self.start_worker();self.assertEqual(worker.wait(timeout=15),0)
        task=self.task(job['task_id']);self.assertEqual(task.status,'done')
        self.assertFalse((self.repo/'greeting.py').exists())
        evidence=self.state/'artifacts'/task.id
        self.assertEqual(json.loads((evidence/'receipt-1.json').read_text())['exit_code'],0)
        self.assertIn('greeting.py',(evidence/'changes-1.patch').read_text())
        self.assertTrue((self.state/'worktrees'/task.id/'greeting.py').exists())
        self.assertTrue(any('Verified completion' in m['text'] for m in app.snapshot(job['conversation'])['messages']))

    def test_verifier_failure_overrules_agent_success(self):
        self.verify.write_text('raise AssertionError("External acceptance failed")\n')
        x=app.submit('Implement greeting')
        self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(x['task_id']).status,'blocked')
        self.assertEqual(json.loads((self.state/'artifacts'/x['task_id']/'receipt-1.json').read_text())['exit_code'],1)

    def test_project_tool_configuration_is_not_inherited(self):
        (self.repo / '.codex').mkdir()
        (self.repo / '.codex/config.toml').write_text('[mcp_servers.unreviewed]\ncommand="unreviewed"\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'unreviewed config'], check=True)
        x=app.submit('Implement greeting');self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(x['task_id']).status, 'blocked')
        self.assertFalse((self.root / 'started').exists())

    def test_api_key_authentication_refused(self):
        (self.root/'mode').write_text('api')
        x=app.submit('Implement greeting');self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(x['task_id']).status,'blocked')
        self.assertFalse((self.root/'started').exists())

    def test_failed_harness_is_not_retried_or_escalated(self):
        (self.root/'mode').write_text('fail')
        x=app.submit('Implement greeting');self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(x['task_id']).status,'blocked')
        self.start_worker().wait(timeout=15)
        with app.db() as conn:self.assertEqual(len(app.KB.list_runs(conn,x['task_id'])),1)

    def test_followup_revises_same_task_and_fences_old_completion(self):
        (self.root/'mode').write_text('slow')
        _, x=self.request('POST','/api/chat',{'text':'Implement greeting'})
        first=self.start_worker();self.wait_started()
        code,y=self.request('POST','/api/chat',{'text':'Add empty-name handling','conversation':x['conversation']})
        self.assertEqual(code,200);self.assertEqual(x['task_id'],y['task_id'])
        self.assertEqual(first.wait(timeout=10),0)
        self.assertEqual(self.task(x['task_id']).status,'ready')
        self.assertFalse((self.state/'artifacts'/x['task_id']/'receipt-1.json').exists())
        (self.root/'release').touch();self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(x['task_id']).status,'done')
        self.assertTrue((self.state/'artifacts'/x['task_id']/'receipt-2.json').exists())

    def test_cancel_running_process(self):
        (self.root/'mode').write_text('slow');x=app.submit('Implement greeting')
        worker=self.start_worker();self.wait_started()
        code,_=self.request('POST','/api/cancel',{'task_id':x['task_id'],'conversation':x['conversation']})
        self.assertEqual(code,200);self.assertEqual(worker.wait(timeout=10),0)
        self.assertEqual(app.snapshot()['tasks'][0]['status'],'cancelled')

    def test_worker_restart_preserves_and_blocks_interrupted_run(self):
        (self.root/'mode').write_text('slow');x=app.submit('Implement greeting')
        worker=self.start_worker();self.wait_started();worker.terminate();worker.wait(timeout=10)
        self.start_worker().wait(timeout=10)
        self.assertEqual(self.task(x['task_id']).status,'blocked')
        self.assertTrue((self.state/'worktrees'/x['task_id']).exists())

    def test_http_permissions_and_artifact_scope(self):
        self.assertEqual(self.request('GET','/api/state',auth=False)[0],401)
        self.assertEqual(self.request('GET','/api/state',host='evil.example')[0],403)
        self.assertEqual(self.request('POST','/api/chat',{'text':'Implement x'},origin='https://evil.example')[0],403)
        self.assertEqual(self.request('GET','/api/artifact?path=token')[0],404)
        self.assertEqual(self.request('POST','/api/chat',{'text':'Implement x','repo':'../../elsewhere'})[0],400)
        self.assertEqual(self.request('POST','/api/chat',{'text':'x','conversation':'unknown'})[0],400)

    def test_billing_environment_and_runtime_policy(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'must-not-propagate','ANTHROPIC_API_KEY':'must-not-propagate','OPENAI_BASE_URL':'https://example.invalid'}):
            self.assertNotIn('OPENAI_API_KEY',app.clean_env());self.assertNotIn('OPENAI_BASE_URL',app.clean_env())
        argv=app.codex_argv(self.repo,self.root/'reply')
        self.assertIn('forced_login_method="chatgpt"',argv)
        self.assertIn('--ignore-user-config',argv)
        self.assertIn('workspace-write',argv)
        self.assertIn('apps',argv);self.assertIn('plugins',argv)

    def test_heartbeat_and_persistence(self):
        x=app.submit('Implement greeting')
        self.assertFalse(app.snapshot()['worker']['online'])
        app.setup(self.config,self.state)
        self.assertEqual(self.task(x['task_id']).status,'ready')
        self.start_worker().wait(timeout=15)
        self.assertTrue(app.snapshot()['worker']['online'])


if __name__=='__main__':unittest.main()
