"""Install and operate only this application's macOS user services and private proxy."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import sqlite3
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
LABEL='local.personal-ai-work.'
RUNTIME=Path.home()/'Library/Application Support/Personal AI Work'


def run(argv,check=True):
    return subprocess.run(argv,check=check,capture_output=True,text=True,timeout=25)


def plist(mode):
    state=RUNTIME/'state';(state/'logs').mkdir(parents=True,exist_ok=True,mode=0o700)
    return {'Label':LABEL+mode,'ProgramArguments':[sys.executable,str(RUNTIME/'app.py'),mode],
            'WorkingDirectory':str(RUNTIME),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,
            'ProcessType':'Background','ExitTimeOut':15,'AbandonProcessGroup':False,
            'StandardOutPath':str(state/'logs'/(mode+'.log')),'StandardErrorPath':str(state/'logs'/(mode+'.log')),
            'EnvironmentVariables':{'HOME':str(Path.home()),'PATH':os.environ.get('PATH','/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin')}}


def deploy():
    RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700)
    for filename in ['app.py','control.py','profiling.py','services.py','workflows.py','mcp_bridge.py','child_runner.py','local_runner.py','dsh_runner.py','dsh_tools.py','external_mcp.py','providers.py','supervisor.py','pr_delivery.py','output_safety.py','index.html','style.css','app.js','components.js']:
        shutil.copy2(ROOT/filename,RUNTIME/filename)
    shutil.copytree(ROOT/'assets',RUNTIME/'assets',dirs_exist_ok=True)
    if (ROOT/'frontend/dist').exists():
        shutil.copytree(ROOT/'frontend/dist',RUNTIME/'frontend/dist',dirs_exist_ok=True)
    shutil.copytree(ROOT/'docs',RUNTIME/'docs',dirs_exist_ok=True)
    first_deploy=not (RUNTIME/'state').exists()
    if first_deploy and (ROOT/'state').exists():
        shutil.copytree(ROOT/'state',RUNTIME/'state',ignore=shutil.ignore_patterns('backups','logs','*.lock','child.json','child.release','processes.json','inline-*.json'))
    (RUNTIME/'state').mkdir(parents=True,exist_ok=True,mode=0o700)
    config_path=ROOT/'config.json'
    if not config_path.exists():shutil.copy2(ROOT/'config.example.json',config_path)
    config=json.loads(config_path.read_text())
    def runtime_arg(value):
        path=Path(value).expanduser()
        source=path if path.is_absolute() else (ROOT/path).resolve()
        if source.is_relative_to(ROOT) and source.exists():return str(RUNTIME/source.relative_to(ROOT))
        return value
    demo=RUNTIME/'demo';demo.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'demo/verify.py',demo/'verify.py')
    demo_repo=ROOT/'demo/repo'
    if not demo_repo.exists():
        demo_repo.mkdir(parents=True)
        shutil.copy2(ROOT/'demo/seed/README.md',demo_repo/'README.md')
    if not (demo_repo/'.git').exists():
        run(['git','init',str(demo_repo)])
        run(['git','-C',str(demo_repo),'add','README.md'])
        run(['git','-C',str(demo_repo),'-c','user.name=Personal AI Work Demo','-c','user.email=demo@example.invalid','commit','-m','Initialize disposable acceptance fixture'])
    if not (demo/'repo/.git').exists():
        run(['git','clone','--no-hardlinks',str(demo_repo),str(demo/'repo')])
    # Only this application's own demo and notes are relocated; user repositories are never moved.
    for entry in config['repositories'].values():
        path=Path(entry['path']).expanduser()
        if not path.is_absolute():path=ROOT/path
        path=path.resolve()
        entry['path']=str(demo/'repo') if path==demo_repo.resolve() else str(path)
        entry['verify']=[runtime_arg(x) for x in entry.get('verify',[])]
    for entry in config.get('knowledge_roots',{}).values():
        path=Path(entry['path']).expanduser()
        if not path.is_absolute():path=ROOT/path
        path=path.resolve()
        if path.is_relative_to(ROOT):entry['path']=str(RUNTIME/path.relative_to(ROOT))
    (RUNTIME/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (RUNTIME/'state').chmod(0o700)
    # Refresh relocated source paths; stale hashes stay excluded until the explicit sync.
    database=RUNTIME/'state/tasks.db'
    if first_deploy and database.exists():
        c=sqlite3.connect(database)
        try:
            c.execute("DELETE FROM paw_chunks");c.execute("DELETE FROM paw_sources");c.commit()
        finally:c.close()
    import app
    app.setup(RUNTIME/'config.json',RUNTIME/'state')
    for name in ['project_notes','demo_repository']:
        if name in app.services.roots():app.services.index_root(name)


def install():
    if sys.platform!='darwin':raise ValueError('macOS launchd is required; run server and worker directly on other platforms')
    processfile=ROOT/'state/processes.json'
    if processfile.exists():
        for pid in json.loads(processfile.read_text()).values():
            found=run(['/bin/ps','-p',str(pid),'-o','command='],False).stdout
            if str(ROOT/'app.py') in found:
                try:os.kill(pid,signal.SIGTERM)
                except ProcessLookupError:pass
        time.sleep(.5)
    for mode in ['serve','worker']:run(['launchctl','bootout','gui/'+str(os.getuid())+'/'+LABEL+mode],False)
    deploy()
    folder=Path.home()/'Library/LaunchAgents';folder.mkdir(parents=True,exist_ok=True)
    for mode in ['serve','worker']:
        path=folder/(LABEL+mode+'.plist');run(['launchctl','bootout','gui/'+str(os.getuid())+'/'+LABEL+mode],False)
        path.write_bytes(plistlib.dumps(plist(mode)));path.chmod(0o600)
        result=run(['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)],False)
        if result.returncode:raise ValueError('launchd bootstrap failed for '+mode+'; inspect macOS service permissions and state/logs')
    return status()


def status():
    result={}
    for mode in ['serve','worker']:
        out=run(['launchctl','print','gui/'+str(os.getuid())+'/'+LABEL+mode],False)
        lines=out.stdout.splitlines()
        result[mode]={'loaded':out.returncode==0,'details':[l.strip() for l in lines if l.strip().startswith(('state =','pid =','last exit code ='))]}
    return result


def stop():
    for mode in ['serve','worker']:run(['launchctl','bootout','gui/'+str(os.getuid())+'/'+LABEL+mode],False)
    return {'stopped':True,'data_preserved':True}


def remote():
    import shutil
    executable=shutil.which('tailscale')
    if not executable:raise ValueError('Install and sign in to the official Tailscale client first')
    data=json.loads(run([executable,'status','--json']).stdout)
    hostname=data.get('Self',{}).get('DNSName','').rstrip('.')
    if data.get('BackendState')!='Running' or not hostname.endswith('.ts.net'):raise ValueError('Tailscale must be online with a .ts.net hostname')
    origin='https://'+hostname+':8443'
    current=json.loads(run([executable,'serve','status','--json']).stdout or '{}')
    occupied=current.get('Web',{}).get(hostname+':8443')
    if occupied and '127.0.0.1:8787' not in json.dumps(occupied):raise ValueError('Tailscale port 8443 already serves another application; nothing was changed')
    result=run([executable,'serve','--bg','--https=8443','http://127.0.0.1:8787'],False)
    verified=json.loads(run([executable,'serve','status','--json']).stdout or '{}')
    if result.returncode or hostname+':8443' not in verified.get('Web',{}):
        for config in [ROOT/'config.json',RUNTIME/'config.json']:
            if config.exists():
                content=json.loads(config.read_text());content['remote_origin']='';config.write_text(json.dumps(content,indent=2)+'\n')
        raise ValueError('Tailscale Serve is not enabled for this tailnet. Its administrator must enable Serve; no remote endpoint is claimed. Local services remain available.')
    for config in [ROOT/'config.json',RUNTIME/'config.json']:
        if config.exists():
            content=json.loads(config.read_text());content['remote_origin']=origin
            temp=config.with_suffix('.tmp');temp.write_text(json.dumps(content,indent=2)+'\n');temp.replace(config)
    for mode in ['serve','worker']:run(['launchctl','kickstart','-k','gui/'+str(os.getuid())+'/'+LABEL+mode],False)
    return {'url':origin,'scope':'private tailnet only; token authentication still required','iphone_test':'not performed','funnel_enabled':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['install','restart','stop','status','remote']);args=p.parse_args()
    try:print(json.dumps({'install':install,'restart':install,'stop':stop,'status':status,'remote':remote}[args.action](),indent=2))
    except (ValueError,OSError,subprocess.SubprocessError,json.JSONDecodeError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
