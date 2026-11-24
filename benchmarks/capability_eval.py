"""Repeated independent local tool acceptance, separate from native usage budgets."""
import json,subprocess,sys,time,os,signal,hashlib,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,control,profiling,dsh_tools
from benchmarks.acceptance import grounded_answer
ROOT=Path(__file__).resolve().parents[1]
def evaluate(config,state,out,repeats=2,models=('lfm2.5-thinking:latest','gemma4:latest'),selected_tasks=None):
 app.setup(config,state);out=Path(out);out.mkdir(parents=True,exist_ok=True);repo=out/'inputs';repo.mkdir(exist_ok=True)
 content={'fact.txt':'Value: 731\n','other.txt':'Other value: 269\n','SKILL.md':'Read fact.txt and other.txt using read_file. Sum their values and report the sum and both SHA256 hashes.\n'}
 for p,s in content.items():(repo/p).write_text(s)
 tasks=[('single-read','Read fact.txt using read_file. Report its value and SHA256.',{'fact.txt'},'731'),('multi-file','Read fact.txt and other.txt. Report their sum and both hashes.',{'fact.txt','other.txt'},'1000'),('skill','Read SKILL.md and use its bounded read-only method. Report the sum and both data hashes.',set(content),'1000'),('recovery','First try reading missing.txt; report it unavailable, then read fact.txt and report its value and hash.',{'fact.txt'},'731'),('thai','อ่าน fact.txt และ other.txt ด้วย read_file แล้วรายงานผลรวมพร้อม SHA256 ของทั้งสองไฟล์',{'fact.txt','other.txt'},'1000')]
 if selected_tasks:tasks=[t for t in tasks if t[0] in selected_tasks]
 results=[]
 for model in models:
  for repeat in range(repeats):
   for task,prompt,required,answer in tasks:
    req={'root':str(repo.resolve()),'home':str((out/f'home-{model.split(":")[0]}-{repeat}-{task}').resolve()),'model':model,'mcp_python':app.CONFIG.get('mcp_python',str(Path(app.CONFIG['hermes_source'])/'venv/bin/python')),'prompt':prompt}
    identity=control.local_identity(model)
    log=out/f'{model.split(":")[0]}-{repeat}-{task}.jsonl';start=time.monotonic();failure=None;passed=False;sources=[]
    with log.open('w') as f:
     child=subprocess.Popen([app.CONFIG['dsh']['python'],str(ROOT/'dsh_runner.py')],stdin=subprocess.PIPE,stdout=f,stderr=subprocess.STDOUT,text=True,start_new_session=True,env=app.clean_env());profile=profiling.Profile(child.pid,shared_ollama=True).start()
     try:
      child.communicate(json.dumps(req),timeout=100)
      if child.returncode:raise ValueError('runtime_error')
      sources=dsh_tools.verify_trace(log,repo.resolve());events=[json.loads(x) for x in log.read_text().splitlines() if x.startswith('{')];result=next((e for e in events if e.get('type')=='result'),{});text=result.get('answer','')
      expected=[hashlib.sha256(content[p].encode()).hexdigest() for p in required if p!='SKILL.md']
      passed=required<={s['path'] for s in sources} and grounded_answer(text,answer,expected)
      if task=='recovery':passed=passed and any(e.get('payload',{}).get('event',{}).get('data',{}).get('message',{}).get('isError') for e in events)
      if not passed:failure='acceptance_failed'
     except subprocess.TimeoutExpired:
      os.killpg(child.pid,signal.SIGKILL);child.wait();failure='timeout'
     except Exception as e:failure=str(e)
     finally:
      if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
      metrics=profile.finish()
    if identity is None or identity!=control.local_identity(model):passed=False;failure='model_identity_unavailable_or_changed'
    row={'runtime_model_identity':identity,'model':model,'runtime':'dsh-local','task_class':task,'repeat':repeat,'passed':passed,'failure':failure,'metrics':metrics,'sources':sources,'evidence':str(log)};results.append(row)
    control.record_capability('dsh-local',model,task,passed,{'log':str(log),'acceptance':'Required tool sources, current hashes and expected answer checked'},metrics)
    # Scoped-analysis eligibility is deliberately gated by repeated multi-file/skill passes.
    if task=='multi-file':control.record_capability('dsh-local',model,'scoped-analysis',passed,{'log':str(log),'case':task},metrics)
    with (out/'results.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(model,task,repeat,passed,round(metrics['seconds'],2),flush=True)
 (out/'results.json').write_text(json.dumps(results,indent=2));return results
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--state',required=True);p.add_argument('--out',required=True);p.add_argument('--repeats',type=int,default=2);p.add_argument('--tasks',nargs='+');p.add_argument('--models',nargs='+',default=['lfm2.5-thinking:latest','gemma4:latest']);a=p.parse_args();evaluate(a.config,a.state,a.out,a.repeats,a.models,a.tasks)
