"""A cancellable inference-only local subagent; model output is never executed."""
import json
from pathlib import Path
import sys
import app

request=json.load(sys.stdin)
app.CONFIG={'local_model':request['model']}
answer=app.local_call(request['messages'])
Path(sys.argv[1]).write_text(answer)
print(json.dumps({'model':request['model'],'endpoint':'loopback','completed':True}))
