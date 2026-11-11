"""Talking to a running detached viewer."""

import json
import urllib.request
from contextlib import suppress

TOKEN_HEADER = "x-plan-review-token"


class ViewerClient:
    def answers_as(self, port: int, run_id: str) -> bool:
        """Is it this run's viewer that answers on `port`?"""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/viewer", timeout=2) as reply:
                return json.load(reply).get("run_id") == run_id
        except OSError, ValueError, AttributeError:
            return False

    def post_stop(self, port: int, token: str) -> None:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/stop", method="POST", headers={TOKEN_HEADER: token}
        )
        with suppress(OSError):
            urllib.request.urlopen(request, timeout=5).close()
