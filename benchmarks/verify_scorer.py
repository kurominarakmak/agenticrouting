import sys,importlib.util
from pathlib import Path
for name in ['README.md','SKILL.md','rules.json','cases.csv']:
 assert (Path.cwd()/name).read_bytes()==(Path(__file__).parent/'fixtures/scorer'/name).read_bytes(), 'Requirement input changed: '+name
p=Path.cwd()/'scorer.py'
spec=importlib.util.spec_from_file_location('scorer',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
for value,maximum,expected,grade in [(45,50,90,'A'),(75,100,75,'B'),(60,100,60,'C'),(-3,100,0,'D'),(103,100,100,'A'),(1,3,33.33,'D'),(89.999,100,90,'A')]:
 assert m.score(value,maximum)==expected,(value,m.score(value,maximum),expected)
 assert m.grade(value,maximum)==grade
for maximum in [0,-1]:
 try:m.score(1,maximum)
 except ValueError:pass
 else:raise AssertionError('Must reject invalid maximum')
print('9 independent acceptance cases passed')
