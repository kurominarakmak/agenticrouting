"""Do not execute a child until its recoverable process identity has been recorded."""
import json
import os
from pathlib import Path
import sys
import time

release=Path(sys.argv[1]);parent=int(sys.argv[2]);argv=json.loads(sys.argv[3])
for _ in range(200):
    if os.getppid()!=parent:sys.exit(75)
    if release.exists():
        release.unlink()
        os.execvpe(argv[0],argv,os.environ)
    time.sleep(.05)
sys.exit(75)
