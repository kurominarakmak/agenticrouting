"""Deterministic routing audit; no inference, credentials or database writes."""
import json,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
CASES=[('How many legs does a dog have?','chat'),('What is a git worktree?','chat'),('How should I backtest a strategy?','chat'),('Could you explain stochastic calculus?','chat'),('Can you please clarify this architecture?','chat'),('I want you to fix this bug','job'),("I'd like you to implement a function",'job'),('Please refactor the code','job'),('Implement a greeting function','job'),('What is the latest stock price?','lookup'),('Transfer money to my account','job')]
def no_inference(*a,**kw):raise AssertionError('Unexpected local triage')
with patch.object(app,'local_call',no_inference),patch.object(app.services,'select_runtime',side_effect=lambda d,o:d):
 start=time.perf_counter();rows=[{'request':q,'expected':kind,'actual':app.route(q)['mode']} for q,kind in CASES];elapsed=time.perf_counter()-start
print(json.dumps({'cases':rows,'adaptive_correct':sum(r['actual']==r['expected'] for r in rows),'always_chat_correct':sum(k=='chat' for _,k in CASES),'always_job_correct':sum(k=='job' for _,k in CASES),'elapsed_ms':elapsed*1000,'scope':'Small explicit rule regression set, not a model quality or general routing benchmark.'},indent=2))
assert all(r['actual']==r['expected'] for r in rows)
