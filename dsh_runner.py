"""On-demand official DSH SDK experiment. Run only as a separately bounded child."""
import json,os,sys,time
from pathlib import Path

SDK_VERSION='0.2.2rc2'
def profile(root,model,mcp_python,config=None,state=None):
    disabled=['persistent-bash','persistent-pwsh','tool-fs','tool-working-directory','attachment-local']
    return [{'id':name,'disabled':True} for name in disabled]+[{'insert':[
        {'id':'syntropic-local-model','name':'@deepseek-ai/dsh-llm-pi-ai','config':{'providers':{'syntropic-local':{'api':'openai-completions','baseURL':'http://127.0.0.1:11434/v1','apiKeyEnv':'SYNTROPIC_LOCAL_KEY','models':[{'id':model,'contextWindow':8192,'maxTokens':1024}],'retryPolicy':{'mode':'normal','maxRetries':0}}}}},
        {'id':'syntropic-scoped-tools','name':'@deepseek-ai/dsh-mcp-client','config':{'serverName':'syntropic','transport':'stdio','command':mcp_python,'args':[str(Path(__file__).with_name('dsh_tools.py')),str(root)]+([str(config),str(state)] if config and state else [])}}
    ]}]

def main():
    request=json.load(sys.stdin)
    root=Path(request['root']).resolve();home=Path(request['home']).resolve()
    if root==Path.home() or not root.is_dir():raise ValueError('An explicit repository scope is required')
    if home==Path.home() or home.is_relative_to(Path.home()/'.dsh'):raise ValueError('An isolated execution home is required; user DSH state is refused')
    home.mkdir(parents=True,exist_ok=True,mode=0o700);home.chmod(0o700)
    patch=home/'syntropic.json';patch.write_text(json.dumps(profile(root,request['model'],request['mcp_python'],request.get('config'),request.get('state'))))
    # This dedicated child never inherits provider credentials or a user's DSH home.
    keep={k:v for k,v in os.environ.items() if k in ['PATH','HOME','TMPDIR','LANG','SYSTEMROOT']}
    os.environ.clear();os.environ.update(keep)
    from importlib.metadata import version
    if version('deepseek-harness-sdk')!=SDK_VERSION:raise ValueError('Review the SDK version before changing the pinned adapter')
    from deepseek_harness import DeepSeekHarness
    count=0;tool_calls=0;usage=[];visible_times=[];wall_started=time.time()
    def event(n):
        nonlocal count,tool_calls
        count+=1
        if n.payload.get("event",{}).get("type")=="tool/call":
            tool_calls+=1
            if tool_calls>8:raise ValueError("DSH tool-call budget exhausted")
        if count>300:raise ValueError('DSH event budget exhausted')
        event_data=n.payload.get('event',{});kind=event_data.get('type');data=event_data.get('data',{})
        if kind=='assistant/message':
            observed={k:v for k,v in data.get('usage',{}).items() if isinstance(v,(int,float))}
            if observed:usage.append(observed);print(json.dumps({'type':'usage','usage':observed,'step':data.get('step')}),flush=True)
            for packet in data.get('stream',[]):
                chunk=packet.get('chunk',{})
                stamp=packet.get('time0') if packet.get('type')=='text-chunks' else (packet.get('time') if chunk.get('type')=='block-start' and chunk.get('blockType')=='text' else None)
                if isinstance(stamp,(int,float)):visible_times.append(max(0,stamp/1000-wall_started))
        if kind in ['tool/call','tool/result','step/start','step/end','turn/start','turn/end'] or n.method=='session.status':
            print(json.dumps({'type':'runtime_event','method':n.method,'payload':n.payload}),flush=True)
    with DeepSeekHarness(dsh_home=str(home),cwd=str(root),profile='sdk-minimal',provider='syntropic-local',model=request['model'],max_tokens=1024,patches=(str(patch),),env={'SYNTROPIC_LOCAL_KEY':'local-only','DSH_CONTEXT_WINDOW':'8192'}) as harness:
        result=harness.run(request['prompt'],on_notification=event)
        print(json.dumps({'type':'result','session_id':result.session_id,'finish_reason':result.finish_reason,'answer':result.final_response,'metrics':{'ttft_seconds':min(visible_times) if visible_times else None,'usage_observations':usage,'observed_model_responses':len(usage),'tool_calls':tool_calls}}),flush=True)
        if result.finish_reason!='completed':raise ValueError('DSH input did not complete')
        if len(sys.argv)>1:Path(sys.argv[1]).write_text(result.final_response)
if __name__=='__main__':main()
