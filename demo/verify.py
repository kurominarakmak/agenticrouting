"""Operator-owned acceptance check, outside the agent's writable worktree."""
import importlib.util
from pathlib import Path

path = Path.cwd() / 'greeting.py'
assert path.is_file(), 'Expected greeting.py in the isolated worktree'
spec = importlib.util.spec_from_file_location('candidate', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.greet('Ada') == 'Hello, Ada!'
assert module.greet('') == 'Hello, friend!'
print('PASS: greeting.py exists and both acceptance examples match')
