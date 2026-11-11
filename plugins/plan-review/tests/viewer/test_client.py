import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from plan_review.viewer.client import ViewerClient


def serve_body(body: bytes) -> tuple[HTTPServer, int]:
    class Answer(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def test_a_port_answering_as_another_run_counts_as_stale() -> None:
    server, port = serve_body(json.dumps({"run_id": "other", "pid": 1}).encode())
    try:
        assert ViewerClient().answers_as(port, "other")
        assert not ViewerClient().answers_as(port, "7")
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("body", [b"<h1>some other server</h1>", b"[1, 2]", b'"text"'])
def test_a_port_answering_with_something_else_counts_as_stale(body: bytes) -> None:
    server, port = serve_body(body)
    try:
        assert not ViewerClient().answers_as(port, "7")
    finally:
        server.shutdown()
        server.server_close()


def test_post_stop_does_not_raise_when_nothing_listens() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    ViewerClient().post_stop(port, "token")  # nothing listens now
