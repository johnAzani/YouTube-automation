#!/usr/bin/env python3
import http.server
import os
import urllib.parse
from pathlib import Path

PORT = 8080
ROOT = Path(__file__).resolve().parent

class DownloadHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS and allow downloads from iframe
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        
        # Check if the requested file is in media/ or ends with .png, .jpg, .zip
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if "download" in query or path.endswith((".zip", ".png", ".jpg")):
            filename = os.path.basename(path) or "download"
            # Set attachment disposition to force browser save dialog
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            
        super().end_headers()

if __name__ == "__main__":
    os.chdir(ROOT)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), DownloadHandler)
    print(f"Serving with force-download on http://0.0.0.0:{PORT}")
    server.serve_forever()
