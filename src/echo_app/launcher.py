from __future__ import annotations

import os
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from .app import create_app
from .config import DEFAULT_HOST, find_free_port


def _serve() -> None:
    app = create_app()
    settings = app.state.settings
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def _wait_until_ready(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=0.5) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.2)
    return False


def main() -> None:
    host = DEFAULT_HOST
    port = find_free_port(host)
    os.environ["ECHO_HOST"] = host
    os.environ["ECHO_PORT"] = str(port)

    server_thread = threading.Thread(target=_serve, daemon=True)
    server_thread.start()

    base_url = f"http://{host}:{port}"
    if not _wait_until_ready(base_url):
        raise SystemExit("Echo backend failed to start.")

    webbrowser.open(base_url)

    try:
        while server_thread.is_alive():
            server_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
