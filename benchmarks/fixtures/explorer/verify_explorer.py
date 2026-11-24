from pathlib import Path
import hashlib,importlib.util
assert hashlib.sha256(Path('SPEC.md').read_bytes()).hexdigest()=='c9390d7d34abe9b177df4ea6800645f40c0cef4bde9caf5f995a2384503b2aa6', 'Specification was modified'
spec=importlib.util.spec_from_file_location('explorer',Path.cwd()/'explorer.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cases=[([],False,[]),(['z.txt','A.txt','b.txt'],False,['A.txt','b.txt','z.txt']),(['.env','a.txt'],False,['a.txt']),(['folder/.env','folder/Z.txt','folder/a.txt'],False,['folder/a.txt','folder/Z.txt']),(['.env','a.txt'],True,['.env','a.txt']),(['folder/a.txt','other/A.txt'],False,['folder/a.txt','other/A.txt'])]
for values,show,expected in cases:
 before=list(values);assert m.visible_entries(values,show)==expected, 'Independent Explorer acceptance failed';assert values==before, 'Input mutation'
print('6 independent Explorer cases passed; specification unchanged')
