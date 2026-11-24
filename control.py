"""Durable evidence and safe event projection in Syntropic's existing database."""
import json,time,hashlib,re,urllib.request,math
from pathlib import Path
A=None
_POS={}
_NEGATION=re.compile(r"(?i)\b(?:do not|don't|never|without|no)\s+(?:automatically\s+)?")
_ACTION_PATTERNS={
 'commit':r'commit(?:ting)?','push':r'push(?:ing)?','publish':r'publish(?:ing)?',
 'deploy':r'deploy(?:ing)?','buy':r'buy(?:ing)?','sell':r'sell(?:ing)?',
 'transfer':r'transfer(?:ring)?','withdraw':r'withdraw(?:ing)?','send':r'send(?:ing)?',
 'drop':r'drop(?:ping)?','create_pr':r'create\s+(?:a\s+)?(?:pr|pull request)'
}

def remove_negated_actions(text,actions):
 """Return text without explicitly negated action verbs and their canonical names.

 Negation applies only to the immediately following operation list in one clause,
 so "no publish; deploy now" still contains a positive deployment request.
 """
 if not isinstance(text,str):return text,set()
 names=set(actions);patterns=[(name,re.compile(r'(?i)\b(?:'+pattern+r')\b')) for name,pattern in _ACTION_PATTERNS.items()]
 removed=[];found=set()
 for clause in re.finditer(r'[^.!?;\n]+',text):
  part=clause.group(0);neg=_NEGATION.search(part)
  if not neg:continue
  cursor=neg.end();spans=[]
  while cursor<len(part):
   while cursor<len(part) and part[cursor].isspace():cursor+=1
   auto=re.match(r'(?i)automatically\s+',part[cursor:])
   if auto:cursor+=auto.end()
   match=next(((name,pattern.match(part,cursor)) for name,pattern in patterns if pattern.match(part,cursor)),None)
   if not match:break
   name,token=match;spans.append((clause.start()+token.start(),clause.start()+token.end()));found.add(name);cursor=token.end()
   separator=re.match(r'(?:\s*,\s*(?:(?:and|or)\s*)?|\s+(?:and|or)\s+)',part[cursor:],re.I)
   if not separator:break
   cursor+=separator.end()
  removed.extend(spans)
 output=text
 for start,end in reversed(removed):output=output[:start]+' '+output[end:]
 return output,found & names

SAFE={'activity','reason','tool','call_id','exit_code','is_error','source_count','source_hashes','event_count','input_tokens','output_tokens','sample_size','evidence_ids','capability','verified','runtime','model','reasoning_effort','seconds','peak_rss_bytes','cpu_seconds','timestamp_kind','role','intent','difficulty','delegation','confidence','provider','iteration','finding_count','blocking_count','stage','status','branch','url','policy'}
def bind(app):
 global A
 A=app
 with A.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS paw_agent_events(cursor INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,revision INTEGER NOT NULL,execution_id TEXT NOT NULL,sequence INTEGER NOT NULL,timestamp REAL NOT NULL,runtime TEXT,model TEXT,event_type TEXT NOT NULL,payload TEXT NOT NULL,source_key TEXT,UNIQUE(task_id,revision,execution_id,source_key));
CREATE TABLE IF NOT EXISTS paw_capabilities(id INTEGER PRIMARY KEY AUTOINCREMENT,runtime TEXT NOT NULL,model TEXT NOT NULL,task_class TEXT NOT NULL,passed INTEGER NOT NULL,created REAL NOT NULL,evidence TEXT NOT NULL,seconds REAL,peak_rss_bytes INTEGER,cpu_seconds REAL);
CREATE TABLE IF NOT EXISTS paw_native_calls(id INTEGER PRIMARY KEY AUTOINCREMENT,created REAL,model TEXT,reasoning_effort TEXT);
CREATE TABLE IF NOT EXISTS paw_provider_calls(id INTEGER PRIMARY KEY AUTOINCREMENT,created REAL NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,role TEXT NOT NULL,task_id TEXT,input_tokens INTEGER,output_tokens INTEGER,finished REAL);
CREATE INDEX IF NOT EXISTS paw_provider_calls_provider ON paw_provider_calls(provider,created);
CREATE INDEX IF NOT EXISTS paw_provider_calls_task ON paw_provider_calls(task_id,created);''')
def payload_safe(payload):
 out={}
 for k,v in payload.items():
  if k not in SAFE or not isinstance(v,(str,int,float,bool,list,type(None))):continue
  if isinstance(v,str):v=re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|token|secret)\s*[=:]\s*)\S+',r'\1[redacted]',v[:500])
  if isinstance(v,list):v=[x for x in v[:30] if isinstance(x,(str,int,float,bool))]
  out[k]=v
 return out

def emit(task_id,kind,payload=None,revision=None,execution_id=None,source_key=None,conn=None):
 def write(c):
  row=c.execute('SELECT j.revision,j.route,t.current_run_id FROM paw_jobs j JOIN tasks t ON t.id=j.task_id WHERE j.task_id=?',(task_id,)).fetchone()
  if not row or revision is not None and row['revision']!=revision:return False
  last=c.execute("SELECT execution_id FROM paw_agent_events WHERE task_id=? AND revision=? AND execution_id!='control' ORDER BY cursor DESC LIMIT 1",(task_id,row['revision'])).fetchone()
  current=row['current_run_id'] or (last[0] if last else 'control')
  if execution_id is not None and (row['current_run_id'] is None or str(execution_id)!=str(current)):return False
  route=json.loads(row['route']);runtime=route.get('runtime');worker=route.get('assignments',{}).get('worker',{})
  model=worker.get('model') or route.get('model') or (A.CONFIG.get('codex_model') if runtime=='codex-chatgpt' else (A.CONFIG.get('dsh',{}).get('model') if runtime=='dsh-local' else A.CONFIG.get('local_model')))
  inserted=c.execute('INSERT OR IGNORE INTO paw_agent_events(task_id,revision,execution_id,sequence,timestamp,runtime,model,event_type,payload,source_key) SELECT ?,?,?,COALESCE(MAX(sequence),0)+1,?,?,?,?,?,? FROM paw_agent_events WHERE task_id=? AND revision=? AND execution_id=? HAVING EXISTS(SELECT 1 FROM paw_jobs j JOIN tasks t ON t.id=j.task_id WHERE j.task_id=? AND j.revision=? AND (? IS NULL OR t.current_run_id=?))',(task_id,row['revision'],current,time.time(),runtime,model,kind,json.dumps(payload_safe(payload or {})),source_key,task_id,row['revision'],current,task_id,row['revision'],execution_id,execution_id))
  return inserted.rowcount>0
 if conn is not None:return write(conn)
 with A.db() as c:return write(c)

def validated_sources(task_id,sources,revision,execution_id):
 emit(task_id,'evidence.validated',{'source_count':len(sources),'source_hashes':[x['sha256'] for x in sources]},revision,execution_id)
 for source in sources:
  if Path(source.get('path','')).name=='SKILL.md':
   emit(task_id,'skill.used',{'activity':'Scoped SKILL.md read and source hash validated','source_hashes':[source['sha256']]},revision,execution_id)

def replay(task_id,after=0,revision=None,limit=200):
 if not isinstance(after,int) or after<0 or limit<1 or limit>200:raise ValueError('Invalid event cursor')
 with A.db() as c:
  row=c.execute('SELECT revision FROM paw_jobs WHERE task_id=?',(task_id,)).fetchone()
  if not row:raise ValueError('Task not found')
  if revision is not None and revision!=row['revision']:raise ValueError('Stale task revision; reload authoritative state')
  rows=c.execute('SELECT * FROM paw_agent_events WHERE task_id=? AND revision=? AND cursor>? ORDER BY cursor LIMIT ?',(task_id,row['revision'],after,limit)).fetchall()
 events=[dict(r)|{'payload':json.loads(r['payload'])} for r in rows]
 return {'events':events,'revision':row['revision'],'cursor':events[-1]['cursor'] if events else after,'has_more':len(events)==limit}

def ingest(path,task_id,revision,execution_id):
 if not path.exists():return
 # A child controls its log content, not event identity or the allowed projection.
 key=(str(path),task_id,revision,execution_id)
 offset,number=_POS.get(key,(0,0))
 if path.stat().st_size<offset:offset,number=0,0
 with path.open(errors='replace') as f:
  f.seek(offset)
  while number<5000:
   start=f.tell();line=f.readline()
   if not line or not line.endswith('\n'):break
   number+=1;_POS[key]=(f.tell(),number)
   if len(line)>200000:
    emit(task_id,'event.omitted',{'activity':'Oversized untrusted log record omitted'},revision,execution_id,source_key=path.name+':'+str(number));continue
   try:data=json.loads(line)
   except ValueError:continue
   e=data.get('payload',{}).get('event',{});kind=e.get('type');d=e.get('data',{});out=None;payload={}
   if kind=='tool/call':out='tool.requested';payload={'tool':d.get('name'),'call_id':d.get('callId')}
   elif kind=='tool/result':out='tool.completed';m=d.get('message',{});payload={'call_id':m.get('toolCallId'),'is_error':bool(m.get('isError'))}
   elif kind=='step/start':out='agent.step.started'
   elif kind=='turn/end':out='agent.turn.ended'
   elif data.get('type') in ['thread.started','turn.started','turn.completed','turn.failed']:out='native.'+data['type']
   elif data.get('type') in ['item.started','item.completed'] and data.get('item',{}).get('type')=='command_execution':out='tool.requested' if data['type']=='item.started' else 'tool.completed';payload={'tool':'native.command','exit_code':data.get('item',{}).get('exit_code')}
   if data.get('type')=='usage':out='usage.observed';payload={'input_tokens':data.get('usage',{}).get('inputTokens'),'output_tokens':data.get('usage',{}).get('outputTokens')}
   if out:
    accepted=emit(task_id,out,payload,revision,execution_id,source_key=path.name+':'+str(number))
    if accepted and out=='tool.requested':
     with A.db() as c:c.execute('UPDATE paw_jobs SET activity=? WHERE task_id=? AND revision=? AND EXISTS(SELECT 1 FROM tasks WHERE id=? AND current_run_id=?)',('Tool requested: '+str(payload.get('tool','native tool'))[:100],task_id,revision,task_id,execution_id))

def local_identity(model):
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as response:models=json.load(response).get('models',[])
        digest=next(m['digest'] for m in models if m['name']==model)
        from dsh_runner import SDK_VERSION
        return digest+':dsh-sdk-'+SDK_VERSION
    except (OSError,ValueError,KeyError,StopIteration):return None


def record_capability(runtime,model,task_class,passed,evidence,metrics=None):
 metrics=metrics or {}
 evidence=dict(evidence)
 if runtime=='dsh-local':evidence['runtime_model_identity']=local_identity(model)
 observed=metrics.get('observed_at')
 if observed is None and evidence.get('log'):observed=Path(evidence['log']).stat().st_mtime
 if observed is None:observed=time.time()
 if not isinstance(observed,(int,float)) or not math.isfinite(observed) or observed>time.time()+5:raise ValueError('Invalid capability observation time')
 # Owner/benchmark API only, never model supplied or browser editable.
 with A.db() as c:
  c.execute('INSERT INTO paw_capabilities(runtime,model,task_class,passed,created,evidence,seconds,peak_rss_bytes,cpu_seconds) VALUES(?,?,?,?,?,?,?,?,?)',(runtime,model,task_class,int(bool(passed)),observed,json.dumps(evidence),metrics.get('seconds'),metrics.get('peak_rss_bytes'),metrics.get('cpu_seconds')))

def capability(runtime,model,task_class,min_samples=2):
 with A.db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM paw_capabilities WHERE runtime=? AND model=? AND task_class=? AND created>? ORDER BY id DESC LIMIT 10',(runtime,model,task_class,time.time()-7*86400))]
 identity=local_identity(model) if runtime=='dsh-local' else None
 recent_count=len(rows)
 if runtime=='dsh-local':rows=[r for r in rows if identity is not None and json.loads(r['evidence']).get('runtime_model_identity')==identity]
 success=sum(r['passed'] for r in rows)
 return {'eligible':len(rows)>=min_samples and success==len(rows),'sample_size':len(rows),'evidence_ids':[r['id'] for r in rows],'task_class':task_class,'runtime_model_identity':identity,'unmatched_identity_samples':recent_count-len(rows),'scope':'Recent exact-identity acceptance evidence, not a model-quality ranking','failures':len(rows)-success}

def reserve_native(runtime='codex-chatgpt',model=None,reasoning_effort=None,task_id=None,role='worker'):
 runtime=runtime or 'codex-chatgpt'
 model=model or (A.CONFIG.get('codex_model') if runtime=='codex-chatgpt' else (A.CONFIG.get('glm',{}).get('model') if runtime=='glm-coding-plan' else A.CONFIG.get('claude_model')))
 if runtime not in ['codex-chatgpt','claude-subscription','glm-coding-plan']:raise ValueError('Unsupported native execution backend')
 if not isinstance(model,str) or not model or len(model)>200:raise ValueError('Native execution requires an explicit configured model ID')
 if runtime=='codex-chatgpt':
  reasoning_effort=reasoning_effort or A.CONFIG.get('codex_reasoning_effort')
  if not isinstance(reasoning_effort,str) or not 1<=len(reasoning_effort)<=32:raise ValueError('Native Codex requires an explicit configured reasoning effort')
  declared=A.CONFIG.get('codex_reasoning_efforts_by_model',{}).get(model)
  if declared is not None and reasoning_effort not in declared:raise ValueError('Reasoning effort is not declared for the configured model')
 elif reasoning_effort is not None:raise ValueError('Reasoning effort is not configured as supported for this native harness')
 import services
 orchestration=services.orchestration_settings();policy=orchestration['policy']
 if runtime in orchestration.get('excluded_providers',[]):raise ValueError('Native harness is excluded by owner policy')
 configured=A.CONFIG.get('native_call_budget')
 selected=policy.get('native_call_budget',configured)
 budget=min(configured,selected) if type(configured) is int and type(selected) is int else 0
 if not isinstance(budget,int) or budget<0:raise ValueError('Invalid native call budget')
 with A.db() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT COUNT(*) FROM paw_native_calls').fetchone()[0]>=budget:raise ValueError('Native call budget exhausted; no automatic fallback')
  if task_id is not None:
   per_task=policy.get('max_provider_calls_per_task',8);native_task=policy.get('max_native_calls_per_task',4)
   ceiling=A.CONFIG.get('native_task_call_budget',4)
   if any(type(x) is not int or x<1 for x in (per_task,native_task,ceiling)):raise ValueError('Invalid native per-task call budget')
   task_used=c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?',(task_id,)).fetchone()[0]
   native_used=c.execute("SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=? AND provider IN ('codex-chatgpt','claude-subscription','glm-coding-plan')",(task_id,)).fetchone()[0]
   provider_used=c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=? AND provider=?',(task_id,runtime)).fetchone()[0]
   if task_used>=per_task:raise ValueError('Per-task total provider-call budget exhausted before native execution')
   if native_used>=min(native_task,ceiling):raise ValueError('Per-task native call budget exhausted')
   if provider_used>=min(per_task,native_task,ceiling):raise ValueError('Native per-provider per-task call budget exhausted')
  c.execute('INSERT INTO paw_native_calls(created,model,reasoning_effort) VALUES(?,?,?)',(time.time(),model,reasoning_effort))
  c.execute('INSERT INTO paw_provider_calls(created,provider,model,role,task_id) VALUES(?,?,?,?,?)',(time.time(),runtime,model,role,task_id));c.commit()

def reserve_provider_call(provider,model,role,task_id,max_output_tokens,budget_calls,task_call_limit):
 if type(max_output_tokens) is not int or not 1<=max_output_tokens<=8192:raise ValueError('Invalid provider output-token limit')
 if type(task_call_limit) is not int or not 1<=task_call_limit<=100:raise ValueError('Invalid provider per-task call limit')
 if budget_calls is not None and (type(budget_calls) is not int or budget_calls<1):raise ValueError('Invalid provider call budget')
 with A.db() as c:
  c.execute('BEGIN IMMEDIATE')
  import services
  if provider in services.orchestration_settings().get('excluded_providers',[]):raise ValueError('Provider is excluded by owner policy')
  if task_id is not None:
   total=services.orchestration_settings()['policy'].get('max_provider_calls_per_task',8)
   if type(total) is not int or total<1:raise ValueError('Invalid task provider-call budget')
   if c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?',(task_id,)).fetchone()[0]>=total:
    raise ValueError('Configured total per-task provider-call budget exhausted')
  if budget_calls is not None and c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE provider=?',(provider,)).fetchone()[0]>=budget_calls:
   raise ValueError('Configured provider request budget exhausted; no fallback was attempted')
  if task_id is not None and c.execute('SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=? AND provider=?',(task_id,provider)).fetchone()[0]>=task_call_limit:
   raise ValueError('Configured provider per-task request budget exhausted')
  c.execute('INSERT INTO paw_provider_calls(created,provider,model,role,task_id) VALUES(?,?,?,?,?)',(time.time(),provider,model,role,task_id));c.commit()

def finish_provider_call(provider,model,role,task_id,usage):
 def count(value):return value if type(value) is int and 0<=value<2**31 else None
 with A.db() as c:
  row=c.execute('SELECT id FROM paw_provider_calls WHERE provider=? AND model=? AND role=? AND task_id IS ? AND finished IS NULL ORDER BY id DESC LIMIT 1',(provider,model,role,task_id)).fetchone()
  if row:c.execute('UPDATE paw_provider_calls SET input_tokens=?,output_tokens=?,finished=? WHERE id=?',(count(usage.get('input_tokens')),count(usage.get('output_tokens')),time.time(),row['id']))

def public_log(path):
    output=[]
    for line in path.read_text(errors='replace').splitlines()[:5000]:
        try:x=json.loads(line)
        except ValueError:continue
        e=x.get('payload',{}).get('event',{});kind=e.get('type') or x.get('type')
        if kind in ['tool/call','tool/result']:
            d=e.get('data',{});m=d.get('message',{})
            output.append({'type':kind,'tool':d.get('name'),'call_id':d.get('callId') or m.get('toolCallId'),'is_error':bool(m.get('isError'))})
        elif kind in ['thread.started','turn.started','turn.completed','turn.failed','step/start','step/end','turn/start','turn/end','result']:
            output.append({'type':kind,'usage':x.get('usage'),'finish_reason':x.get('finish_reason')})
    return '\n'.join(json.dumps(x) for x in output)

def native_budget():
    with A.db() as c:used=c.execute('SELECT COUNT(*) FROM paw_native_calls').fetchone()[0]
    import services
    configured=A.CONFIG.get('native_call_budget')
    requested=services.orchestration_settings()['policy'].get('native_call_budget',configured)
    limit=min(configured,requested) if type(configured) is int and type(requested) is int else 0
    remaining=max(0,limit-used) if type(limit) is int and limit>=0 else 0
    return {'used':used,'limit':limit,'remaining':remaining,'scope':'Finite owner-configured call budget, not subscription quota'}

def catalog():
    with A.db() as c:
        return [dict(r) for r in c.execute('SELECT runtime,model,task_class,COUNT(*) AS sample_size,SUM(passed) AS passed,MAX(created) AS last_observed,AVG(seconds) AS mean_seconds,MAX(peak_rss_bytes) AS observed_peak_rss_bytes,AVG(cpu_seconds) AS mean_cpu_seconds FROM paw_capabilities GROUP BY runtime,model,task_class')]
