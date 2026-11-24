"""Focused deterministic acceptance tests for provider routing and orchestration."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import app
import control
import output_safety
import pr_delivery
import providers
import services
import supervisor
import workflows
import test_app as fixture


class _ProtocolHandler(http.server.BaseHTTPRequestHandler):
    requests=[]
    redirect_to=None
    fail=False
    def log_message(self,*_args):pass
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
        body=json.loads(raw or b'{}')
        type(self).requests.append((self.path,body,self.headers.get('Authorization'),self.headers.get('x-api-key')))
        if self.path.endswith('/redirect') or self.path.endswith('/chat/completions') and body.get('model')=='redirect-model':
            self.send_response(302);self.send_header('Location',type(self).redirect_to);self.end_headers();return
        if body.get('model')=='failure-model' or type(self).fail:
            content=b'provider echoed secret=fixture-secret-value'
            self.send_response(500);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        if self.path.endswith('/api/chat'):
            result={'message':{'content':'Ollama fixture answer'},'prompt_eval_count':3,'eval_count':2}
        elif self.path.endswith('/chat/completions'):
            result={'choices':[{'message':{'content':'Compatible fixture answer'}}], 'usage':{'prompt_tokens':5,'completion_tokens':4}}
        elif self.path.endswith('/responses'):
            result={'output':[{'content':[{'type':'output_text','text':'Responses fixture answer'}]}], 'usage':{'input_tokens':6,'output_tokens':3}}
        elif self.path.endswith('/messages'):
            result={'content':[{'type':'text','text':'Anthropic fixture answer'}], 'usage':{'input_tokens':7,'output_tokens':2}}
        else:
            result={'choices':[{'message':{'content':'Redirect target reached'}}]}
        content=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)


class FocusedOrchestrationTests(unittest.TestCase):
    # Reuse the disposable repository, fake CLI, verifier, DB and HTTP fixture from
    # test_app without inheriting and rerunning its entire legacy test class.
    setUp=fixture.PilotTests.setUp
    tearDown=fixture.PilotTests.tearDown
    start_worker=fixture.PilotTests.start_worker
    task=fixture.PilotTests.task

    def _set_provider(self, provider_id, spec):
        return services.update_settings({'orchestration':{'providers':{provider_id:spec}}})

    def _remote_spec(self, kind, base, *, model='fixture-model'):
        return {'type':kind,'base_url':base,'enabled':True,'remote':True,'share_context':True,'metered':True,'consent':True,
                'budget_calls':20,'task_call_limit':20,'max_output_tokens':64,'timeout_seconds':5,'secret_ref':'provider.json#API_KEY','models':[model],
                'temperature':0.6,'top_p':0.95}

    def test_removed_repository_policy_does_not_block_settings_save(self):
        with patch.dict(app.CONFIG, {'repositories': {}}):
            orchestration = services.orchestration_settings()
            self.assertEqual(orchestration['pr_policy'], {})
            services.update_settings({'orchestration': orchestration})

    def test_json_fence_parser_and_private_reasoning_filter_are_strict(self):
        self.assertEqual(output_safety.json_object('{"intent":"answer"}'),{'intent':'answer'})
        self.assertEqual(output_safety.json_object('```json\n{"intent":"answer"}\n```'),{'intent':'answer'})
        for bad in ('Here is the answer: {"intent":"answer"}', '```json\n{"intent":"answer"}\n``` extra', '[1,2]', '```json\n[1]\n```'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):output_safety.json_object(bad)
        self.assertEqual(output_safety.visible_text('<think>private</think>Visible answer'), 'Visible answer')
        with self.assertRaisesRegex(ValueError,'visible answer'):output_safety.visible_text('<think>unfinished private reasoning')

    def test_all_provider_protocols_sampling_usage_and_redaction(self):
        _ProtocolHandler.requests=[];_ProtocolHandler.fail=False
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),_ProtocolHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:%d'%server.server_port
            secret_dir=self.state/'secrets';secret_dir.mkdir(mode=0o700)
            secret_file=secret_dir/'provider.json';secret_file.write_text(json.dumps({'API_KEY':'fixture-secret-value'}));secret_file.chmod(0o600)
            self.assertEqual(secret_file.stat().st_mode&0o077,0)
            for name,kind,url,model in [
                ('compat','openai-compatible',base+'/v1','fixture-model'),('responses','openai',base+'/v1','fixture-model'),
                ('anthropic','anthropic',base+'/v1','fixture-model')]:
                self._set_provider(name,self._remote_spec(kind,url,model=model))
            ollama={'type':'ollama','base_url':base,'enabled':True,'remote':False,'task_call_limit':10,'max_output_tokens':64,
                    'models':['local-fixture'],'temperature':0.4,'top_p':0.8}
            self._set_provider('local-fixture',ollama)
            for name,model in [('compat','fixture-model'),('responses','fixture-model'),('anthropic','fixture-model'),('local-fixture','local-fixture')]:
                out=providers.complete(name,model,[{'role':'user','content':'fixture'}],role='assistant',share_context=True)
                self.assertTrue(out['text'].endswith('fixture answer'));self.assertIsInstance(out['usage'],dict)
            paths=[item[0] for item in _ProtocolHandler.requests]
            self.assertIn('/v1/chat/completions',paths);self.assertIn('/v1/responses',paths);self.assertIn('/v1/messages',paths);self.assertIn('/api/chat',paths)
            compat=next(item[1] for item in _ProtocolHandler.requests if item[0].endswith('/chat/completions'))
            self.assertEqual((compat['temperature'],compat['top_p']),(0.6,0.95))
            ollama_body=next(item[1] for item in _ProtocolHandler.requests if item[0].endswith('/api/chat'))
            self.assertEqual((ollama_body['options']['temperature'],ollama_body['options']['top_p']),(0.4,0.8))
            self.assertTrue(all(item[2]=='Bearer fixture-secret-value' for item in _ProtocolHandler.requests if item[0].endswith('/chat/completions') or item[0].endswith('/responses')))
            self.assertTrue(any(item[3]=='fixture-secret-value' for item in _ProtocolHandler.requests if item[0].endswith('/messages')))
            public=json.dumps(services.settings())
            self.assertNotIn('fixture-secret-value',public);self.assertNotIn('secret_ref',public)
            with self.assertRaisesRegex(ValueError,'unsupported fields'):
                providers.validate_provider('bad',ollama|{'unreviewed_field':True})
            with self.assertRaises(ValueError):
                providers.validate_provider('bad',ollama|{'api_key':'inline-secret'})
            providers_config=app.CONFIG.setdefault('providers',{})
            providers_config['external-local']={'type':'openai-compatible','base_url':'https://api.example.invalid/v1','enabled':True,'remote':False,'models':['x']}
            with patch.object(providers,'_request',side_effect=AssertionError('external endpoint must not be contacted')) as request:
                with self.assertRaisesRegex(ValueError,'explicitly configured as remote'):
                    providers.complete('external-local','x',[{'role':'user','content':'x'}])
                request.assert_not_called()
            providers_config.pop('external-local')
            # The provider returns an error body that echoes a secret. Only its status escapes.
            failing=self._remote_spec('openai-compatible',base+'/v1',model='failure-model')|{'models':['failure-model']}
            self._set_provider('failing',failing)
            with self.assertRaises(ValueError) as caught:providers.complete('failing','failure-model',[{'role':'user','content':'x'}],share_context=True)
            self.assertNotIn('fixture-secret-value',str(caught.exception));self.assertIn('500',str(caught.exception))
            failure_request=next(x for x in _ProtocolHandler.requests if x[1].get('model')=='failure-model')
            self.assertEqual(failure_request[2],'Bearer fixture-secret-value')
        finally:
            server.shutdown();server.server_close()

    def test_redirect_refusal_and_provider_task_budget_are_enforced(self):
        _ProtocolHandler.requests=[]
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),_ProtocolHandler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            base='http://127.0.0.1:%d'%server.server_port
            secret_dir=self.state/'secrets';secret_dir.mkdir(mode=0o700,exist_ok=True)
            secret_file=secret_dir/'provider.json';secret_file.write_text(json.dumps({'API_KEY':'fixture-secret-value'}));secret_file.chmod(0o600)
            _ProtocolHandler.redirect_to=base+'/captured'
            spec=self._remote_spec('openai-compatible',base+'/v1',model='redirect-model')|{'models':['redirect-model']}
            self._set_provider('redirector',spec)
            with self.assertRaises(ValueError):providers.complete('redirector','redirect-model',[{'role':'user','content':'x'}],share_context=True)
            self.assertTrue(any(item[0]=='/v1/chat/completions' for item in _ProtocolHandler.requests))
            self.assertFalse(any(item[0]=='/captured' for item in _ProtocolHandler.requests))
            bounded=self._remote_spec('openai-compatible',base+'/v1',model='one-call')|{'models':['one-call'],'task_call_limit':1,'budget_calls':10}
            self._set_provider('one-call',bounded)
            task='provider-budget-fixture'
            providers.complete('one-call','one-call',[{'role':'user','content':'x'}],task_id=task,share_context=True)
            before=len(_ProtocolHandler.requests)
            with self.assertRaisesRegex(ValueError,'per-task request budget'):
                providers.complete('one-call','one-call',[{'role':'user','content':'x'}],task_id=task,share_context=True)
            self.assertEqual(len(_ProtocolHandler.requests),before)
        finally:
            server.shutdown();server.server_close()

    @staticmethod
    def _proposal(**updates):
        base={'goal':'Implement the requested change','referenced_project':None,'referenced_task':None,'intent':'coding','difficulty':3,
              'capabilities':['coding','filesystem','tests'],'permissions':['write_worktree','run_tests'],'strategy':'direct_work',
              'delegation_beneficial':False,'planner_role':'none','worker_role':'configured','reviewer_role':'none','context_files':[],
              'evidence':['User requested an implementation.'],'confidence':0.9,'resources':{'provider_calls':2,'note':'Bounded local work'}}
        return base|updates

    def test_supervisor_contract_task_scope_one_read_and_role_effort_snapshot(self):
        proposal=self._proposal()
        self.assertEqual(supervisor._validate(proposal,None,'demo','Implement greeting'),proposal)
        with self.assertRaisesRegex(ValueError,'Invalid Supervisor intent'):
            supervisor._validate(proposal|{'intent':'planned_work'},None,'demo','Implement greeting')
        with self.assertRaisesRegex(ValueError,'required decision contract'):
            supervisor._validate(proposal|{'unrecognized':True},None,'demo','Implement greeting')
        created=app.submit('Implement greeting function')
        app.CONFIG['supervisor']={'enabled':True}
        task_id=created['task_id'];conversation=created['conversation']
        proposal_ref=proposal|{'referenced_task':task_id}
        self.assertEqual(supervisor._validate(proposal_ref,conversation,'demo','Continue the prior task')['referenced_task'],task_id)
        with self.assertRaisesRegex(ValueError,'outside this conversation'):
            supervisor._validate(proposal_ref,'different-conversation','demo','Continue the prior task')
        README=self.repo/'README.md';read_hash=hashlib.sha256(README.read_bytes()).hexdigest()
        first=self._proposal(context_files=['README.md']);second=self._proposal()
        answers=iter([first,second]);calls=[]
        def fake_complete(_provider,_model,_messages,_schema,**_kwargs):
            calls.append(_messages);return {'text':'```json\n'+json.dumps(next(answers))+'\n```','usage':{'input_tokens':8,'output_tokens':9}}
        with patch.object(providers,'complete',side_effect=fake_complete):
            result,metadata=supervisor.propose('Implement the greeting function',None,'demo')
        self.assertEqual(len(calls),2);self.assertEqual(result['context_files'],[])
        self.assertEqual(metadata['read_hashes'],[read_hash]);self.assertEqual(metadata['context_files'],['README.md'])
        with self.assertRaises(ValueError):supervisor._read_context('demo','../README.md')
        provider={'type':'openai-compatible','base_url':'http://127.0.0.1:1234/v1','enabled':True,'remote':False,'models':['role-model'],
                  'task_call_limit':4,'max_output_tokens':128,'reasoning_efforts_by_model':{'role-model':['low','medium']},'reasoning_parameter':'reasoning_effort'}
        services.update_settings({'orchestration':{'providers':{'role-api':provider},'roles':{
            'planner':{'mode':'manual','backend':'api','enabled':True,'provider':'role-api','model':'role-model','reasoning_effort':'medium'},
            'reviewer':{'mode':'manual','backend':'api','enabled':True,'provider':'role-api','model':'role-model','reasoning_effort':'low'}}}})
        settings=services.orchestration_settings()
        self.assertEqual(settings['roles']['planner']['reasoning_effort'],'medium')
        self.assertEqual(supervisor._role_selection('planner')['model'],'role-model')
        self.assertEqual(supervisor._role_selection('planner')['reasoning_effort'],'medium')

    def test_report_answer_prompt_uses_current_verified_same_conversation_receipt(self):
        self.verify.write_text("import runpy\ngreet=runpy.run_path('greeting.py')['greet']\ncases=[('Ada','Hello, Ada!'),('','Hello, friend!'),(None,'Hello, friend!'),('Lin','Hello, Lin!'),('Zoë','Hello, Zoë!'),('0','Hello, 0!')]\nfor name,expected in cases: assert greet(name)==expected\nprint('6 independent Explorer cases passed')\n")
        task_result,_=self._run_verified()
        task=fixture.PilotTests.task(self,task_result['task_id'])
        app.CONFIG['supervisor']={'enabled':True}
        api={'type':'openai-compatible','base_url':'http://127.0.0.1:1234/v1','enabled':True,'remote':False,
             'models':['report-model'],'task_call_limit':4,'max_output_tokens':512}
        services.update_settings({'orchestration':{'providers':{'report-api':api},'roles':{
            'supervisor':{'mode':'manual','enabled':True,'backend':'api','provider':'report-api','model':'report-model'}}}})
        proposal=self._proposal(intent='report',strategy='report_from_context',referenced_task=task.id,
            capabilities=['reasoning','read_context'],permissions=['read_context'],planner_role='none',worker_role='none',reviewer_role='none')
        final_messages=[]
        def fake_complete(_provider,_model,messages,_schema=None,*,role='assistant',**_kwargs):
            if role=='supervisor':return {'text':json.dumps(proposal),'usage':{'input_tokens':10,'output_tokens':8}}
            final_messages.extend(messages)
            return {'text':'Fixture report based on the verified task.','usage':{'input_tokens':20,'output_tokens':12}}
        with patch.object(providers,'complete',side_effect=fake_complete):
            response=app.submit('Please write a report based on the previous task',conversation=task_result['conversation'],repo='demo')
        self.assertIn('Fixture report',response['answer'])
        system=json.loads(final_messages[0]['content'].split('Context: ',1)[1])
        facts=system['verified_report_task']
        self.assertEqual(facts['status'],'verified');self.assertTrue(facts['verified'])
        self.assertEqual((facts['task_id'],facts['revision'],facts['task_status']),(task.id,1,'done'))
        self.assertEqual(facts['verifier_exit_code'],0);self.assertEqual(facts['case_count'],6)
        self.assertEqual(facts['changed_files'],['greeting.py'])
        self.assertEqual(facts['delivery'],{'prepared':True,'status':'prepared','commit_confirmed':False,
                                           'push_confirmed':False,'pull_request_url':None})
        self.assertNotIn('6 independent Explorer cases passed',json.dumps(system))

    def test_external_supervisor_context_filters_private_memories_and_sources(self):
        memories=[{'kind':'preference','text':'private memory sentinel','frontier':False},
                  {'kind':'evidence','text':'shared memory sentinel','frontier':True}]
        sources=[{'path':'private.md','sha256':'a','text':'private source sentinel','trust':'untrusted','frontier':False},
                 {'path':'shared.md','sha256':'b','text':'shared source sentinel','trust':'untrusted','frontier':True}]
        with patch.object(services,'knowledge_state',return_value={'memories':memories}),patch.object(services,'search',return_value=sources) as search:
            query='Please write a report based on the previous task memory sentinel'
            packet=supervisor._context(query,None,'demo',
                                       {'remote':True,'share_context':True},True)
            self.assertEqual([x['text'] for x in packet['memory']],['shared memory sentinel'])
            self.assertEqual([x['path'] for x in packet['scoped_sources']],['shared.md'])
            search.assert_any_call(query,frontier=True,limit=3)

            prior=app.submit('Implement greeting function')
            app.CONFIG['supervisor']={'enabled':True}
            secret_dir=self.state/'secrets';secret_dir.mkdir(mode=0o700,exist_ok=True)
            secret_file=secret_dir/'provider.json';secret_file.write_text(json.dumps({'API_KEY':'fixture-secret-value'}));secret_file.chmod(0o600)
            api={'type':'openai-compatible','base_url':'http://127.0.0.1:1234/v1','enabled':True,'remote':True,
                 'share_context':True,'metered':False,'consent':True,'budget_calls':4,'task_call_limit':4,
                 'max_output_tokens':512,'secret_ref':'provider.json#API_KEY','models':['context-model']}
            services.update_settings({'orchestration':{'providers':{'context-api':api},'roles':{'supervisor':{
                'mode':'manual','enabled':True,'backend':'api','provider':'context-api','model':'context-model'}}}})
            api_calls=[]
            def api_complete(_provider,_model,messages,_schema=None,**_kwargs):
                api_calls.append(messages)
                return {'text':json.dumps(self._proposal(intent='report',strategy='report_from_context',referenced_task=prior['task_id'],
                    capabilities=['reasoning','read_context'],permissions=['read_context'])),'usage':{}}
            with patch.object(providers,'complete',side_effect=api_complete):
                supervisor.propose(query,prior['conversation'],'demo')
            api_packet=json.loads(api_calls[0][1]['content'])['conversation_context']
            api_rendered=json.dumps(api_packet)
            self.assertNotIn('private memory sentinel',api_rendered);self.assertNotIn('private source sentinel',api_rendered)
            self.assertIn('shared memory sentinel',api_rendered);self.assertIn('shared.md',api_rendered)
            services.update_settings({'orchestration':{'roles':{'supervisor':{'mode':'manual','enabled':True,'backend':'native',
                'runtime':'codex-chatgpt','model':'fixture-native-model','reasoning_effort':'medium'}}}})
            captured=[]
            def native(messages,*_args,**_kwargs):
                captured.append(messages)
                return json.dumps(self._proposal(intent='report',strategy='report_from_context',referenced_task=prior['task_id'],
                    capabilities=['reasoning','read_context'],permissions=['read_context']))
            with patch.object(app,'frontier_answer',side_effect=native):
                supervisor.propose(query,prior['conversation'],'demo')
            payload=json.loads(captured[0][1]['content'])['context']
            rendered=json.dumps(payload)
            self.assertNotIn('private memory sentinel',rendered)
            self.assertNotIn('private source sentinel',rendered)
            self.assertIn('shared memory sentinel',rendered)
            self.assertIn('shared.md',rendered)

    def test_provider_exclusions_apply_to_roles_and_both_reservation_boundaries(self):
        task=app.submit('Implement a greeting function')['task_id']
        api={'type':'openai-compatible','base_url':'http://127.0.0.1:1234/v1','enabled':True,'remote':False,
             'models':['excluded-model'],'task_call_limit':4,'max_output_tokens':128}
        services.update_settings({'orchestration':{'providers':{'excluded-api':api},'excluded_providers':['excluded-api','codex-chatgpt'],
            'provider_priority':['excluded-api'],'roles':{
                'planner':{'mode':'manual','enabled':True,'backend':'api','provider':'excluded-api','model':'excluded-model'},
                'reviewer':{'mode':'manual','enabled':True,'backend':'native','runtime':'codex-chatgpt','model':'fixture-native-model','reasoning_effort':'medium'}}}})
        self.assertEqual(services.select_runtime({'mode':'job','reasoning':'deep','risk':'workspace-write'})['runtime'],'unavailable')
        with self.assertRaisesRegex(ValueError,'excluded by owner policy'):
            supervisor._role_selection('planner')
        with self.assertRaisesRegex(ValueError,'excluded by owner policy'):
            supervisor._role_selection('reviewer')
        with patch.object(providers,'_request',side_effect=AssertionError('excluded provider must not contact endpoint')) as request:
            with self.assertRaisesRegex(ValueError,'excluded by owner policy'):
                providers.complete('excluded-api','excluded-model',[{'role':'user','content':'x'}])
            request.assert_not_called()
        with app.db() as c:
            before_native=c.execute('SELECT COUNT(*) FROM paw_native_calls').fetchone()[0]
            before_provider=c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?',(task,)).fetchone()[0]
        with self.assertRaisesRegex(ValueError,'excluded by owner policy'):
            control.reserve_provider_call('excluded-api','excluded-model','planner',task,128,None,4)
        with self.assertRaisesRegex(ValueError,'excluded by owner policy'):
            control.reserve_native('codex-chatgpt','fixture-native-model','medium',task,'reviewer')
        with app.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM paw_native_calls').fetchone()[0],before_native)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?',(task,)).fetchone()[0],before_provider)

    def test_native_budget_counts_prior_api_calls_for_total_task_ceiling(self):
        task=app.submit('Implement a greeting function')['task_id']
        api={'type':'openai-compatible','base_url':'http://127.0.0.1:1234/v1','enabled':True,'remote':False,
             'models':['planner-model'],'task_call_limit':4,'max_output_tokens':128}
        services.update_settings({'orchestration':{'providers':{'planner-api':api},'policy':{
            'max_provider_calls_per_task':1,'max_native_calls_per_task':4}}})
        control.reserve_provider_call('planner-api','planner-model','planner',task,128,None,4)
        with app.db() as c:
            before_native=c.execute('SELECT COUNT(*) FROM paw_native_calls').fetchone()[0]
            before_task=c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?',(task,)).fetchone()[0]
        with self.assertRaisesRegex(ValueError,'total provider-call budget'):
            control.reserve_native('codex-chatgpt','fixture-native-model','medium',task,'worker')
        with app.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM paw_native_calls').fetchone()[0],before_native)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?',(task,)).fetchone()[0],before_task)

    def test_configured_supervisor_failure_never_calls_legacy_classifier(self):
        with patch.object(supervisor,'configured',return_value=True),\
             patch.object(supervisor,'decide',side_effect=ValueError('invalid contract')),\
             patch.object(app,'local_call',side_effect=AssertionError('legacy classifier must not run')),\
             patch.object(providers,'complete',side_effect=AssertionError('alternate provider must not run')):
            decision=app.route('Based on the prior task, could you help with this?')
        self.assertEqual(decision['runtime'],'unavailable')
        self.assertEqual(decision['decision_source'],'supervisor-failed-closed')
        self.assertIn('no heuristic classifier',decision['blocked_reason'])

    def _install_review_fixture(self, mode='review-fix'):
        script='''#!%s
import json,os,subprocess,sys,time
from pathlib import Path
args=sys.argv[1:];root=Path(__file__).parent
if args[:2]==['login','status']:
 print('Logged in using ChatGPT');sys.exit(0)
if args and args[0]=='sandbox':sys.exit(subprocess.call(args[args.index('--')+1:]))
prompt=sys.stdin.read();(root/('prompt-'+str(len(list(root.glob('prompt-*.txt')))+1)+'.txt')).write_text(prompt)
out=Path(args[args.index('-o')+1])
if '--output-schema' in args:
 (root/'reviewer.argv.json').write_text(json.dumps(args))
 bug="+def greet(name): return 'Hello, '+name+'!'" in prompt
 mode=(root/'mode').read_text()
 if mode=='review-limit' or bug:
  result={'approved':False,'summary':'The empty-name case is not handled.','findings':[{'path':'greeting.py','severity':'blocker','title':'Empty name raises an error','details':'The changed implementation concatenates the name without a fallback.'}]}
 else:result={'approved':True,'summary':'The empty-name fallback is present.','findings':[]}
 out.write_text(json.dumps(result));sys.exit(0)
countfile=root/'worker-count';count=int(countfile.read_text())+1 if countfile.exists() else 1;countfile.write_text(str(count))
mode=(root/'mode').read_text()
if mode=='review-repeat':definition="def greet(name): return 'Hello, '+name+'!'\\n"
elif count==1:definition="def greet(name): return 'Hello, '+name+'!'\\n"
else:definition="def greet(name):\\n    return 'Hello, '+(name or 'friend')+'!'\\n"
Path('greeting.py').write_text(definition);out.write_text('Fixture worker completed')
'''%sys.executable
        self.fake.write_text(script);self.fake.chmod(0o700)
        (self.root/'mode').write_text(mode)
        verify_normal=self.root/'verify-normal.py'
        verify_normal.write_text("import runpy\ngreet=runpy.run_path('greeting.py')['greet']\nassert greet('Ada')=='Hello, Ada!'\nprint('Normal greeting passed')\n")
        verify_empty=self.root/'verify-empty.py'
        verify_empty.write_text("import runpy\ngreet=runpy.run_path('greeting.py')['greet']\nassert greet('')=='Hello, friend!'\nprint('Empty-name post-check passed')\n")
        cfg=json.loads(self.config.read_text());cfg['repositories']['demo']['verify']=[sys.executable,str(verify_normal)]
        cfg['codex_model']='fixture-native-model';cfg['codex_reasoning_effort']='medium';cfg['codex_reasoning_efforts_by_model']={'fixture-native-model':['low','medium','high']}
        cfg['native_call_budget']=30;cfg['native_task_call_budget']=12
        self.config.write_text(json.dumps(cfg));app.CONFIG.update(cfg)
        services.update_settings({'orchestration':{'roles':{'reviewer':{'mode':'manual','enabled':True,'backend':'native','runtime':'codex-chatgpt','model':'fixture-native-model','reasoning_effort':'medium'}},
            'policy':{'max_iterations':2,'max_concurrency':1,'max_native_calls_per_task':8,'max_wall_seconds':120}}})
        return verify_empty

    def test_worker_reviewer_finds_real_bug_worker_fixes_retests_and_external_postcheck_passes(self):
        external_postcheck=self._install_review_fixture()
        result=app.submit('Implement greet(name) and handle an empty name')
        process=self.start_worker();self.assertEqual(process.wait(timeout=30),0)
        task=fixture.PilotTests.task(self,result['task_id']);self.assertEqual(task.status,'done')
        worktree=self.state/'worktrees'/task.id
        self.assertIn("name or 'friend'",(worktree/'greeting.py').read_text())
        receipt=json.loads((self.state/'artifacts'/task.id/'receipt-1.json').read_text())
        self.assertEqual(len(receipt['review_cycles']),2)
        self.assertFalse(receipt['review_cycles'][0]['review']['approved'])
        self.assertTrue(receipt['review_cycles'][1]['review']['approved'])
        self.assertIn('Independent Reviewer requested', (self.root/'prompt-3.txt').read_text())
        reviewer_argv=json.loads((self.root/'reviewer.argv.json').read_text())
        sandbox=reviewer_argv[reviewer_argv.index('-s')+1]
        self.assertEqual(sandbox,'read-only')
        self.assertIn('--output-schema',reviewer_argv)
        with app.db() as c:
            roles=[r[0] for r in c.execute("SELECT role FROM paw_provider_calls WHERE task_id=? ORDER BY id",(task.id,))]
        self.assertEqual(roles,['worker','reviewer','worker','reviewer'])
        calls=app.snapshot(result['conversation'])['agent_calls']
        self.assertEqual([call['role'] for call in reversed(calls)],roles)
        self.assertTrue(all(call['task_id']==task.id and call['created']>0 for call in calls))
        another=app.submit('How many legs does a dog have?')['conversation']
        self.assertEqual(app.snapshot(another)['agent_calls'],[])
        checked=subprocess.run([sys.executable,str(external_postcheck)],cwd=worktree,capture_output=True,text=True)
        self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)

    def test_repeated_unchanged_review_failure_and_iteration_exhaustion_never_complete(self):
        for mode in ('review-repeat','review-limit'):
            with self.subTest(mode=mode):
                self.tearDown();self.setUp()
                self._install_review_fixture(mode)
                result=app.submit('Implement greet(name) and handle an empty name')
                process=self.start_worker();self.assertEqual(process.wait(timeout=30),0)
                status=fixture.PilotTests.task(self,result['task_id']).status
                self.assertNotEqual(status,'done')
                self.assertIn(status,('blocked','failed'))
                self.assertTrue((self.state/'artifacts'/result['task_id']/'receipt-1.json').exists())

    def test_reviewer_cannot_override_a_failing_independent_verifier(self):
        self._install_review_fixture('review-limit')
        always_fail=self.root/'always-fail.py';always_fail.write_text("raise AssertionError('Independent check failed')\n")
        cfg=json.loads(self.config.read_text());cfg['repositories']['demo']['verify']=[sys.executable,str(always_fail)]
        self.config.write_text(json.dumps(cfg));app.CONFIG.update(cfg)
        result=app.submit('Implement greeting function')
        process=self.start_worker();self.assertEqual(process.wait(timeout=30),0)
        self.assertEqual(fixture.PilotTests.task(self,result['task_id']).status,'blocked')
        receipt=json.loads((self.state/'artifacts'/result['task_id']/'receipt-1.json').read_text())
        self.assertNotEqual(receipt['exit_code'],0)
        self.assertFalse((self.root/'reviewer.argv.json').exists())

    def test_parallel_worker_claims_two_worktrees_and_same_claim_is_atomic(self):
        self.assertEqual(services.orchestration_settings()['policy']['max_concurrency'],1)
        result=app.submit('Implement greeting function');task_id=result['task_id']
        barrier=threading.Barrier(3);claims=[];failures=[]
        def claim():
            try:
                barrier.wait()
                with app.db() as c:claims.append(app.KB.claim_task(c,task_id,ttl_seconds=60))
            except Exception as exc:failures.append(exc)
        threads=[threading.Thread(target=claim) for _ in range(2)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join()
        self.assertFalse(failures);self.assertEqual(sum(x is not None for x in claims),1)
        # Reset the single-claim fixture by scheduling two separate task IDs below.
        result_a=app.submit('Implement greeting A');result_b=app.submit('Implement greeting B')
        services.update_settings({'orchestration':{'policy':{'max_concurrency':2}}})
        (self.root/'mode').write_text('parallel')
        worker=self.start_worker();self.assertEqual(worker.wait(timeout=30),0)
        self.assertEqual(fixture.PilotTests.task(self,result_a['task_id']).status,'done')
        self.assertEqual(fixture.PilotTests.task(self,result_b['task_id']).status,'done')
        wa=self.state/'worktrees'/result_a['task_id'];wb=self.state/'worktrees'/result_b['task_id']
        self.assertNotEqual(wa.resolve(),wb.resolve());other=(wb/'greeting.py').read_bytes()
        (wa/'greeting.py').write_text((wa/'greeting.py').read_text()+'# isolated mutation\n')
        self.assertEqual((wb/'greeting.py').read_bytes(),other)
        markers=list(self.root.glob('started-*'));self.assertGreaterEqual(len(markers),2)

    def _run_verified(self, text='Implement greeting function'):
        result=app.submit(text);worker=self.start_worker();self.assertEqual(worker.wait(timeout=30),0)
        return result, self.state/'worktrees'/result['task_id']

    def _add_bare_origin(self):
        bare=self.root/'origin.git';subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
        subprocess.run(['git','-C',str(self.repo),'remote','add','origin',str(bare)],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.name','Fixture Owner'],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.email','owner@fixture.invalid'],check=True)
        cfg=json.loads(self.config.read_text());cfg['repositories']['demo']['default_branch']=subprocess.check_output(['git','-C',str(self.repo),'branch','--show-current'],text=True).strip()
        self.config.write_text(json.dumps(cfg));app.CONFIG.update(cfg)
        return bare

    def _mock_gh(self):
        path=self.root/'gh-fixture'
        path.write_text('''#!%s
import json,sys
from pathlib import Path
root=Path(__file__).parent;args=sys.argv[1:];mark=root/'pr-created'
if args[:2]==['pr','list']:
 print(json.dumps([{'url':'https://github.com/fixture/repo/pull/17','state':'OPEN'}] if mark.exists() else []))
elif args[:2]==['pr','create']:
 mark.write_text('created');print('https://github.com/fixture/repo/pull/17')
else:sys.exit(2)
'''%sys.executable)
        path.chmod(0o700);return path

    def test_prepared_pr_default_does_not_mutate_and_receipt_hash_staleness_is_denied(self):
        result,worktree=self._run_verified()
        delivery=pr_delivery.snapshot(result['task_id'])
        self.assertEqual(delivery['status'],'prepared');self.assertIsNone(delivery['commit_sha']);self.assertIsNone(delivery['pushed_at']);self.assertIsNone(delivery['pr_url'])
        self.assertTrue(delivery['policy']['require_commit_approval']);self.assertTrue(delivery['policy']['require_push_approval'])
        (worktree/'greeting.py').write_text((worktree/'greeting.py').read_text()+'# stale\n')
        with app.db() as c:
            job=dict(c.execute('SELECT * FROM paw_jobs WHERE task_id=?',(result['task_id'],)).fetchone())
        task=fixture.PilotTests.task(self,result['task_id']);receipt=json.loads((self.state/'artifacts'/result['task_id']/'receipt-1.json').read_text())
        with self.assertRaisesRegex(ValueError,'changed after verification'):
            pr_delivery.prepare(task,job,worktree,receipt,app.change_patch(worktree))
        self.assertIsNone(pr_delivery.snapshot(result['task_id'])['commit_sha'])

    def test_tracked_benign_deletions_are_supported_by_pr_changed_path_scan(self):
        (self.repo/'remove-me.txt').write_text('ordinary tracked content\n')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Test','-c','user.email=test@localhost','commit','-qm','tracked deletion fixture'],check=True)
        result,worktree=self._run_verified()
        (worktree/'remove-me.txt').unlink()
        self.assertIn('remove-me.txt',pr_delivery._changed_paths(worktree))

    def test_separate_commit_push_pr_approvals_and_ambiguous_push_reconcile(self):
        self._add_bare_origin();result,_=self._run_verified();task_id=result['task_id'];gh=self._mock_gh()
        with self.assertRaisesRegex(ValueError,'separate commit approval'):pr_delivery.commit(task_id,'owner-policy')
        pr_delivery.commit(task_id,'authenticated-owner')
        with self.assertRaisesRegex(ValueError,'separate push approval'):pr_delivery.push(task_id,'owner-policy')
        real_run=subprocess.run;interrupted={'done':False}
        def ambiguous(argv,*args,**kwargs):
            completed=real_run(argv,*args,**kwargs)
            if argv and argv[0]=='git' and 'push' in argv and not interrupted['done']:
                interrupted['done']=True
                return subprocess.CompletedProcess(argv,1,completed.stdout,'connection ended after remote accepted the update')
            return completed
        with patch.object(pr_delivery.shutil,'which',return_value=str(gh)),patch.object(pr_delivery.subprocess,'run',side_effect=ambiguous):
            with self.assertRaisesRegex(ValueError,'did not confirm'):pr_delivery.push(task_id,'authenticated-owner')
        log=json.loads(pr_delivery._get(task_id)[0]['action_log']);self.assertEqual(log['push']['state'],'intent')
        with patch.object(pr_delivery.shutil,'which',return_value=str(gh)):
            pr_delivery.push(task_id,'authenticated-owner')
            final=pr_delivery.create_pr(task_id,'authenticated-owner')
        self.assertEqual(final['status'],'in_review');self.assertEqual(final['pr_url'],'https://github.com/fixture/repo/pull/17')
        self.assertTrue(final['review_task_id']);self.assertEqual(final['action_log']['push']['state'],'reconciled')

    def test_explicit_owner_preapproved_auto_policy_commits_pushes_and_creates_pr(self):
        self._add_bare_origin();gh=self._mock_gh()
        gh_bin=self.root/'bin';gh_bin.mkdir();gh.rename(gh_bin/'gh');gh=gh_bin/'gh'
        services.update_settings({'orchestration':{'pr_policy':{'demo':{'require_commit_approval':False,'require_push_approval':False,
                    'automatic_pr_after_verification':True,'require_owner_review_before_done':True}}}})
        with patch.dict(os.environ,{'PATH':str(gh_bin)+os.pathsep+os.environ.get('PATH','')}):
            result,_=self._run_verified()
        delivery=pr_delivery.snapshot(result['task_id'])
        self.assertTrue(delivery['commit_sha']);self.assertTrue(delivery['pushed_at'])
        self.assertEqual(delivery['pr_url'],'https://github.com/fixture/repo/pull/17')
        self.assertEqual(delivery['status'],'in_review')
        self.assertEqual(delivery['commit_actor'],'owner-policy');self.assertEqual(delivery['push_actor'],'owner-policy');self.assertEqual(delivery['pr_actor'],'owner-policy')
        self.assertEqual(delivery['action_log']['commit']['state'],'complete')
        self.assertEqual(delivery['action_log']['push']['state'],'reconciled')
        self.assertEqual(delivery['action_log']['create_pr']['state'],'reconciled')

    def test_task_no_publication_constraint_overrides_preapproved_auto_policy(self):
        self._add_bare_origin();gh=self._mock_gh()
        gh_bin=self.root/'bin';gh_bin.mkdir();gh.rename(gh_bin/'gh')
        services.update_settings({'orchestration':{'pr_policy':{'demo':{'require_commit_approval':False,'require_push_approval':False,
                    'automatic_pr_after_verification':True,'require_owner_review_before_done':True}}}})
        with patch.dict(os.environ,{'PATH':str(gh_bin)+os.pathsep+os.environ.get('PATH','')}):
            result,_=self._run_verified('Implement greeting. Do not commit, push, or publish.')
        self.assertEqual(fixture.PilotTests.task(self,result['task_id']).status,'review')
        delivery=pr_delivery.snapshot(result['task_id'])
        self.assertEqual(delivery['status'],'prepared')
        self.assertTrue(delivery['patch_available']);self.assertTrue(delivery['body_available'])
        self.assertIsNone(delivery['commit_sha']);self.assertIsNone(delivery['pushed_at']);self.assertIsNone(delivery['pr_url'])
        self.assertEqual(delivery['action_log']['automatic_delivery']['state'],'blocked_task_constraint')
        self.assertFalse((gh_bin/'pr-created').exists())
        remote=subprocess.check_output(['git','--git-dir',str(self.root/'origin.git'),'for-each-ref','--format=%(refname)'],text=True)
        self.assertEqual(remote.strip(),'')

    def test_cancel_and_superseding_revision_fence_commit_push_and_pr(self):
        bare=self._add_bare_origin();gh=self._mock_gh()
        services.update_settings({'orchestration':{'pr_policy':{'demo':{'require_owner_review_before_done':True}}}})
        first,_=self._run_verified();task=fixture.PilotTests.task(self,first['task_id'])
        workflows.action(task.id,first['conversation'],'cancel',actor='authenticated-owner')
        with self.assertRaisesRegex(ValueError,'Cancelled or paused'):
            pr_delivery.commit(task.id,'authenticated-owner')
        self.assertIsNone(pr_delivery.snapshot(task.id)['commit_sha'])

        second,_=self._run_verified();task=fixture.PilotTests.task(self,second['task_id'])
        pr_delivery.commit(task.id,'authenticated-owner')
        app.submit('Revise the greeting wording',conversation=second['conversation'],task_id=task.id)
        with self.assertRaisesRegex(ValueError,'stale'):
            pr_delivery.push(task.id,'authenticated-owner')
        workflows.action(task.id,second['conversation'],'cancel',actor='authenticated-owner')
        refs=subprocess.check_output(['git','--git-dir',str(bare),'for-each-ref','--format=%(refname)'],text=True)
        self.assertNotIn('refs/heads/codex/paw-'+task.id,refs)

        third,_=self._run_verified();task=fixture.PilotTests.task(self,third['task_id'])
        pr_delivery.commit(task.id,'authenticated-owner');pr_delivery.push(task.id,'authenticated-owner')
        app.submit('Revise this task after verification',conversation=third['conversation'],task_id=task.id)
        with patch.object(pr_delivery.shutil,'which',return_value=str(gh)) as which:
            with self.assertRaisesRegex(ValueError,'stale'):
                pr_delivery.create_pr(task.id,'authenticated-owner')
            which.assert_not_called()
        self.assertFalse((self.root/'pr-created').exists())
