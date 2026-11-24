import json,unittest
from pathlib import Path
import test_app as base
import app,services,manage_mcp
from external_mcp import External
class ExternalTests(unittest.TestCase):
 setUp=base.PilotTests.setUp
 tearDown=base.PilotTests.tearDown
 def setup_provider(self):
  path=self.root/'external-config.json';data=dict(app.CONFIG)
  spec={'enabled':True,'transport':'stdio','command':str(Path(app.CONFIG['hermes_source'])/'venv/bin/python'),'args':[str(app.ROOT/'tests/external_fixture.py')],'allowed_tools':{'read_number':'read'},'finance':True}
  path.write_text(json.dumps(data));manage_mcp.register(path,'fixture',spec);return path
 def test_external_protocol_validation_permission_and_revocation(self):
  path=self.setup_provider();bridge=External(path,self.state);tools=bridge.inventory();self.assertEqual(len(tools),1);name=tools[0]['name']
  value=bridge.call(name,{'offset':2});self.assertIn('742',json.dumps(value))
  with self.assertRaises(ValueError):bridge.call(name,{'offset':'not an integer'})
  with self.assertRaises(ValueError):services.mcp_request('fixture','call','place_order',{})
  data=json.loads(path.read_text());data['mcp_servers']['fixture']['enabled']=False;path.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'revoked'):bridge.call(name,{'offset':1})
 def test_provider_credential_is_redacted_from_returned_results(self):
  path=self.setup_provider();folder=self.state/'secrets';folder.mkdir(exist_ok=True)
  secret=folder/'fixture.json';secret.write_text(json.dumps({'READ_FIXTURE_KEY':'private-fixture-credential-12345'}));secret.chmod(0o600)
  data=json.loads(path.read_text());data['mcp_servers']['fixture'].update(secret_file='fixture.json',env={'READ_FIXTURE_KEY':'secret:READ_FIXTURE_KEY'});path.write_text(json.dumps(data))
  bridge=External(path,self.state);tool=bridge.inventory()[0];result=bridge.call(tool['name'],{'offset':1})
  self.assertNotIn('private-fixture-credential',json.dumps(result));self.assertIn('[redacted]',json.dumps(result));self.assertIn('provenance',result)
 def test_registration_rejects_inline_credentials_and_write_permission(self):
  for spec in [{'transport':'streamable-http','url':'https://example.invalid','allowed_tools':{'write':'write'}},{'transport':'streamable-http','url':'https://example.invalid','allowed_tools':{},'headers':{'Authorization':'Bearer private'}}]:
   with self.assertRaises(ValueError):manage_mcp.validate(spec)
