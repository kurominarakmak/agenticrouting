"""Local PR preparation and separately approved, reconciled GitHub delivery."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.parse
import services
import control

SECRET = re.compile(r"(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s,;]{6,}|\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b)")
PRIVATE_PATH = re.compile(r"(?i)(?:^|/)(?:\.env(?:\.|$)|[^/]*(?:secret|credential|token|private.key)[^/]*)")
NO_AUTOMATIC_DELIVERY = re.compile(r"(?i)\b(?:do not|don't|never|without|no)\s+(?:automatically\s+)?(?:commit|push|publish(?:ing)?|create\s+(?:a\s+)?(?:pr|pull request))\b")


def _policy(repo):
    value=services.orchestration_settings().get('pr_policy',{}).get(repo,{})
    return {'require_commit_approval':True,'require_push_approval':True,
            'automatic_pr_after_verification':False,'require_owner_review_before_done':True}|value


def _get(task_id):
    with services.A.db() as c:
        row=c.execute('SELECT * FROM paw_pr_delivery WHERE task_id=?',(task_id,)).fetchone()
        job=c.execute('SELECT * FROM paw_jobs WHERE task_id=?',(task_id,)).fetchone()
    return (dict(row) if row else None),(dict(job) if job else None)


def _git(worktree,*args,timeout=20):
    result=subprocess.run(['git','-C',str(worktree),*args],env=services.A.clean_env(),capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise ValueError('Git delivery precondition failed; inspect the local repository configuration')
    return result.stdout.strip()


def _changed_paths(worktree):
    tracked=_git(worktree,'diff','--name-only','-z','HEAD').split('\0')
    untracked=_git(worktree,'ls-files','--others','--exclude-standard','-z').split('\0')
    values=sorted(set(x for x in tracked+untracked if x))
    if not values or len(values)>500:raise ValueError('PR preparation requires 1–500 changed files')
    for name in values:
        if name.startswith('/') or '..' in Path(name).parts or PRIVATE_PATH.search(name):raise ValueError('PR delivery refuses a private or out-of-scope file')
        path=Path(worktree)/name
        if not path.exists():
            if path.is_symlink():raise ValueError('PR delivery refuses symlink changes')
            try:_git(worktree,'ls-files','--error-unmatch','--',name,timeout=10);tracked=True
            except ValueError:tracked=False
            if tracked:continue
            raise ValueError('PR delivery refuses an unresolved missing path')
        if path.is_symlink() or not path.is_file() or path.stat().st_size>1_000_000:raise ValueError('PR delivery refuses symlinks or files larger than one megabyte')
        raw=path.read_bytes()
        if b'\0' in raw or SECRET.search(raw.decode('utf-8','ignore')):raise ValueError('Secret scan blocked repository publication')
    return values


def _actor(value):
    if value not in ('authenticated-owner','owner-policy'):raise ValueError('Repository delivery requires an authenticated owner action')
    return value


def _journal(task_id,revision,action,state,**details):
    with services.A.db() as c:
        row=c.execute('SELECT action_log FROM paw_pr_delivery WHERE task_id=? AND revision=?',(task_id,revision)).fetchone()
        if not row:raise ValueError('Prepared delivery revision changed before action journaling')
        log=json.loads(row['action_log'] or '{}')
        previous=log.get(action,{})
        previous.update({'state':state,'updated_at':time.time()}|details)
        log[action]=previous
        c.execute('UPDATE paw_pr_delivery SET action_log=? WHERE task_id=? AND revision=?',(json.dumps(log),task_id,revision))
    return log[action]


def prepare(task,job,worktree,receipt,diff):
    app=services.A
    branch=_git(worktree,'branch','--show-current')
    expected='codex/paw-'+task.id
    if branch!=expected:raise ValueError('Prepared branch does not match the isolated task worktree')
    if not isinstance(receipt,dict) or not isinstance(receipt.get('workspace_hashes'),dict) or receipt['workspace_hashes']!=app.workspace_hashes(worktree):
        raise ValueError('Worktree changed after verification; rerun acceptance before PR preparation')
    paths=_changed_paths(worktree)
    if not isinstance(receipt,dict) or receipt.get('revision')!=job['revision'] or receipt.get('exit_code')!=0:
        raise ValueError('PR preparation requires current passing verification evidence')
    policy=_policy(job['repo']);publish_allowed=not bool(SECRET.search(diff))
    if not publish_allowed:publish_reason='Patch secret scan found a credential-like value; publication is disabled.'
    else:publish_reason='Owner approval is required for each repository mutation.'
    with app.db() as c:
        prompts=c.execute("SELECT text FROM paw_messages WHERE task_id=? AND role='user' ORDER BY id",(task.id,)).fetchall()
    request='\nFollow-up: '.join(x['text'] for x in prompts) or task.title
    request=re.sub(r"[\r\n\t]+"," ",request).strip()
    request=SECRET.sub('[redacted]',request)
    title=request[:120].strip(' .') or ('Syntropic task '+task.id)
    if SECRET.search(title):title='Review implementation for task '+task.id
    cycles=receipt.get('review_cycles',[]);review=receipt.get('review',{})
    auto_policy=bool(policy['automatic_pr_after_verification'] and not policy['require_commit_approval'] and not policy['require_push_approval'])
    delivery_note=('The owner policy preauthorizes commit, push, and PR creation after verification.' if auto_policy else
                   'The owner must authorize commit, push, and PR creation separately.')
    body=('## Summary\n\n'+request[:2000]+'\n\n## Verification\n\n'
          +'- Configured acceptance command passed (exit code 0).\n'
          +'- Independent reviewer: '+('approved' if review.get('approved') else ('not configured' if not review else 'findings recorded in Syntropic artifacts'))+'.\n'
          +'- Worker/review iterations: '+str(max(1,len(cycles)))+'.\n\n## Changed files\n\n'
          +'\n'.join('- `'+name+'`' for name in paths)+'\n\n## Residual notes\n\n'
          +'This PR was prepared locally. '+delivery_note+' Syntropic does not merge or deploy.')
    folder=app.STATE/'artifacts'/task.id;folder.mkdir(parents=True,exist_ok=True)
    patch_path=folder/('prepared-pr-%d.patch'%job['revision']);body_path=folder/('prepared-pr-%d.md'%job['revision'])
    patch_path.write_text(diff);body_path.write_text(body)
    action_log={'base_sha':_git(worktree,'rev-parse','HEAD')}
    metadata={'task_id':task.id,'revision':job['revision'],'branch':branch,'title':title,'body_path':str(body_path.relative_to(app.STATE)),
              'patch_path':str(patch_path.relative_to(app.STATE)),'patch_sha256':hashlib.sha256(diff.encode()).hexdigest(),
              'prepared_at':time.time(),'publish_allowed':publish_allowed,'status':'prepared' if publish_allowed else 'blocked_secret_scan',
              'policy':policy,'changed_files':paths,'action_log':action_log,'commit_sha':None,'commit_actor':None,'commit_at':None,'push_actor':None,
              'pushed_at':None,'pr_actor':None,'pr_url':None,'pr_at':None}
    with app.db() as c:
        c.execute('INSERT OR REPLACE INTO paw_pr_delivery(task_id,revision,branch,title,body_path,patch_path,patch_sha256,prepared_at,publish_allowed,status,changed_files,commit_sha,commit_actor,commit_at,push_actor,pushed_at,pr_actor,pr_url,pr_at,action_log) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (task.id,job['revision'],branch,title,metadata['body_path'],metadata['patch_path'],metadata['patch_sha256'],metadata['prepared_at'],int(publish_allowed),metadata['status'],json.dumps(paths),None,None,None,None,None,None,None,None,json.dumps(action_log)))
    receipt_path=folder/('pr-delivery-%d.json'%job['revision']);receipt_path.write_text(json.dumps(metadata,indent=2))
    control.emit(task.id,'pr.prepared',{'branch':branch,'status':metadata['status'],'policy':'explicit owner policy applies to commit and push','reason':publish_reason})
    return metadata


def snapshot(task_id):
    row,job=_get(task_id)
    if not row:return None
    policy=_policy(job['repo']) if job else {}
    row['changed_files']=json.loads(row['changed_files'] or '[]')
    row['action_log']=json.loads(row.get('action_log') or '{}')
    row['policy']=policy
    row['patch_available']=bool((services.A.STATE/row['patch_path']).is_file())
    row['body_available']=bool((services.A.STATE/row['body_path']).is_file())
    return row


def _check_current(task_id,actor):
    actor=_actor(actor);row,job=_get(task_id)
    if not row or not job:raise ValueError('No prepared PR patch exists for this task')
    if job['cancel'] or job['paused']:raise ValueError('Cancelled or paused tasks cannot perform repository delivery actions')
    if row['revision']!=job['revision']:raise ValueError('Prepared patch is stale for the current task revision')
    if not row['publish_allowed']:raise ValueError('PR publication was blocked by the secret scan')
    repo=services.A.CONFIG['repositories'][job['repo']]
    worktree=services.A.STATE/'worktrees'/task_id
    if not worktree.is_dir() or not worktree.resolve().is_relative_to((services.A.STATE/'worktrees').resolve()):raise ValueError('Task worktree is unavailable')
    expected='codex/paw-'+task_id
    if _git(worktree,'branch','--show-current')!=expected or row['branch']!=expected:raise ValueError('Task branch or worktree identity changed')
    current=_git(worktree,'rev-parse','HEAD')
    journal=json.loads(row.get('action_log') or '{}');commit_intent=journal.get('commit',{})
    if not row['commit_sha'] and commit_intent.get('state')=='intent' and current!=journal.get('base_sha'):
        parent=_git(worktree,'rev-parse','HEAD^')
        subject=_git(worktree,'show','-s','--format=%s','HEAD')
        committed=sorted(x for x in _git(worktree,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines() if x)
        if parent!=journal.get('base_sha') or subject!=row['title'] or committed!=json.loads(row['changed_files']) or _git(worktree,'status','--porcelain'):
            raise ValueError('Interrupted local commit is ambiguous; inspect the branch before retrying')
        with services.A.db() as c:c.execute("UPDATE paw_pr_delivery SET commit_sha=?,commit_actor=?,commit_at=?,status='committed' WHERE task_id=? AND revision=?",(current,commit_intent.get('actor','authenticated-owner'),time.time(),task_id,row['revision']))
        _journal(task_id,row['revision'],'commit','reconciled',commit_sha=current,actor=commit_intent.get('actor','authenticated-owner'))
        row,_=_get(task_id)
    if row['commit_sha']:
        if current!=row['commit_sha'] or _git(worktree,'status','--porcelain'):
            raise ValueError('Committed worktree changed after PR preparation')
    else:
        diff=services.A.change_patch(worktree)
        if hashlib.sha256(diff.encode()).hexdigest()!=row['patch_sha256']:raise ValueError('Worktree changed after PR preparation; rerun verification')
    return actor,row,job,repo,worktree


def _commit_locked(task_id,actor):
    actor,row,job,repo,worktree=_check_current(task_id,actor);policy=_policy(job['repo'])
    if actor=='owner-policy' and policy['require_commit_approval']:raise ValueError('Owner policy still requires separate commit approval')
    if row['commit_sha']:return snapshot(task_id)
    paths=_changed_paths(worktree)
    _git(worktree,'diff','--check','HEAD')
    _git(worktree,'add','--',*paths)
    staged=_git(worktree,'diff','--cached','--binary','HEAD')
    if SECRET.search(staged):raise ValueError('Staged patch secret scan blocked commit')
    _git(worktree,'var','GIT_AUTHOR_IDENT');_git(worktree,'var','GIT_COMMITTER_IDENT')
    hooks=services.A.STATE/'git-no-hooks';hooks.mkdir(mode=0o700,exist_ok=True)
    title=row['title']
    _journal(task_id,row['revision'],'commit','intent',actor=actor,patch_sha256=row['patch_sha256'])
    result=subprocess.run(['git','-C',str(worktree),'-c','core.hooksPath='+str(hooks),'commit','-m',title],env=services.A.clean_env(),capture_output=True,text=True,timeout=30)
    if result.returncode:raise ValueError('Local commit failed; inspect owner Git identity and staged worktree state')
    sha=_git(worktree,'rev-parse','HEAD')
    with services.A.db() as c:c.execute("UPDATE paw_pr_delivery SET commit_sha=?,commit_actor=?,commit_at=?,status='committed' WHERE task_id=? AND revision=?",(sha,actor,time.time(),task_id,row['revision']))
    _journal(task_id,row['revision'],'commit','complete',actor=actor,patch_sha256=row['patch_sha256'],commit_sha=sha)
    control.emit(task_id,'pr.commit.created',{'branch':row['branch'],'status':'committed locally','reason':'Explicit authenticated owner action'})
    return snapshot(task_id)


def commit(task_id,actor):
    with services.A.gate():return _commit_locked(task_id,actor)


def _push_locked(task_id,actor):
    actor,row,job,repo,worktree=_check_current(task_id,actor);policy=_policy(job['repo'])
    if actor=='owner-policy' and policy['require_push_approval']:raise ValueError('Owner policy still requires separate push approval')
    if not row['commit_sha']:raise ValueError('Commit approval and local commit are required before push')
    remote_url=_git(worktree,'remote','get-url','origin')
    parsed=urllib.parse.urlsplit(remote_url)
    if parsed.username or parsed.password or parsed.scheme not in ('https','ssh','file',''):
        raise ValueError('Configured origin remote is not an allowed delivery destination')
    _journal(task_id,row['revision'],'push','intent',actor=actor,commit_sha=row['commit_sha'],remote='origin',branch=row['branch'])
    remote_sha=_git(worktree,'ls-remote','--heads','origin',row['branch'])
    if remote_sha:
        observed=remote_sha.split()[0]
        if observed!=row['commit_sha']:raise ValueError('Remote branch exists at another commit; no overwrite was attempted')
    else:
        result=subprocess.run(['git','-C',str(worktree),'push','--set-upstream','origin',row['branch']],env=services.A.clean_env(),capture_output=True,text=True,timeout=45)
        if result.returncode:raise ValueError('Push did not confirm; reconcile the remote branch before retrying')
        remote_sha=_git(worktree,'ls-remote','--heads','origin',row['branch'])
        if not remote_sha or remote_sha.split()[0]!=row['commit_sha']:raise ValueError('Push result is ambiguous; no retry was attempted')
    with services.A.db() as c:c.execute("UPDATE paw_pr_delivery SET push_actor=?,pushed_at=?,status='pushed' WHERE task_id=? AND revision=?",(actor,time.time(),task_id,row['revision']))
    _journal(task_id,row['revision'],'push','reconciled',actor=actor,commit_sha=row['commit_sha'],remote='origin',branch=row['branch'])
    control.emit(task_id,'pr.branch.pushed',{'branch':row['branch'],'status':'pushed and reconciled','reason':'Explicit authenticated owner action; remote hash confirmed'})
    return snapshot(task_id)


def push(task_id,actor):
    with services.A.gate():return _push_locked(task_id,actor)


def _create_pr_locked(task_id,actor):
    actor,row,job,repo,worktree=_check_current(task_id,actor);policy=_policy(job['repo'])
    if actor=='owner-policy' and (not policy['automatic_pr_after_verification'] or policy['require_commit_approval'] or policy['require_push_approval']):
        raise ValueError('Owner policy does not preauthorize automatic PR creation')
    if not row['commit_sha'] or not row['pushed_at']:raise ValueError('Confirmed push is required before PR creation')
    gh=shutil.which('gh')
    if not gh:raise ValueError('GitHub CLI is unavailable; PR creation remains unverified')
    existing=subprocess.run([gh,'pr','list','--head',row['branch'],'--json','url,state'],cwd=worktree,env=services.A.clean_env(),capture_output=True,text=True,timeout=30)
    if existing.returncode:raise ValueError('Could not reconcile existing pull requests; no create retry was attempted')
    try:items=json.loads(existing.stdout)
    except ValueError:raise ValueError('GitHub pull-request reconciliation returned malformed data')
    url=None
    if items:
        candidate=items[0].get('url')
        if not isinstance(candidate,str) or not candidate.startswith('https://github.com/'):raise ValueError('GitHub did not confirm a canonical PR URL')
        url=candidate
    else:
        base=repo.get('default_branch')
        if not base:
            head=_git(worktree,'symbolic-ref','refs/remotes/origin/HEAD')
            base=head.rsplit('/',1)[-1]
        if not isinstance(base,str) or not re.fullmatch(r'[A-Za-z0-9._/-]{1,120}',base):raise ValueError('Repository default branch is not safely configured')
        body=(services.A.STATE/row['body_path']).read_text()
        _journal(task_id,row['revision'],'create_pr','intent',actor=actor,branch=row['branch'],commit_sha=row['commit_sha'])
        result=subprocess.run([gh,'pr','create','--title',row['title'],'--body',body,'--head',row['branch'],'--base',base],cwd=worktree,env=services.A.clean_env(),capture_output=True,text=True,timeout=60)
        if result.returncode:raise ValueError('GitHub PR creation did not confirm; reconcile by branch before retrying')
        candidate=result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ''
        if not candidate.startswith('https://github.com/'):raise ValueError('GitHub did not return a canonical PR URL')
        # Read after write to reconcile an ambiguous response before storing success.
        check=subprocess.run([gh,'pr','list','--head',row['branch'],'--json','url,state'],cwd=worktree,env=services.A.clean_env(),capture_output=True,text=True,timeout=30)
        if check.returncode:raise ValueError('PR may exist, but GitHub readback failed; reconcile before retrying')
        try:confirmed=json.loads(check.stdout)
        except ValueError:raise ValueError('GitHub PR readback was malformed')
        if not any(x.get('url')==candidate for x in confirmed):raise ValueError('GitHub PR URL was not confirmed by readback')
        url=candidate
    with services.A.db() as c:c.execute("UPDATE paw_pr_delivery SET pr_actor=?,pr_url=?,pr_at=?,status='in_review' WHERE task_id=? AND revision=?",(actor,url,time.time(),task_id,row['revision']))
    _ensure_pr_review_task(task_id,job,url,row['revision'])
    _journal(task_id,row['revision'],'create_pr','reconciled',actor=actor,branch=row['branch'],commit_sha=row['commit_sha'],url=url)
    control.emit(task_id,'pr.created',{'branch':row['branch'],'url':url,'status':'in review','reason':'GitHub confirmed the pull request URL'})
    return snapshot(task_id)


def create_pr(task_id,actor):
    with services.A.gate():return _create_pr_locked(task_id,actor)


def automatic_delivery(task_id):
    row,job=_get(task_id)
    if not row or not job:return None
    policy=_policy(job['repo'])
    # Saving this explicit combination is an owner preauthorization; every default keeps
    # the commit, push and PR action on a separate authenticated button.
    if not (policy['automatic_pr_after_verification'] and not policy['require_commit_approval'] and not policy['require_push_approval']):
        return snapshot(task_id)
    with services.A.db() as c:
        requests=[r['text'] for r in c.execute("SELECT text FROM paw_messages WHERE task_id=? AND role='user' ORDER BY id",(task_id,))]
    prohibited=set()
    for request in requests:
        _,found=control.remove_negated_actions(request,{'commit','push','publish','create_pr'})
        prohibited.update(found)
    if prohibited:
        _journal(task_id,row['revision'],'automatic_delivery','blocked_task_constraint',reason='Task request prohibited automated commit, push, or publication')
        return snapshot(task_id)
    if not row['commit_sha']:commit(task_id,'owner-policy')
    row,_=_get(task_id)
    if not row['pushed_at']:push(task_id,'owner-policy')
    row,_=_get(task_id)
    if not row['pr_url']:create_pr(task_id,'owner-policy')
    return snapshot(task_id)


def _ensure_pr_review_task(task_id,job,url,revision):
    app=services.A
    with app.db() as c:
        row=c.execute('SELECT review_task_id FROM paw_pr_delivery WHERE task_id=? AND revision=?',(task_id,revision)).fetchone()
        if not row:raise ValueError('Prepared PR revision changed during delivery')
        if row['review_task_id']:
            return row['review_task_id']
        repo=app.CONFIG['repositories'][job['repo']]
        review_id=app.KB.create_task(c,title=('Review pull request: '+url)[:160],
            body=json.dumps({'source_task':task_id,'revision':revision,'pull_request':url,
                             'instruction':'Human review is pending. Syntropic may only read GitHub state; it must not merge or deploy.'}),
            assignee='default',created_by='syntropic-pr-delivery',workspace_kind='dir',workspace_path=repo['path'],
            max_runtime_seconds=app.CONFIG.get('timeout',300),max_retries=1)
        route={'mode':'job','runtime':'github-pr-review','task_kind':'pr-review','source_task':task_id,
               'source_revision':revision,'pull_request':url,'decision_source':'authorized-delivery'}
        c.execute("INSERT INTO paw_jobs(task_id,conversation,repo,route,kind,parent_id,stage,activity) VALUES(?,?,?,?,?,?,?,?)",
                  (review_id,job['conversation'],job['repo'],json.dumps(route),'pr_review',task_id,'review','GitHub pull request awaits human review'))
        if not app.KB.request_review(c,review_id,summary='GitHub confirmed pull request '+url,
                                     metadata={'source_task':task_id,'revision':revision,'pull_request':url},force=True):
            raise ValueError('Could not create the durable pull-request review task')
        c.execute('UPDATE paw_pr_delivery SET review_task_id=? WHERE task_id=? AND revision=?',(review_id,task_id,revision))
    control.emit(review_id,'pr.review.pending',{'url':url,'status':'human review pending','reason':'GitHub confirmed pull request; merge and deploy remain disabled'})
    return review_id


def refresh_pr(review_task_id,actor):
    with services.A.gate():return _refresh_pr_locked(review_task_id,actor)


def _refresh_pr_locked(review_task_id,actor):
    _actor(actor)
    with services.A.db() as c:
        job=c.execute('SELECT * FROM paw_jobs WHERE task_id=? AND kind=?',(review_task_id,'pr_review')).fetchone()
        task=services.A.KB.get_task(c,review_task_id) if job else None
        route=json.loads(job['route']) if job else {}
    if not job:raise ValueError('Task is not a pull-request review task')
    source=route.get('source_task');delivery,_=_get(source)
    if not delivery or delivery.get('review_task_id')!=review_task_id or delivery.get('pr_url')!=route.get('pull_request'):
        raise ValueError('Pull-request review identity does not match the prepared delivery')
    gh=shutil.which('gh')
    if not gh:raise ValueError('GitHub CLI is unavailable; pull-request state cannot be verified')
    worktree=services.A.STATE/'worktrees'/source
    result=subprocess.run([gh,'pr','view',delivery['pr_url'],'--json','url,state'],cwd=worktree,env=services.A.clean_env(),capture_output=True,text=True,timeout=30)
    if result.returncode:raise ValueError('GitHub state readback failed; no task status change was made')
    try:data=json.loads(result.stdout)
    except ValueError:raise ValueError('GitHub state readback was malformed')
    if data.get('url')!=delivery['pr_url'] or data.get('state') not in ['OPEN','CLOSED','MERGED']:
        raise ValueError('GitHub did not confirm the expected pull-request state')
    state=data['state'].lower()
    # refresh_pr owns the gate for the complete GitHub readback and status update.
    # Reacquiring the process lock here can deadlock (flock is not recursive).
    with services.A.db() as c:
        c.execute('UPDATE paw_pr_delivery SET status=? WHERE task_id=? AND revision=?',('merged' if state=='merged' else ('closed' if state=='closed' else 'in_review'),source,delivery['revision']))
        if state=='merged' and task.status=='review':
            if not services.A.KB.complete_task(c,review_task_id,summary='GitHub confirmed merged pull request '+delivery['pr_url'],
                    metadata={'source_task':source,'revision':delivery['revision'],'pull_request':delivery['pr_url'],'github_state':'MERGED'},fire_lifecycle_hook=False):
                raise ValueError('Merged pull request could not complete the review task')
            c.execute("UPDATE paw_jobs SET stage='done',activity='GitHub confirmed merged pull request' WHERE task_id=?",(review_task_id,))
    if state=='merged':services.stage(review_task_id,'done','GitHub confirmed merged pull request; Syntropic did not merge or deploy')
    control.emit(review_task_id,'pr.review.reconciled',{'url':delivery['pr_url'],'status':state,'reason':'Authenticated read-only GitHub status check'})
    return {'task_id':review_task_id,'pull_request':delivery['pr_url'],'status':state}
