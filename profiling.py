"""Sample process-tree RSS/CPU through macOS ps; model GPU allocation is unknown."""
import subprocess,time,threading
class Profile:
 def __init__(self,pid,shared_ollama=False):self.shared_ollama=shared_ollama;self.shared_peak=0;self.shared_cpu={};self.pid=pid;self.peak=0;self.cpu={};self.first=None;self.started=time.monotonic();self.stop=threading.Event();self.samples=0
 def sample(self):
  try:raw=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,rss=,time=,comm='],text=True,timeout=3)
  except subprocess.SubprocessError:return
  rows={}
  for line in raw.splitlines():
   try:
    pid,parent,rss,clock,command=line.split(None,4);days=0
    if '-' in clock:day,clock=clock.split('-',1);days=int(day)*86400
    parts=clock.split(':');seconds=0
    for part in parts:seconds=seconds*60+float(part)
    rows[int(pid)]=(int(parent),int(rss)*1024,seconds+days,command)
   except ValueError:continue
  descendants={self.pid}
  for _ in range(20):
   found={p for p,(parent,_,_,_) in rows.items() if parent in descendants};new=found-descendants
   if not new:break
   descendants|=new
  if self.shared_ollama:
   shared={p for p,(_,_,_,name) in rows.items() if 'ollama' in name.lower()}
   self.shared_peak=max(self.shared_peak,sum(rows[p][1] for p in shared))
   for p in shared:
    if p not in self.shared_cpu:self.shared_cpu[p]=[rows[p][2],rows[p][2]]
    else:self.shared_cpu[p][1]=rows[p][2]
  self.peak=max(self.peak,sum(rows[p][1] for p in descendants if p in rows));self.samples+=1
  for p in descendants:
   if p in rows:self.cpu[p]=max(self.cpu.get(p,0),rows[p][2])
 def run(self):
  while not self.stop.wait(.2):self.sample()
 def start(self):self.sample();self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start();return self
 def finish(self):
  self.stop.set();self.thread.join();self.sample()
  return {'observed_at':time.time(),'seconds':time.monotonic()-self.started,'peak_rss_bytes':self.peak,'cpu_seconds':sum(self.cpu.values()),'shared_ollama_peak_rss_bytes':self.shared_peak if self.shared_ollama else None,'shared_ollama_cpu_seconds':sum(max(0,b-a) for a,b in self.shared_cpu.values()) if self.shared_ollama else None,'samples':self.samples,'sampling_interval_seconds':.2,'gpu_memory_bytes':None,'scope':'Sampled child process tree only. Shared Ollama server, Metal/GPU allocation and between-sample peaks excluded.'}
