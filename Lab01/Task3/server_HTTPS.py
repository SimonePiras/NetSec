from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
import ssl
from urllib.parse import urlparse
import json
import uuid

HOST = "0.0.0.0"
PORT = 8443

cookies = {}


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/":
            self.response(200, "text/plain", b"Hello, HTTPS!")

        elif parsed_url.path == "/me":
            if "Cookie" not in self.headers:
                body = json.dumps({"error": "No session cookie"}).encode("utf-8")
                self.response(401, "application/json; charset=utf-8", body)
                return
            cookie = self.headers["Cookie"]
            sessionID = cookie.split("=")[1]
            username = cookies.get(sessionID)

            if username:
                body = json.dumps({"user": username}).encode("utf-8")
                self.response(200, "application/json; charset=utf-8", body)
            else:
                body = json.dumps({"error": "Invalid session"}).encode("utf-8")
                self.response(401, "application/json; charset=utf-8", body)

        elif parsed_url.path == "/whoami":
            certificate = self.connection.getpeercert()
            if not certificate:
                body = b"Client certificate required"
                self.response(401, "text/plain; charset=utf-8", body)
                return

            common_name = None

            for subject_part in certificate.get("subject", ()):
                for attribute, value in subject_part:
                    if attribute == "commonName":
                        common_name = value
                        break
                if common_name is not None:
                    break

        
            self.response(200, "text/plain; charset=utf-8", common_name.encode("utf-8"))

        else:
            self.response(404, "text/plain", b"Page not found!")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        content_type = self.headers.get("Content-Type", "")
        if parsed_url.path == "/login":
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
            username = data.get("user")

            password = data.get("password")

            if password == "netsec":
                sessionID = str(uuid.uuid4())
                cookies[sessionID] = username
                body = json.dumps({"message": f"Welcome, {username}!"}).encode("utf-8")
                self.response(200, "application/json; charset=utf-8", body, f"session={sessionID}; Secure; HttpOnly")
            else:
                body = json.dumps({"error": "Invalid credentials"}).encode("utf-8")
                self.response(401, "application/json; charset=utf-8", body)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}\n")

    def response(self, status, content_type, body, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


CERT_DIR = "NetSec/Lab01/Task3/Certificate"
MTLS_PORT = 8444

https_server = ThreadingHTTPServer((HOST, PORT), RequestHandler)

https_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
https_context.load_cert_chain(
    certfile=f"{CERT_DIR}/server.crt",
    keyfile=f"{CERT_DIR}/server.key",
)

https_server.socket = https_context.wrap_socket(
    https_server.socket,
    server_side=True,
)


mtls_server = ThreadingHTTPServer((HOST, MTLS_PORT), RequestHandler)

mtls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
mtls_context.load_cert_chain(
    certfile=f"{CERT_DIR}/server.crt",
    keyfile=f"{CERT_DIR}/server.key",
)

mtls_context.load_verify_locations(cafile=f"{CERT_DIR}/ca.crt")

mtls_context.verify_mode = ssl.CERT_REQUIRED

mtls_server.socket = mtls_context.wrap_socket(
    mtls_server.socket,
    server_side=True,
)


print(f"HTTPS server listening at https://localhost:{PORT}")
print(f"mTLS server listening at https://localhost:{MTLS_PORT}")
print("Press Ctrl+C to stop the servers.")

https_thread = threading.Thread(
    target=https_server.serve_forever,
    daemon=True,
)
mtls_thread = threading.Thread(
    target=mtls_server.serve_forever,
    daemon=True,
)

https_thread.start()
mtls_thread.start()

try:
    https_thread.join()
    mtls_thread.join()
except KeyboardInterrupt:
    print("\nStopping the servers.")
finally:
    https_server.shutdown()
    mtls_server.shutdown()
    https_server.server_close()
    mtls_server.server_close()
