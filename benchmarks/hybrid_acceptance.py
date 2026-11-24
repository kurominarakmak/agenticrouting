"""Owner-invoked real Luna Medium acceptance. Never modifies the installed service."""
import argparse,json,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,control,dsh_tools
from benchmarks.acceptance import grounded_answer
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--directory',required=True);p.add_argument('--mode',choices=['hybrid','codex-only'],required=True);p.add_argument('--capability-results');a=p.parse_args()
base=Path(a.directory).resolve()
if base.exists():raise ValueError('Use a new isolated directory; existing state is never replaced')
base.mkdir(mode=0o700);repo=base/'repo';shutil.copytree(Path(__file__).parent/'fixtures/scorer',repo)
subprocess.run(['git','init','-q',str(repo)],check=True);subprocess.run(['git','-C',str(repo),'add','.'],check=True);subprocess.run(['git','-C',str(repo),'-c','user.name=Acceptance','-c','user.email=acceptance@example.invalid','commit','-qm','Acceptance input'],check=True)
c=json.loads(Path(a.config).read_text());c.update(codex_model='gpt-6-luna',codex_reasoning_effort='medium',native_call_budget=2 if a.mode=='hybrid' else 1,timeout=180,max_attempts=3,max_delegates=1,delegation_enabled=a.mode=='hybrid',knowledge_roots={});c['repositories']={'demo':{'path':str(repo),'verify':[sys.executable,str((Path(__file__).parent/'verify_scorer.py').resolve())]}}
if a.mode=='hybrid':
 if not a.capability_results:raise ValueError('Hybrid mode requires actual independently verified capability results')
 c['dsh']['enabled']=True
else:c['dsh']['enabled']=False
config=base/'config.json';config.write_text(json.dumps(c,indent=2));app.setup(config,base/'state')
if a.capability_results:
 source=Path(a.capability_results).resolve();data=json.loads(source.read_text());inputs=source.parent/'inputs'
 for row in data:
  if row.get('task_class')!='multi-file' or row.get('model')!=c['dsh']['model']:continue
  if not row.get('runtime_model_identity') or row['runtime_model_identity']!=control.local_identity(row['model']):raise ValueError('Capability evaluation lacks matching original model/SDK identity; rerun local acceptance')
  log=Path(row['evidence']).resolve()
  if not log.is_relative_to(source.parent):raise ValueError('Capability log outside its declared evaluation')
  verified=dsh_tools.verify_trace(log,inputs.resolve());required={'fact.txt','other.txt'};final=next(json.loads(l) for l in log.read_text().splitlines() if l.startswith('{') and json.loads(l).get('type')=='result');text=final.get('answer','');passed=required<={s['path'] for s in verified} and grounded_answer(text,'1000',[s['sha256'] for s in verified if s['path'] in required])
  control.record_capability('dsh-local',row['model'],'multi-file',passed,{'log':str(log),'acceptance':'rechecked source set, hashes and sum'},row['metrics'])
  control.record_capability('dsh-local',row['model'],'scoped-analysis',passed,{'log':str(log)},row['metrics'])
request='Implement scorer.py from README.md, rules.json and cases.csv with rigorous multi-step inspection. Consider a bounded read-only cross-check by an eligible local agent when useful. Match the specified grade boundaries, invalid inputs, clamping and rounding.'
x=app.submit(request,override='codex-chatgpt');started=time.monotonic()
for _ in range(5):
 app.worker(once=True);snap=app.snapshot(x['conversation']);t=next(t for t in snap['tasks'] if t['id']==x['task_id'])
 if t['status'] in ['done','blocked','failed','triage','review']:break
result={'mode':a.mode,'seconds':time.monotonic()-started,'parent':t,'children':[t for t in snap['tasks'] if t['parent_id']==x['task_id']],'model':'gpt-6-luna','reasoning_effort':'medium'};(base/'result.json').write_text(json.dumps(result,indent=2,default=str));print(t['status'])
if t['status']!='done':sys.exit(1)
if a.mode=='hybrid' and not result['children']:raise ValueError('Lead chose no local delegation; mixed acceptance not established')
