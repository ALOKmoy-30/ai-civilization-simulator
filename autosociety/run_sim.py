#!/usr/bin/env python3
"""
Master launcher — boots the FastAPI backend and Streamlit frontend together.
Usage:
    python -m autosociety.run_sim

Or from project root:
    python run_sim.py
"""

import sys
import subprocess
import signal
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Prefer the venv Python if running from outside the venv
_venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
if _venv_python.exists() and "venv" not in sys.executable:
    PYTHON = str(_venv_python)
else:
    PYTHON = sys.executable

# On Windows, asyncio ProactorEventLoop raises noisy ConnectionResetError [WinError 10054]
# inside _ProactorBasePipeTransport._call_connection_lost() when clients close sockets abruptly.
if sys.platform == "win32":
    import asyncio.proactor_events as _pe
    import socket as _socket

    def _safe_call_connection_lost(self, exc):
        if self._called_connection_lost:
            return
        try:
            self._protocol.connection_lost(exc)
        finally:
            if hasattr(self, "_sock") and self._sock is not None:
                try:
                    if hasattr(self._sock, "shutdown") and self._sock.fileno() != -1:
                        self._sock.shutdown(_socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    try:
                        self._sock.close()
                    except OSError:
                        pass
                    self._sock = None
            server = self._server
            if server is not None:
                server._detach(self)
                self._server = None
            self._called_connection_lost = True

    _pe._ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost

BACKEND_PORT = 8243


def main():
    print("=" * 50)
    print("  AutoSociety — Starting servers")
    print("=" * 50)
    print()

    backend_cmd = [
        PYTHON, "-m", "uvicorn",
        "autosociety.backend.main:app",
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT),
        "--log-level", "warning",
    ]
    frontend_cmd = [
        PYTHON, "-m", "streamlit", "run",
        str(PROJECT_ROOT / "autosociety" / "frontend" / "app.py"),
        "--server.port", "8501",
        "--server.headless", "true",
    ]

    print(f"  🌐 Backend:  http://0.0.0.0:{BACKEND_PORT}")
    print(f"  🖥️  Frontend: http://0.0.0.0:8501")
    print(f"  📚 API docs: http://0.0.0.0:{BACKEND_PORT}/docs")
    print()

    backend = subprocess.Popen(
        backend_cmd, cwd=PROJECT_ROOT,
    )
    time.sleep(2)

    # Verify backend actually started
    if backend.poll() is not None:
        print("\n  ❌ Backend failed to start! Check errors above.")
        sys.exit(1)

    frontend = subprocess.Popen(
        frontend_cmd, cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,  # Streamlit is noisy; keep backend visible
    )

    def shutdown(sig, frame):
        print("\nShutting down...")
        frontend.terminate()
        backend.terminate()
        frontend.wait()
        backend.wait()
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("  Both servers running. Press Ctrl+C to stop.")
    print("=" * 50)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
