import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import app
import services
import workflows
import ops
import test_app as base


class FeatureTests(unittest.TestCase):
    setUp=base.PilotTests.setUp
    tearDown=base.PilotTests.tearDown
    request=base.PilotTests.request
    start_worker=base.PilotTests.start_worker
    wait_started=base.PilotTests.wait_started
    task=base.PilotTests.task

    def test_local_only_blocks_incompatible_write_harness(self):
        services.update_settings({'routing':'local-only'})
        result=app.submit('Implement greeting')
        self.assertEqual(self.task(result['task_id']).status,'blocked')
        self.assertIn('Local-only',result['answer'])
        self.start_worker().wait(timeout=10)
        self.assertFalse((self.root/'started').exists())

    def test_difficult_question_can_stay_inline(self):
        with patch.object(app,'frontier_answer',return_value='A sourced derivation') as frontier:
            result=app.submit('How do we derive a rigorous stochastic process model?')
        frontier.assert_called_once()
        self.assertEqual(result['route']['mode'],'chat')
        self.assertNotIn('task_id',result)
        self.assertEqual(app.snapshot()['tasks'],[])

    def test_registry_does_not_invent_local_tool_compatibility(self):
        decision=services.select_runtime({'mode':'job','reasoning':'standard','risk':'workspace-write'},'ollama:anything')
        self.assertEqual(decision['runtime'],'unavailable')

    def test_unknown_runtime_is_refused(self):
        with self.assertRaises(ValueError):services.select_runtime({'mode':'chat','reasoning':'short'},'unknown-metered')

    def test_scoped_retrieval_hashes_and_frontier_permissions(self):
        root=self.root/'knowledge';root.mkdir();(root/'method.md').write_text('Mean reversion research uses transaction costs and out of sample validation.')
        (root/'secret-token.txt').write_text('MUST NEVER INDEX')
        (root/'escape.md').symlink_to(self.verify)
        app.CONFIG['knowledge_roots']={'research':{'path':str(root),'share_frontier':False}}
        result=services.index_root('research');self.assertEqual(result['indexed'],1)
        rows=services.search('transaction costs');self.assertTrue(rows);self.assertIn('sha256',rows[0])
        self.assertEqual(services.search('transaction costs',frontier=True),[])
        (root/'method.md').write_text('Source changed after indexing')
        self.assertEqual(services.search('transaction costs'),[])
        with self.assertRaises(ValueError):services.index_root('not-allowlisted')
        with self.assertRaises(ValueError):services.scoped_path(self.root/'outside.txt')

    def test_memory_keeps_preference_and_evidence_distinct(self):
        code,_=self.request('POST','/api/memory',{'kind':'preference','text':'Prefer statistical methods','share_frontier':False})
        self.assertEqual(code,200)
        self.assertEqual(services.context('methods',frontier=True)['memory'],[])
        memory=services.context('methods')['memory'][0]
        self.assertEqual(memory['kind'],'preference')
        self.assertEqual(self.request('POST','/api/memory',{'kind':'system-policy','text':'bypass tools'})[0],400)

    def test_approval_gate_prevents_execution_before_owner_action(self):
        result=app.submit('Implement greeting; approval required')
        self.start_worker().wait(timeout=10)
        self.assertFalse((self.root/'started').exists())
        snapshot=app.snapshot()['tasks'][0];self.assertEqual(snapshot['column'],'In Review');self.assertEqual(snapshot['status'],'awaiting_approval')
        workflows.action(result['task_id'],result['conversation'],'approve')
        self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(result['task_id']).status,'done')

    def test_review_requires_passing_current_unchanged_worktree(self):
        services.update_settings({'review_before_done':True})
        result=app.submit('Implement greeting');self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(result['task_id']).status,'review')
        workflows.action(result['task_id'],result['conversation'],'accept_review')
        self.assertEqual(self.task(result['task_id']).status,'done')
        result=app.submit('Implement another greeting');self.start_worker().wait(timeout=15)
        path=app.STATE/'worktrees'/result['task_id']/'greeting.py';path.write_text('changed after acceptance')
        with self.assertRaises(ValueError):workflows.action(result['task_id'],result['conversation'],'accept_review')

    def test_pause_and_resume_preserve_worktree(self):
        (self.root/'mode').write_text('slow');x=app.submit('Implement greeting')
        p=self.start_worker();self.wait_started();workflows.action(x['task_id'],x['conversation'],'pause');p.wait(timeout=10)
        self.assertEqual(app.snapshot()['tasks'][0]['status'],'paused')
        (self.root/'release').touch();workflows.action(x['task_id'],x['conversation'],'resume')
        self.start_worker().wait(timeout=15);self.assertEqual(self.task(x['task_id']).status,'done')

    def test_user_retries_are_bounded(self):
        (self.root/'mode').write_text('fail');x=app.submit('Implement greeting')
        self.start_worker().wait(timeout=15)
        for attempt in range(3):
            try:workflows.action(x['task_id'],x['conversation'],'retry')
            except ValueError:break
            self.start_worker().wait(timeout=15)
        else:self.fail('Retry limit did not stop repeated failures')
        self.assertLessEqual(app.snapshot()['tasks'][0]['attempts'],3)
        self.assertEqual(app.snapshot()['tasks'][0]['status'],'failed')

    def test_delegated_dag_fences_parent_until_handoff(self):
        result=app.submit('Implement a complex greeting function with multi-step analysis')
        plan={'subtasks':[{'title':'Inspect repository conventions','instruction':'Read the actual inventory and identify missing tests'}]}
        with patch.object(workflows,'harness_text',return_value=json.dumps(plan)):app.worker(once=True)
        self.assertEqual(self.task(result['task_id']).status,'todo')
        child=next(t for t in app.snapshot()['tasks'] if t['parent_id']==result['task_id'])
        self.assertEqual(child['route']['runtime'],'ollama')
        def local(argv,*args,**kwargs):Path(argv[2]).write_text('Local fixture observation: README.md exists');return 0
        with patch.object(app,'run_child',side_effect=local):app.worker(once=True)
        self.assertEqual(self.task(child['id']).status,'done')
        app.worker(once=True)
        self.assertEqual(self.task(result['task_id']).status,'done')
        self.assertTrue((app.STATE/'artifacts'/child['id']/'observations.json').exists())

    def test_followup_targets_root_and_invalidates_old_plan(self):
        x=app.submit('Implement a complex greeting function')
        with patch.object(workflows,'harness_text',return_value=json.dumps({'subtasks':[{'title':'Inspect context','instruction':'Inspect files'}]})):app.worker(once=True)
        result=app.submit('Add empty name behavior',x['conversation'])
        self.assertEqual(result['task_id'],x['task_id'])
        child=next(t for t in app.snapshot()['tasks'] if t['parent_id'])
        self.assertEqual(child['status'],'cancelled')
        self.assertEqual(next(t for t in app.snapshot()['tasks'] if t['id']==x['task_id'])['dependencies'],[])

    def test_invalid_plan_cannot_inject_executables_or_unbounded_fanout(self):
        for plan in [{'subtasks':[{'title':'x','instruction':'y','command':'rm'}]}, {'subtasks':[{'title':'x','instruction':'y'}]*4}]:
            with self.assertRaises(ValueError):workflows.validate_plan(plan)

    def test_unconfigured_and_financial_tools_fail_closed(self):
        with self.assertRaises(ValueError):services.mcp_request('missing','call','read_status',{})
        app.CONFIG['mcp_servers']={'finance':{'enabled':True,'finance':True,'allowed_tools':{'place_order':'read'}}}
        with self.assertRaises(ValueError):services.mcp_request('finance','call','place_order',{})
        with self.assertRaises(ValueError):services.mcp_request('finance','call','anything_else',{})

    def test_real_mcp_protocol_fixture_discovery_and_allowlist(self):
        sdk=Path(app.CONFIG['hermes_source'])/'venv/bin/python'
        app.CONFIG['mcp_servers']={'fixture':{'enabled':True,'command':str(sdk),'args':[str(app.ROOT/'tests/mcp_fixture.py')],'finance':True,'allowed_tools':{'read_status':'read'}}}
        listed=services.mcp_request('fixture');self.assertTrue(any(t['name']=='read_status' and t['authorized'] for t in listed['tools']))
        self.assertTrue(any(t['name']=='place_order' and not t['authorized'] for t in listed['tools']))
        result=services.mcp_request('fixture','call','read_status',{})
        self.assertIn('not a real provider',json.dumps(result))
        with app.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM paw_tool_audit').fetchone()[0],2)

    def test_private_origin_is_exact_and_does_not_trust_forwarded_headers(self):
        app.CONFIG['remote_origin']='https://fixture.tailnet.ts.net:8443'
        self.assertEqual(self.request('GET','/api/state',host='fixture.tailnet.ts.net:8443')[0],200)
        self.assertEqual(self.request('POST','/api/chat',{'text':'How many legs does a dog have?'},host='fixture.tailnet.ts.net:8443',origin=app.CONFIG['remote_origin'])[0],200)
        self.assertEqual(self.request('POST','/api/chat',{'text':'x'},origin='https://evil.ts.net')[0],403)
        self.assertEqual(self.request('GET','/api/state',host='fixture.tailnet.ts.net:443')[0],403)

    def test_risky_external_operation_is_blocked_not_silently_approved(self):
        result=app.submit('Deploy the app and transfer money')
        self.assertEqual(self.task(result['task_id']).status,'blocked')
        self.start_worker().wait(timeout=10)
        self.assertFalse((self.root/'started').exists())

    def test_real_stream_endpoint_emits_deltas_and_persists_final_message(self):
        import http.client
        def infer(messages,schema=None,on_delta=None,model=None):
            on_delta('Five');on_delta(' legs is wrong; four is normal.');return 'Four is normal.'
        with patch.object(app,'local_call',side_effect=infer):
            c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
            c.request('POST','/api/chat/stream',json.dumps({'text':'What is a normal animal fact?'}),{'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
            response=c.getresponse();events=[json.loads(line) for line in response.read().decode().splitlines()];c.close()
        self.assertEqual([e['type'] for e in events],['delta','delta','result'])
        result=events[-1]['data'];messages=app.snapshot(result['conversation'])['messages']
        self.assertEqual(messages[-1]['text'],'Four is normal.')
        self.assertEqual(app.snapshot()['tasks'],[])

    def test_hard_killed_worker_recovers_and_stops_recorded_child(self):
        (self.root/'mode').write_text('slow');x=app.submit('Implement greeting')
        first=self.start_worker();self.wait_started();pid=int((self.root/'started').read_text())
        first.kill();first.wait(timeout=5)
        self.start_worker().wait(timeout=10)
        self.assertEqual(self.task(x['task_id']).status,'blocked')
        result=subprocess.run(['/bin/ps','-p',str(pid),'-o','stat='],capture_output=True,text=True)
        self.assertTrue(result.returncode!=0 or 'Z' in result.stdout)
        self.assertTrue((app.STATE/'worktrees'/x['task_id']).exists())

    def test_concurrent_submissions_preserve_one_task_and_both_instructions(self):
        from concurrent.futures import ThreadPoolExecutor
        conversation=app.submit('How many legs does a dog have?')['conversation']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda text:app.submit(text,conversation),['Implement greeting','Add empty-name handling']))
        self.assertEqual(results[0]['task_id'],results[1]['task_id'])
        self.assertEqual(len(app.snapshot()['tasks']),1)
        with app.db() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM paw_messages WHERE task_id=? AND role='user'",(results[0]['task_id'],)).fetchone()[0],2)

    def test_second_worker_cannot_conflict_with_active_worker(self):
        (self.root/'mode').write_text('slow');app.submit('Implement greeting')
        first=self.start_worker();self.wait_started();second=self.start_worker()
        self.assertNotEqual(second.wait(timeout=5),0)
        (self.root/'release').touch();self.assertEqual(first.wait(timeout=15),0)
        self.assertEqual(len(app.snapshot()['tasks']),1)

    def test_quota_error_classification_never_starts_another_provider(self):
        path=self.root/'quota.log';path.write_text('{"type":"error","message":"usage_limit_reached"}')
        reason=app.harness_failure(path,1)
        self.assertIn('quota',reason);self.assertIn('without provider escalation',reason)
        self.assertFalse((self.root/'started').exists())

    def test_server_specific_secret_mapping_requires_owner_only_files(self):
        folder=app.STATE/'secrets';folder.mkdir();secret=folder/'fixture.json';secret.write_text('{"KEY":"fixture-only"}');secret.chmod(0o644)
        app.CONFIG['mcp_servers']={'fixture':{'enabled':True,'secret_file':'fixture.json','env':{'KEY':'secret:KEY'}}}
        with self.assertRaises(ValueError):services.mcp_request('fixture')

    def test_review_followup_returns_same_task_for_rework(self):
        services.update_settings({'review_before_done':True})
        x=app.submit('Implement greeting');self.start_worker().wait(timeout=15)
        self.assertEqual(self.task(x['task_id']).status,'review')
        result=app.submit('Add empty-name behavior',x['conversation'])
        self.assertEqual(result['task_id'],x['task_id'])
        self.assertEqual(self.task(x['task_id']).status,'ready')
        with self.assertRaises(ValueError):workflows.action(x['task_id'],x['conversation'],'accept_review')

    def test_parent_resume_restores_only_active_local_dependencies(self):
        x=app.submit('Implement a complex greeting')
        with patch.object(workflows,'harness_text',return_value=json.dumps({'subtasks':[{'title':'Inspect files','instruction':'Inspect the actual repository'}]})):app.worker(once=True)
        child=next(t for t in app.snapshot()['tasks'] if t['parent_id'])
        workflows.action(x['task_id'],x['conversation'],'pause')
        workflows.action(x['task_id'],x['conversation'],'resume')
        with app.db() as c:self.assertFalse(c.execute('SELECT paused FROM paw_jobs WHERE task_id=?',(child['id'],)).fetchone()[0])
        def local(argv,*_,**__):Path(argv[2]).write_text('Local context');return 0
        with patch.object(app,'run_child',side_effect=local):app.worker(once=True)
        workflows.action(x['task_id'],x['conversation'],'cancel')
        self.assertEqual(self.task(child['id']).status,'done')
        self.assertEqual(next(t for t in app.snapshot()['tasks'] if t['id']==child['id'])['status'],'done')

    def test_retry_cannot_bypass_pending_execution_approval(self):
        x=app.submit('Implement greeting; approval required')
        with self.assertRaises(ValueError):workflows.action(x['task_id'],x['conversation'],'retry')
        self.start_worker().wait(timeout=10)
        self.assertFalse((self.root/'started').exists())

    def test_notification_outbox_is_private_and_delivery_is_bounded(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        import threading
        captured=[]
        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append(self.rfile.read(int(self.headers['Content-Length'])).decode())
                self.send_response(200);self.end_headers()
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            app.CONFIG['notification_webhook']={'enabled':True,'url':'http://127.0.0.1:'+str(server.server_port),'include_titles':False}
            services.notify(None,'completed','Sensitive example title must stay local')
            services.deliver_notifications();services.deliver_notifications()
            self.assertEqual(len(captured),1);self.assertNotIn('Sensitive',captured[0])
            with app.db() as c:self.assertEqual(c.execute('SELECT delivered FROM paw_notifications').fetchone()[0],1)
        finally:server.shutdown();server.server_close()

    def test_glm_profile_is_explicit_and_does_not_leak_into_other_providers(self):
        folder=app.STATE/'secrets';folder.mkdir();secret=folder/'glm.json';secret.write_text('{"GLM_CODING_PLAN_KEY":"fixture-plan-key"}');secret.chmod(0o600)
        app.CONFIG['glm']={'enabled':True,'plan_entitlement_confirmed':True,'base_url':'https://api.z.ai/api/anthropic','model':'operator-confirmed-fixture','confirmed_plan_models':['operator-confirmed-fixture'],'secret_file':'glm.json'}
        env=services.provider_env('glm-coding-plan')
        self.assertEqual(env['ANTHROPIC_BASE_URL'],'https://api.z.ai/api/anthropic')
        self.assertTrue(env['CLAUDE_CONFIG_DIR'].endswith('providers/glm'))
        self.assertEqual(services.provider_env('codex-chatgpt'),{})
        self.assertEqual(services.provider_env('claude-subscription'),{})
        app.CONFIG['glm']['base_url']='https://example.invalid/metered'
        with self.assertRaises(ValueError):services.provider_env('glm-coding-plan')
        app.CONFIG['glm']['base_url']='https://api.z.ai/api/anthropic';app.CONFIG['glm']['plan_entitlement_confirmed']=False
        with self.assertRaises(ValueError):services.provider_env('glm-coding-plan')

    def test_remote_setup_requires_readback_even_when_cli_returns_success(self):
        from types import SimpleNamespace
        def command(argv,check=True):
            if argv[1:]==['status','--json']:return SimpleNamespace(returncode=0,stdout=json.dumps({'BackendState':'Running','Self':{'DNSName':'fixture.tailnet.ts.net.'}}))
            if argv[1:]==['serve','status','--json']:return SimpleNamespace(returncode=0,stdout='{}')
            return SimpleNamespace(returncode=0,stdout='Serve is not enabled on your tailnet')
        with patch.object(ops,'ROOT',self.root),patch.object(ops,'RUNTIME',self.root/'installed'),patch.object(ops,'run',side_effect=command),patch('shutil.which',return_value='/fixture/tailscale'):
            with self.assertRaises(ValueError):ops.remote()
        self.assertEqual(json.loads(self.config.read_text())['remote_origin'],'')

    def test_history_pagination_keeps_old_conversation_tasks_inspectable(self):
        conversation=app.submit('How many legs does a dog have?')['conversation'];ids=[]
        with app.db() as c:
            for i in range(105):
                task=app.KB.create_task(c,title='Historical fixture '+str(i),assignee='default',workspace_kind='dir',workspace_path=str(self.repo))
                app.KB.complete_task(c,task,summary='Pagination fixture only',fire_lifecycle_hook=False)
                c.execute('INSERT INTO paw_jobs(task_id,conversation,repo,route) VALUES(?,?,?,?)',(task,conversation,'demo',json.dumps({'mode':'job','runtime':'codex-chatgpt'})))
                ids.append(task)
            for i in range(55):c.execute('INSERT INTO paw_conversations VALUES(?,?)',('historical-'+str(i),i))
        first=app.snapshot();self.assertEqual(first['task_total'],105);self.assertEqual(len(first['tasks']),100)
        self.assertEqual(len(app.snapshot(offset=100)['tasks']),5)
        self.assertEqual(len(app.snapshot(conversation)['tasks']),105)
        self.assertIn(ids[0],[t['id'] for t in app.snapshot(include_task=ids[0])['tasks']])
        self.assertEqual(self.request('GET','/api/conversations?offset=50')[0],200)
        self.assertEqual(len(self.request('GET','/api/conversations?offset=50')[1]),6)
        self.assertEqual(self.request('GET','/api/state?offset=-1')[0],400)

    def test_lead_can_avoid_unnecessary_delegation(self):
        result=app.submit('Implement a complex greeting function')
        with patch.object(workflows,'harness_text',return_value=json.dumps({'subtasks':[]})):app.worker(once=True)
        self.assertEqual(self.task(result['task_id']).status,'done')
        self.assertFalse(any(t['parent_id'] for t in app.snapshot()['tasks']))

    def test_launchd_config_uses_absolute_paths_and_preserves_process_groups(self):
        config=ops.plist('worker')
        self.assertTrue(Path(config['ProgramArguments'][0]).is_absolute())
        self.assertTrue(config['KeepAlive']);self.assertFalse(config['AbandonProcessGroup'])
        self.assertNotIn('OPENAI_API_KEY',config['EnvironmentVariables'])
