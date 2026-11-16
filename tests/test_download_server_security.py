"""The local download server must not expose repository internals."""
import functools
import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import download_server


class DownloadServerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'repo'
        (self.root / 'docs').mkdir(parents=True)
        (self.root / 'docs' / 'asset.txt').write_text('safe asset')
        (self.root / '.env').write_text('secret')
        (self.root / '.git').mkdir()
        (self.root / '.git' / 'config').write_text('private')
        (self.root.parent / 'outside.txt').write_text('outside secret')
        (self.root / 'escape').symlink_to(self.root.parent / 'outside.txt')
        (self.root / 'secret-link').symlink_to(self.root / '.env')
        (self.root / 'bad-index').mkdir()
        (self.root / 'bad-index' / 'index.html').symlink_to(self.root.parent / 'outside.txt')
        (self.root / 'hidden-index').mkdir()
        (self.root / 'hidden-index' / 'index.html').symlink_to(self.root / '.env')
        self.root_patch = patch.object(download_server, 'ROOT', self.root)
        self.root_patch.start()
        handler = functools.partial(download_server.DownloadHandler, directory=str(self.root))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.root_patch.stop()
        self.tmp.cleanup()

    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_docs_fallback_still_serves_assets(self):
        self.assertEqual(self.get('/asset.txt'), (200, b'safe asset'))

    def test_hidden_traversal_and_symlink_paths_are_not_served(self):
        for path in ('/.env', '/.git/config', '/%2eenv', '/..%2foutside.txt',
                     '/missing/../../outside.txt', '/escape', '/secret-link',
                     '/bad-index/', '/hidden-index/', '/%00'):
            with self.subTest(path=path):
                status, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b'secret', body)

    def test_directory_listing_disabled(self):
        self.assertEqual(self.get('/')[0], 403)


if __name__ == '__main__':
    unittest.main()
