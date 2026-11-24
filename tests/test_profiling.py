import subprocess,sys,time,unittest
import profiling
class ProfilingTests(unittest.TestCase):
 def test_real_child_resource_sample(self):
  child=subprocess.Popen([sys.executable,'-c','import time; x=bytearray(8_000_000); time.sleep(.6)'])
  profile=profiling.Profile(child.pid).start();child.wait();result=profile.finish()
  self.assertGreater(result['peak_rss_bytes'],1_000_000);self.assertGreater(result['samples'],0);self.assertGreaterEqual(result['cpu_seconds'],0);self.assertIsNone(result['gpu_memory_bytes'])
