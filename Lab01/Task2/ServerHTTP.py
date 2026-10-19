from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
from random import randint

HOST = "0.0.0.0"
PORT = 8080

dictionary = {}


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/":
            body = b"<h1>NETSEC</h1>"
            content_type = "text/html; charset=utf-8"
            status = 200

        elif parsed_url.path == "/echo":
            query = parse_qs(parsed_url.query)
            message = query.get("msg", [""])[0]

            response = {"msg": message}

            body = json.dumps(response).encode("utf-8")
            content_type = "application/json; charset=utf-8"
            status = 200

        elif parsed_url.path.startswith("/notes"):

            id = parsed_url.path.split("/")[-1] if len(parsed_url.path.split("/")) > 2 else None

            if id is not None and id.isdigit():
                id = int(id)
                text = dictionary.get(id)

                if text is not None:
                    response = {"id": id, "text": text}
                    body = json.dumps(response).encode("utf-8")
                    content_type = "application/json; charset=utf-8"
                    status = 200
                else:
                    body = b'{"error": "Note not found"}'
                    content_type = "application/json; charset=utf-8"
                    status = 404
            else:
                body = b'{"error": "Invalid or missing ID"}'
                content_type = "application/json; charset=utf-8"
                status = 404

        else:
            body = b'{"error": "Path not Found"}'
            content_type = "application/json; charset=utf-8"
            status = 404

        self.response(status, content_type, body)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        content_type = self.headers.get("Content-Type")

        if parsed_url.path == "/notes":
            if content_type != "application/json":
                body = json.dumps({"error": "Content-Type must be application/json"}).encode("utf-8")
                self.response(415, "application/json; charset=utf-8", body)
                return

            content_length = self.headers.get("Content-Length")
            length = int(content_length)
            request_body = self.rfile.read(length)

            try:
                data = json.loads(request_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = json.dumps({"error": "Invalid JSON"}).encode("utf-8")
                self.response(400, "application/json; charset=utf-8", body)
                return

            if "text" not in data:
                body = json.dumps({"error": "Missing 'text' field"}).encode("utf-8")
                self.response(400, "application/json; charset=utf-8", body)
                return

            text = data.get("text")

            if not isinstance(text, str):
                body = json.dumps({"error": "'text' field must be a string"}).encode("utf-8")
                self.response(400, "application/json; charset=utf-8", body)
                return

            id = randint(1, 1000000)
            dictionary[id] = text
            response = {"id": id}

            body = json.dumps(response).encode("utf-8")

            self.response(201, "application/json; charset=utf-8", body)

    def do_DELETE(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path.startswith("/notes"):
            id = parsed_url.path.split("/")[-1] if len(parsed_url.path.split("/")) > 2 else None

            if id is not None and id.isdigit():
                id = int(id)
                if id in dictionary:
                    del dictionary[id]
                    body = b'{"message": "Note deleted successfully"}'
                    status = 204
                else:
                    body = b'{"error": "Note not found"}'
                    status = 404
            else:
                body = b'{"error": "Invalid or missing ID"}'
                status = 404
        else:
            body = b'{"error": "Path not Found"}'
            status = 404

        self.response(status, "application/json; charset=utf-8", body)

    def do_PUT(self):
        self.not_allowed()

    def do_PATCH(self):
        self.not_allowed()

    def do_OPTIONS(self):
        self.not_allowed()

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}\n")

    def response(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def not_allowed(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path.startswith("/notes"):
            self.response(405, "application/json; charset=utf-8", b'{"error": "Method not allowed"}')


server = HTTPServer((HOST, PORT), RequestHandler)

print(f"Server listening at http://{HOST}:{PORT}")
print("Press Ctrl+C to stop the server.")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nStopping server...")
finally:
    server.server_close()
