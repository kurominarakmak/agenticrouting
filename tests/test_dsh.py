import json,tempfile,unittest
from pathlib import Path
import dsh_tools,dsh_runner
class DSHTests(unittest.TestCase):
    def test_tool_scope_and_secret_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'fact.txt').write_text('731');(root/'token').write_text('private')
            self.assertEqual(dsh_tools.inspect(root,'fact.txt')['text'],'731')
            for name in ['../outside','token','.env','config.json']:
                with self.assertRaises(ValueError):dsh_tools.inspect(root,name)
            (root/'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):dsh_tools.inspect(root,'escape')
    def test_profile_only_mounts_local_model_and_scoped_read_tools(self):
        patch=dsh_runner.profile(Path('/tmp/repo'),'local-model','/usr/bin/python3')
        disabled={p['id'] for p in patch if p.get('disabled')}
        self.assertTrue({'persistent-bash','persistent-pwsh','tool-fs','tool-working-directory','attachment-local'}<=disabled)
        text=json.dumps(patch);self.assertIn('http://127.0.0.1:11434/v1',text);self.assertNotIn('https://',text)

    def test_handoff_rejects_missing_tool_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/'events.jsonl';log.write_text('{"type":"result","answer":"success"}\n')
            with self.assertRaisesRegex(ValueError,'No successful'):dsh_tools.verify_trace(log,Path(d))

    def test_file_excerpts_are_bounded_and_keep_full_file_provenance(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);content=('line\n'*500).encode();(root/'data.txt').write_bytes(content)
            excerpt=dsh_tools.inspect(root,'data.txt',3,6)
            self.assertEqual(excerpt['text'],'line\n'*4);self.assertEqual(excerpt['sha256'],hashlib.sha256(content).hexdigest());self.assertTrue(excerpt['truncated'])
            with self.assertRaises(ValueError):dsh_tools.inspect(root,'data.txt',1,500)
            (root/'wide.txt').write_text('ก'*3000);limited=dsh_tools.inspect(root,'wide.txt');self.assertLessEqual(len(limited['text'].encode()),4000);self.assertTrue(limited['truncated'])
