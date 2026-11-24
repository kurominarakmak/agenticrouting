"""Owner-configured read-only MCP projection; revocation is checked on every call."""
import hashlib,json
from pathlib import Path
class External:
 def __init__(self,config,state):
  import app,services
  self.app=app;self.services=services;self.config=Path(config);app.setup(self.config,state);app.MCP_PARENT_GROUP=True
 def refresh(self):self.app.CONFIG['mcp_servers']=json.loads(self.config.read_text()).get('mcp_servers',{})
 def inventory(self):
  self.refresh();out=[]
  for server,spec in self.app.CONFIG.get('mcp_servers',{}).items():
   if not spec.get('enabled'):continue
   try:tools=self.services.mcp_request(server)['tools']
   except ValueError:continue
   for tool in tools:
    if not tool.get('authorized'):continue
    alias='external_'+hashlib.sha256((server+'\0'+tool['name']).encode()).hexdigest()[:16]
    out.append({'name':alias,'description':'Authorized read-only reference: '+server+' / '+tool['name'],'inputSchema':tool.get('inputSchema',{}),'server':server,'tool':tool['name']})
  return out
 def call(self,name,arguments):
  # Re-discovery rechecks revocation, server identity and current input schema.
  tool=next((t for t in self.inventory() if t['name']==name),None)
  if not tool:raise ValueError('External tool is revoked or unavailable')
  return self.services.mcp_request(tool['server'],'call',tool['tool'],arguments)
