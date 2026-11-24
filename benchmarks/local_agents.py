"""Repeat the same grounded question through direct inference and the official DSH loop."""
import argparse,json,os,subprocess,tempfile,time,urllib.request,hashlib,signal
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--python',required=True);p.add_argument('--mcp-python',required=True);p.add_argument('--repeats',type=int,default=3);args=p.parse_args()
root=Path(__file__).resolve().parents[1];results=[]
with tempfile.TemporaryDirectory(prefix='syntropic-agent-eval-') as d:
    base=Path(d);repo=base/'repo';repo.mkdir();content='The measured fixture value is 731.\n';(repo/'fact.txt').write_text(content);sha=hashlib.sha256(content.encode()).hexdigest()
    for i in range(args.repeats):
        for runtime in ['direct-ollama','dsh-local']:
            prompt='Read fact.txt. Report the measured value and SHA256. Use the read_file tool if available. Do not guess.'
            started=time.monotonic();error=None;answer='';tools=False
            try:
                if runtime=='direct-ollama':
                    data={'model':'lfm2.5-thinking:latest','messages':[{'role':'user','content':prompt+'\nAvailable reference: '+json.dumps({'path':'fact.txt','sha256':sha,'text':content})}],'stream':False,'think':False,'options':{'num_predict':1024,'temperature':0}}
                    request=urllib.request.Request('http://127.0.0.1:11434/api/chat',json.dumps(data).encode(),{'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=90) as response:answer=json.load(response)['message']['content']
                else:
                    req={'root':str(repo),'home':str(base/f'home-{i}'),'model':'lfm2.5-thinking:latest','mcp_python':args.mcp_python,'prompt':prompt}
                    child=subprocess.Popen([args.python,str(root/'dsh_runner.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
                    try:stdout,stderr=child.communicate(json.dumps(req),timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGKILL);child.communicate();raise
                    result=subprocess.CompletedProcess(child.args,child.returncode,stdout,stderr)
                    events=[]
                    for line in result.stdout.splitlines():
                        try:events.append(json.loads(line))
                        except ValueError:pass
                    final=next((e for e in events if e.get('type')=='result'),{})
                    answer=final.get('answer','');tools=any(e.get('payload',{}).get('event',{}).get('type')=='tool/result' and not e['payload']['event'].get('data',{}).get('message',{}).get('isError') for e in events)
                    if result.returncode:error=result.stderr[-500:]
            except Exception as e:error=str(e)
            row={'runtime':runtime,'repeat':i,'seconds':time.monotonic()-started,'answer_grounded': '731' in answer and sha in answer,'tool_result_observed':tools,'error':error,'peak_ram_bytes':None,'cpu_seconds':None,'ttft_seconds':None}
            results.append(row);print(json.dumps(row),flush=True)
print(json.dumps({'scope':'Repeated tiny file-grounding task only; no real market data, native comparison, RAM/GPU/CPU or intelligence benchmark. Direct inference receives the same reference content upfront; DSH must retrieve it.','results':results}),flush=True)
