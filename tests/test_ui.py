"""Static UI serving must not broaden filesystem access."""
import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import app

class StaticUITests(unittest.TestCase):
    def test_built_ui_default_legacy_fallback_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'index.html').write_text('legacy')
            base=root/'frontend/dist';base.mkdir(parents=True);(base/'index.html').write_text('react')
            (root/'config.json').write_text('private')
            with patch.object(app,'ROOT',root),patch.object(app,'CONFIG',{'remote_origin':''}):
                server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                def get(path):
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                    conn.request('GET',path);r=conn.getresponse();out=(r.status,r.read().decode());conn.close();return out
                try:
                    self.assertEqual(get('/'),(200,'react'))
                    self.assertEqual(get('/ui/'),(200,'react'))
                    self.assertEqual(get('/legacy/'),(200,'legacy'))
                    self.assertEqual(get('/ui/../../../config.json')[0],404)
                    (base/'index.html').unlink()
                    self.assertEqual(get('/'),(200,'legacy'))
                finally:server.shutdown();thread.join();server.server_close()
