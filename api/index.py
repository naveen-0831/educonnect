from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write('NAKED TEST: IF YOU SEE THIS, VERCEL IS UPDATING'.encode('utf-8'))
        return
node_identifier: app = handler # Just in case Vercel looks for app
