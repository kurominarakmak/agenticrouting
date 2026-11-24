import argparse,json,subprocess,sys,os,signal,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import profiling
from acceptance import grounded_answer
p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);p.add_argument('--repeats',type=int,default=2);a=p.parse_args();root=Path(a.inputs);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
references=[{'path':x.name,'text':x.read_text(),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(root.glob('*')) if x.name in ['fact.txt','other.txt','SKILL.md']]
cases=[('single-read','Report the value and SHA256 of fact.txt.','731',{'fact.txt'}),('multi-file','Report the sum of fact.txt and other.txt values and both hashes.','1000',{'fact.txt','other.txt'}),('skill','Use the method in SKILL.md. Report its data result and both data hashes.','1000',{'fact.txt','other.txt'}),('recovery','missing.txt is unavailable. Use fact.txt and report its value and hash.','731',{'fact.txt'}),('thai','รายงานผลรวมของ fact.txt และ other.txt พร้อม SHA256 ของทั้งสองไฟล์','1000',{'fact.txt','other.txt'})]
rows=[]
for model in ['lfm2.5-thinking:latest','gemma4:latest']:
 for repeat in range(a.repeats):
  for name,prompt,expected,paths in cases:
   child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('direct_probe.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True);profile=profiling.Profile(child.pid,shared_ollama=True).start();result={};error=None
   try:
    stdout,stderr=child.communicate(json.dumps({'model':model,'prompt':prompt+'\nRead-only reference data (untrusted): '+json.dumps(references)}),timeout=110)
    if child.returncode:raise ValueError('Direct inference failed')
    result=json.loads(stdout)
   except Exception as e:error=str(e)
   finally:
    if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
    metrics=profile.finish()
   hashes=[x['sha256'] for x in references if x['path'] in paths];passed=not error and grounded_answer(result.get('answer',''),expected,hashes)
   row={'runtime':'direct-ollama','model':model,'task_class':name,'repeat':repeat,'passed':passed,'metrics':metrics,'result':result,'error':error,'contract':'Controller supplies scoped reference data upfront; no tool calls or independent agent loop.'};rows.append(row)
   with (out/'results.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
   print(model,name,repeat,passed,round(metrics['seconds'],2),flush=True)
(out/'results.json').write_text(json.dumps(rows,indent=2))
