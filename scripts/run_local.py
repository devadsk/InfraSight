"""
Local Runner for InfraSight (Phase 5).
Launches FastAPI backend (uvicorn) and Streamlit frontend concurrently.
Windows-friendly process management with graceful Ctrl+C termination.

Usage:
    python scripts/run_local.py
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 8501


def main():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    print("=" * 65)
    print("      InfraSight - Evidence-First Infrastructure Assistant      ")
    print("              Meta Global AI Developer Hackathon                ")
    print("=" * 65)
    print(f"[*] Workspace Root: {root_dir}")
    print(f"[*] Starting FastAPI Backend on http://{BACKEND_HOST}:{BACKEND_PORT}...")

    # Start FastAPI backend via uvicorn (no --reload on Windows for stable subprocesses)
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
        "--log-level",
        "info",
    ]
    backend_proc = subprocess.Popen(backend_cmd)

    # Wait 2 seconds for backend to initialize
    time.sleep(2)

    print(f"[*] Starting Streamlit Frontend on http://{BACKEND_HOST}:{FRONTEND_PORT}...")
    frontend_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "frontend/app.py",
        "--server.port",
        str(FRONTEND_PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    frontend_proc = subprocess.Popen(frontend_cmd)

    print("\n" + "=" * 65)
    print(f"  🚀 Frontend Dashboard: http://localhost:{FRONTEND_PORT}")
    print(f"  🔌 REST API Docs:     http://localhost:{BACKEND_PORT}/docs")
    print(f"  ⚡ Default Mode:      Offline Replay (Zero token charges)")
    print("=" * 65)
    print("Press Ctrl+C to terminate both servers gracefully.\n")

    def handle_sigint(sig, frame):
        print("\n[*] Shutting down InfraSight services...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
            frontend_proc.wait(timeout=3)
            backend_proc.wait(timeout=3)
        except Exception:
            frontend_proc.kill()
            backend_proc.kill()
        print("[*] All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while True:
            # Monitor processes
            if backend_proc.poll() is not None:
                print(f"[!] Backend process exited unexpectedly with code {backend_proc.returncode}")
                frontend_proc.terminate()
                break
            if frontend_proc.poll() is not None:
                print(f"[!] Frontend process exited unexpectedly with code {frontend_proc.returncode}")
                backend_proc.terminate()
                break
            time.sleep(1)
    except KeyboardInterrupt:
        handle_sigint(None, None)


if __name__ == "__main__":
    main()
