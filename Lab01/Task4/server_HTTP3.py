import asyncio
import hashlib
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration

HOST = "0.0.0.0"
PORT = 4433

BASE_DIR = Path(__file__).parent
CERT_DIR = BASE_DIR / "Certificate"


# ---------------------------------------------------------------------
# Classic HTTPS server: TCP 4433
# ---------------------------------------------------------------------


class HTTPSRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = b"Hello, classic HTTPS!"
            self.response(200, "text/plain", body, 'Alt-Svc: h3=":4433"')
        elif self.path == "/proto":
            if self.request_version == "HTTP/1.1":
                body = b"HTTP/1.1"
            elif self.request_version == "HTTP/2":
                body = b"HTTP/2"
            self.response(200, "text/plain", body)
        else:
            body = b"Not found"
            self.response(404, "text/plain", body)

    def log_message(self, format, *args):
        print(f"HTTPS {self.client_address[0]} - {format % args}")

    def response(self, status, content_type, body, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if extra_headers is not None:
            for header in extra_headers.split("\n"):
                if header:
                    self.send_header(*header.split(": ", 1))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_https_server():
    server = ThreadingHTTPServer((HOST, PORT), HTTPSRequestHandler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        certfile=CERT_DIR / "server.crt",
        keyfile=CERT_DIR / "server.key",
    )

    server.socket = context.wrap_socket(
        server.socket,
        server_side=True,
    )

    print(f"HTTPS server listening on TCP port {PORT}")

    try:
        server.serve_forever()
    finally:
        server.server_close()


# ---------------------------------------------------------------------
# HTTP/3 server: QUIC UDP 4433
# ---------------------------------------------------------------------


class HTTP3ServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = H3Connection(self._quic)
        self.request_events = {}
        self.request_bodies = {}

    def quic_event_received(self, event):
        for http_event in self.http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                stream_id = http_event.stream_id

                self.request_events[stream_id] = http_event
                self.request_bodies[stream_id] = bytearray()

                if http_event.stream_ended:
                    self.handle_request(http_event, b"")
                    self.request_events.pop(stream_id, None)
                    self.request_bodies.pop(stream_id, None)

            elif isinstance(http_event, DataReceived):
                stream_id = http_event.stream_id

                body = self.request_bodies.setdefault(
                    stream_id,
                    bytearray(),
                )
                body.extend(http_event.data)

                if http_event.stream_ended:
                    request_event = self.request_events.pop(stream_id, None)
                    request_body = bytes(self.request_bodies.pop(stream_id, body))

                    if request_event is not None:
                        self.handle_request(request_event, request_body)

    def handle_request(self, event, body):
        headers = dict(event.headers)

        method = headers.get(b":method", b"")
        if method == b"GET":
            self.do_GET(event, headers, body)

        elif method == b"POST":
            self.do_POST(event, headers, body)

    def do_GET(self, event, headers, body):
        path = headers.get(b":path", b"")

        if path == b"/":
            self.response(event, b"200", b"text/plain", b"Hello, HTTP/3!")

        elif path == b"/proto":
            self.response(event, b"200", b"text/plain", b"HTTP/3")

        else:
            self.response(event, b"404", b"text/plain", b"Not found")

        return

    def do_POST(self, event, headers, body):
        path = headers.get(b":path", b"")

        if path == b"/hash":
            response_body = hashlib.sha256(body).hexdigest().encode()
            self.response(event, b"200", b"text/plain", response_body)

        else:
            self.response(event, b"404", b"text/plain", b"Not found")

        return

    def response(self, event, status, content_type, body):
        self.log_message(event, status.decode())
        self.http.send_headers(
            stream_id=event.stream_id,
            headers=[(b":status", status), (b"content-type", content_type), (b"content-length", str(len(body)).encode())],
        )

        self.http.send_data(stream_id=event.stream_id, data=body, end_stream=True)

        self.transmit()

    def log_message(self, event, status):

        headers = dict(event.headers)
        method = headers.get(b":method", b"-").decode("utf-8", errors="replace")
        path = headers.get(b":path", b"-").decode("utf-8", errors="replace")

        client_ip = "-"
        if self._quic._network_paths:
            address = self._quic._network_paths[0].addr
            client_ip = address[0]

        print(f'HTTP3 {client_ip} - "{method} {path} HTTP/3" {status} -', flush=True)


async def run_http3_server():
    configuration = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)

    configuration.load_cert_chain(certfile=str(CERT_DIR / "server.crt"), keyfile=str(CERT_DIR / "server.key"))

    http3_server = await serve(HOST, PORT, configuration=configuration, create_protocol=HTTP3ServerProtocol)

    print(f"HTTP/3 server listening on UDP port {PORT}")

    try:
        await asyncio.Future()
    finally:
        http3_server.close()


# ---------------------------------------------------------------------
# Start both servers
# ---------------------------------------------------------------------


async def main():
    https_thread = threading.Thread(target=run_https_server, daemon=True)
    https_thread.start()
    await run_http3_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping servers.")
