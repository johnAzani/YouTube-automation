#!/usr/bin/env python3
"""High-performance range-supporting HTTP server for video preview & asset downloads."""
import http.server
import os
import re
import urllib.parse
from pathlib import Path

PORT = 8080
ROOT = Path(__file__).resolve().parent

class _RangeFileWrapper:
    def __init__(self, f, length):
        self.f = f
        self.remaining = length

    def read(self, size=-1):
        if self.remaining <= 0:
            return b''
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self.f.read(size)
        self.remaining -= len(data)
        return data

    def close(self):
        self.f.close()


class DownloadHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def translate_path(self, path):
        # Resolve path against repo root, falling back to docs/
        p = super().translate_path(path)
        if not os.path.exists(p):
            parsed = urllib.parse.urlparse(path).path.lstrip('/')
            docs_alt = ROOT / 'docs' / parsed
            if docs_alt.exists():
                return str(docs_alt)
        return p

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            return super().send_head()

        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        total_size = os.path.getsize(path)
        range_header = self.headers.get('Range')

        if range_header and range_header.startswith('bytes='):
            match = re.match(r'bytes=(\d*)-(\d*)', range_header)
            if match:
                start_str, end_str = match.groups()
                if start_str and end_str:
                    start = int(start_str)
                    end = int(end_str)
                elif start_str:
                    start = int(start_str)
                    end = total_size - 1
                elif end_str:
                    start = total_size - int(end_str)
                    end = total_size - 1
                else:
                    start = 0
                    end = total_size - 1

                start = max(0, min(start, total_size - 1))
                end = max(start, min(end, total_size - 1))
                content_length = end - start + 1

                self.send_response(206, 'Partial Content')
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Range', f'bytes {start}-{end}/{total_size}')
                self.send_header('Content-Length', str(content_length))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.end_headers()

                f.seek(start)
                return _RangeFileWrapper(f, content_length)

        # Standard non-range response
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(total_size))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')

        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if 'download' in query or (parsed.path.endswith(('.zip', '.png', '.jpg')) and not parsed.path.endswith('-poster.jpg')):
            filename = os.path.basename(parsed.path) or 'download'
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')

        self.end_headers()
        return f


if __name__ == '__main__':
    os.chdir(ROOT)
    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), DownloadHandler)
    print(f'Serving with range support and CORS on http://0.0.0.0:{PORT}')
    server.serve_forever()
