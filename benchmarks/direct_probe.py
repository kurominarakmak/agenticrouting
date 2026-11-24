"""One streamed loopback inference with observed Ollama timings and usage."""
import json,sys,time,urllib.request
from acceptance import final_answer
request=json.load(sys.stdin);started=time.monotonic();first=None;text='';usage={}
body={'model':request['model'],'messages':[{'role':'user','content':request['prompt']}],'stream':True,'think':False,'options':{'num_ctx':8192,'num_predict':1024,'temperature':0},'keep_alive':'2m'}
req=urllib.request.Request('http://127.0.0.1:11434/api/chat',json.dumps(body).encode(),{'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=100) as response:
 for line in response:
  event=json.loads(line);chunk=event.get('message',{}).get('content','')
  if chunk and first is None:first=time.monotonic()-started
  text+=chunk
  if event.get('done'):usage={k:event.get(k) for k in ['prompt_eval_count','eval_count','load_duration','prompt_eval_duration','eval_duration','total_duration']}
print(json.dumps({'answer':final_answer(text),'ttft_seconds':first,'seconds':time.monotonic()-started,'usage':usage}))
