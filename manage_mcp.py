"""Local owner-only MCP registration. Never accepts model-generated commands."""
import argparse,json,os,re,tempfile
from pathlib import Path
from urllib.parse import urlsplit

def validate(spec):
 if not isinstance(spec,dict) or spec.get('transport') not in ['stdio','streamable-http']:raise ValueError('Explicit supported transport required')
 if spec['transport']=='stdio':
  path=Path(spec.get('command',''))
  if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK):raise ValueError('Existing absolute owner-selected executable required')
 else:
  url=urlsplit(spec.get('url',''))
  if url.username or url.password or url.query or url.fragment or url.scheme!='https' and not (url.scheme=='http' and url.hostname in ['127.0.0.1','localhost','::1']):raise ValueError('HTTPS or loopback URL required; credentials must use a secret file')
 tools=spec.get('allowed_tools',{})
 if not isinstance(tools,dict) or any(v!='read' for v in tools.values()):raise ValueError('Only explicit read permissions may be registered')
 for value in [*spec.get('env',{}).values(),*spec.get('headers',{}).values()]:
  if not isinstance(value,str) or not value.startswith('secret:'):raise ValueError('Provider credentials must reference owner-only secret files')
 return spec

def register(config,name,spec):
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',name):raise ValueError('Invalid server name')
 spec=validate(spec);path=Path(config);content=json.loads(path.read_text());content.setdefault('mcp_servers',{})[name]=spec
 fd,temporary=tempfile.mkstemp(dir=path.parent,prefix='.mcp-config-')
 try:
  with os.fdopen(fd,'w') as f:json.dump(content,f,indent=2);f.flush();os.fsync(f.fileno())
  os.chmod(temporary,0o600);os.replace(temporary,path)
 finally:Path(temporary).unlink(missing_ok=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--name',required=True);p.add_argument('--spec',required=True);a=p.parse_args();register(a.config,a.name,json.loads(Path(a.spec).read_text()));print('Read-only MCP registration saved; existing credentials were not printed.')
