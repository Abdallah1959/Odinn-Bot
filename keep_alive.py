from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import os

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Odinn Bot is Alive and Running 24/7!")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def run():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()