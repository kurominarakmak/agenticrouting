"""Apply the preserved fixed-native patch in a temporary copy, then run the verifier."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
EXPECTED_SPEC_SHA256="c9390d7d34abe9b177df4ea6800645f40c0cef4bde9caf5f995a2384503b2aa6"
if __import__('hashlib').sha256((ROOT/'SPEC.md').read_bytes()).hexdigest()!=EXPECTED_SPEC_SHA256:
    raise SystemExit("Fixture specification hash changed")
with tempfile.TemporaryDirectory(prefix="explorer-acceptance-") as folder:
    target=Path(folder)
    for name in ("SPEC.md","explorer.py","verify_explorer.py"):
        shutil.copy2(ROOT/name,target/name)
    subprocess.run(["git","apply",str(ROOT/"accepted-native-baseline.patch")],cwd=target,check=True)
    result=subprocess.run([sys.executable,"verify_explorer.py"],cwd=target,check=False)
    if result.returncode:raise SystemExit(result.returncode)
if __import__('hashlib').sha256((ROOT/'SPEC.md').read_bytes()).hexdigest()!=EXPECTED_SPEC_SHA256:
    raise SystemExit("Fixture specification changed during acceptance replay")
