from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse


HOST = "0.0.0.0"
PORT = 8090

stored_token=""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/":
            body = b"<h1>NETSEC</h1>"
            content_type = "text/html; charset=utf-8"
            status = 200

        elif parsed_url.path == "/claim":
            body = stored_token.encode("utf-8")
            content_type = "application/json; charset=utf-8"
            status = 200
        else:
            body = b'{"error": "Path not Found"}'
            content_type = "application/json; charset=utf-8"
            status = 404

        self.response(status, content_type, body)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path=="/claim":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            if body != "":
                global stored_token
                stored_token = body
                self.response(200, "application/json; charset=utf-8", b'{"message": "Token stored successfully"}')

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}\n")

    def response(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = HTTPServer((HOST, PORT), RequestHandler)

print(f"Server listening at http://{HOST}:{PORT}")
print("Press Ctrl+C to stop the server.")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nStopping server...")
finally:
    server.server_close()
