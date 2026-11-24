import json,threading,unittest,http.client
from pathlib import Path
from unittest.mock import patch
import test_app as base
import app,control
class ControlTests(unittest.TestCase):
 request=base.PilotTests.request
 setUp=base.PilotTests.setUp
 tearDown=base.PilotTests.tearDown
 def task(self):return app.submit('Implement greeting')['task_id']
 def test_replay_dedup_revision_and_redaction(self):
  task=self.task();control.emit(task,'tool.requested',{'tool':'read_file','secret':'hidden','activity':'token=private'},source_key='same');control.emit(task,'tool.requested',{'tool':'read_file'},source_key='same')
  page=control.replay(task);self.assertEqual(sum(e['event_type']=='tool.requested' for e in page['events']),1);self.assertNotIn('private',json.dumps(page));self.assertEqual(control.replay(task,page['cursor'])['events'],[])
  app.submit('Add an empty-name case',conversation=app.snapshot()['tasks'][0]['conversation'],task_id=task)
  self.assertFalse(control.emit(task,'task.completed',revision=1))
  with self.assertRaisesRegex(ValueError,'Stale'):control.replay(task,revision=1)
 def test_event_cursor_is_durable_and_sequences_ordered(self):
  task=self.task()
  threads=[threading.Thread(target=control.emit,args=(task,'tool.completed',{'exit_code':0})) for _ in range(5)]
  for t in threads:t.start()
  for t in threads:t.join()
  events=control.replay(task)['events'];seq=[e['sequence'] for e in events];self.assertEqual(seq,sorted(set(seq)))
  control.bind(app);self.assertEqual(control.replay(task)['events'],events)
 @patch.object(control,"local_identity",return_value="test-model-identity")
 def test_registry_unknown_failed_and_recent_evidence(self,_identity):
  self.assertFalse(control.capability('dsh-local','fixture','multi-file')['eligible'])
  for _ in range(2):control.record_capability('dsh-local','fixture','multi-file',True,{'fixture':True})
  self.assertTrue(control.capability('dsh-local','fixture','multi-file')['eligible'])
  control.record_capability('dsh-local','fixture','multi-file',False,{'fixture':True});self.assertFalse(control.capability('dsh-local','fixture','multi-file')['eligible'])
 def test_changed_model_identity_is_not_automatically_eligible(self):
  with patch.object(control,'local_identity',return_value='identity-a'):
   for _ in range(2):control.record_capability('dsh-local','fixture','multi-file',True,{'fixture':True})
   self.assertTrue(control.capability('dsh-local','fixture','multi-file')['eligible'])
  with patch.object(control,'local_identity',return_value='identity-b'):self.assertFalse(control.capability('dsh-local','fixture','multi-file')['eligible'])
 @patch.object(control,"local_identity",return_value="test-model-identity")
 def test_imported_old_evidence_does_not_become_recent(self,_identity):
  import time
  for _ in range(2):control.record_capability('dsh-local','fixture','multi-file',True,{}, {'observed_at':time.time()-8*86400})
  self.assertFalse(control.capability('dsh-local','fixture','multi-file')['eligible'])
  with self.assertRaises(ValueError):control.record_capability('dsh-local','fixture','multi-file',True,{}, {'observed_at':float('nan')})
 def test_validated_skill_read_is_projected_without_contents(self):
  task=self.task();control.validated_sources(task,[{'path':'methods/SKILL.md','sha256':'abc','text':'private instructions'}],1,None)
  events=control.replay(task)['events'];self.assertTrue(any(e['event_type']=='skill.used' for e in events));self.assertNotIn('private instructions',json.dumps(events))
 def test_native_budget_is_durable_and_configured_model_effort_are_generic(self):
  model='fixture-codex-model';app.CONFIG['native_call_budget']=2
  app.CONFIG['codex_reasoning_efforts_by_model']={model:['low','medium']}
  app.services.update_settings({'orchestration':{'policy':{'native_call_budget':2}}})
  control.reserve_native('codex-chatgpt',model,'medium','task-planner','planner')
  with self.assertRaisesRegex(ValueError,'Reasoning effort'):control.reserve_native('codex-chatgpt',model,'unlisted','task-review','reviewer')
  control.reserve_native('codex-chatgpt',model,'low','task-review','reviewer')
  with app.db() as c:
   roles=[r[0] for r in c.execute('SELECT role FROM paw_provider_calls WHERE provider=? ORDER BY id',( 'codex-chatgpt',))]
  self.assertEqual(roles,['planner','reviewer'])
  with self.assertRaisesRegex(ValueError,'budget'):control.reserve_native('codex-chatgpt',model,'medium')
 def test_negated_publication_constraint_is_not_a_request(self):
  self.assertNotIn('blocked_reason',app.route('Implement greeting. Do not publish.'))
  self.assertNotIn('blocked_reason',app.route('Implement greeting. Do not commit, push, or publish.'))
  self.assertIn('blocked_reason',app.route('Publish the application'))
  self.assertIn('blocked_reason',app.route('No publish; deploy now'))

 def test_negation_parser_handles_actions_outside_callers_subset(self):
  text,found=control.remove_negated_actions('Implement greeting. Do not commit, push, or publish; deploy now.',{'publish','deploy'})
  self.assertEqual(found,{'publish'})
  self.assertNotRegex(text,r'(?i)\b(?:commit|push|publish)\b')
  self.assertRegex(text,r'(?i)\bdeploy now\b')
  self.assertIn('blocked_reason',app.route('Implement greeting. Do not commit, push, or publish; deploy now.'))

 def test_http_event_authorization_and_sse_replay(self):
  task=self.task();path='/api/events?task='+task+'&revision=1'
  self.assertEqual(self.request('GET',path,auth=False)[0],401)
  code,page=self.request('GET',path);self.assertEqual(code,200);self.assertTrue(page['events'])
  conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
  conn.request('GET','/api/events/stream?task='+task+'&revision=1&after=0',headers={'Authorization':'Bearer '+self.token})
  response=conn.getresponse();self.assertEqual(response.status,200);self.assertEqual(response.getheader('Content-Type'),'text/event-stream')
  self.assertTrue(response.readline().startswith(b'id: '));event=json.loads(response.readline().decode().removeprefix('data: '));self.assertEqual(event['task_id'],task);conn.close()
  self.assertEqual(self.request('GET','/api/events?task='+task+'&revision=999')[0],409)
