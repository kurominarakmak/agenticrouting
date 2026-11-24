"""Real project configuration audit, independently checked against current source files."""
import json,subprocess,sys,signal,os,re,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,profiling,dsh_tools
parser=argparse.ArgumentParser();parser.add_argument('--dsh-python',required=True);parser.add_argument('--mcp-python',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
expected=json.loads((root/'config.example.json').read_text());sdk=(root/'requirements-dsh.txt').read_text().strip().split('==')[1]
references=[dsh_tools.inspect(root,name) for name in ['config.example.json','requirements-dsh.txt']]
prompt='Inspect config.example.json and requirements-dsh.txt. Return only JSON with codex_model, reasoning_effort (from codex_reasoning_effort), sdk_version (from the SDK requirement), dsh_enabled (boolean), and sources (map of filename to full-file SHA256). Use read_file when available. Do not guess configuration.'
rows=[]
for model in ['lfm2.5-thinking:latest','gemma4:latest']:
 for mode in ['direct-ollama','dsh-local']:
  for repeat in range(2):
   if mode=='dsh-local':argv=[args.dsh_python,str(root/'dsh_runner.py')];request={'root':str(root),'home':str(out/f'home-{model.split(":")[0]}-{repeat}'),'model':model,'mcp_python':args.mcp_python,'prompt':prompt}
   else:argv=[sys.executable,str(Path(__file__).with_name('direct_probe.py'))];request={'model':model,'prompt':prompt+'\nController-provided read-only references: '+json.dumps(references)}
   path=out/f'{mode}-{model.split(":")[0]}-{repeat}.jsonl';error=None;passed=False;answer='';result={}
   with path.open('w') as log:
    child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=app.clean_env(),text=True,start_new_session=True);profile=profiling.Profile(child.pid,shared_ollama=True).start()
    try:
     child.communicate(json.dumps(request),timeout=130)
     if child.returncode:raise ValueError('runtime_failed')
     records=[json.loads(l) for l in path.read_text().splitlines() if l.startswith('{')];result=next((r for r in records if r.get('type')=='result'),records[-1]);answer=result.get('answer','');body=re.sub(r'^```(?:json)?\s*|\s*```$','',answer.strip());data=json.loads(body)
     passed=data.get('codex_model')==expected['codex_model'] and data.get('reasoning_effort')=='medium' and data.get('sdk_version')==sdk and data.get('dsh_enabled') is expected['dsh']['enabled'] and all(data.get('sources',{}).get(r['path'])==r['sha256'] for r in references)
     if mode=='dsh-local':passed=passed and {r['path'] for r in references}<={s['path'] for s in dsh_tools.verify_trace(path,root)}
     if not passed:error='independent_acceptance_failed'
    except Exception as e:error=type(e).__name__
    finally:
     if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
     metrics=profile.finish()
   row={'model':model,'mode':mode,'repeat':repeat,'passed':bool(passed and not error),'error':error,'metrics':metrics,'observed_usage':result.get('metrics') or result.get('usage'),'ttft_seconds':result.get('ttft_seconds') or result.get('metrics',{}).get('ttft_seconds'),'log':str(path),'task_class':'project-config-audit'};rows.append(row);print(model,mode,repeat,row['passed'],flush=True)
   (out/'results.json').write_text(json.dumps(rows,indent=2))
