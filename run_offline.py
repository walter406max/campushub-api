"""
One-command launcher for the CampusHub offline development platform.

    python run_offline.py            # backend + Streamlit frontend (desktop)
    python run_offline.py --mobile   # backend only, reachable from your phone / emulator

Checks that the local Ollama model is ready and stops everything on Ctrl+C.
"""

import os
import socket
import subprocess
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OFFLINE_MODE", "1")

MOBILE = "--mobile" in sys.argv
API_HOST = os.getenv("CAMPUSHUB_HOST", "0.0.0.0" if MOBILE else "127.0.0.1")
API_PORT = os.getenv("CAMPUSHUB_API_PORT", "8000")
UI_PORT = os.getenv("CAMPUSHUB_UI_PORT", "8501")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def lan_ip() -> str:
    """Best guess of this PC's address on the local network (no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def check_ollama() -> None:
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json()
    except Exception:
        print("[warn] Ollama is not running. The app will start, but AI features will show")
        print("       a message until you start Ollama (https://ollama.com).")
        return
    names = [m.get("name", "") for m in tags.get("models", [])]
    if not any(n == OLLAMA_MODEL or n.startswith(f"{OLLAMA_MODEL}:") for n in names):
        print(f"[warn] Model '{OLLAMA_MODEL}' is not installed. Run: ollama pull {OLLAMA_MODEL}")
    else:
        print(f"[ok]   Ollama ready with model '{OLLAMA_MODEL}'.")


def main() -> None:
    print("CampusHub offline platform")
    print(f"  mode: {'OFFLINE' if os.environ['OFFLINE_MODE'] != '0' else 'HYBRID (cloud first)'}")
    check_ollama()

    shown_host = lan_ip() if API_HOST == "0.0.0.0" else API_HOST
    env = os.environ.copy()
    env["CAMPUSHUB_API_URL"] = f"http://{'127.0.0.1' if API_HOST == '0.0.0.0' else API_HOST}:{API_PORT}"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"  # no telemetry calls

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "offline_main:app", "--host", API_HOST, "--port", API_PORT],
        env=env,
    )

    frontend = None
    if not MOBILE:
        time.sleep(2)
        frontend = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "ui.py",
             "--server.port", UI_PORT, "--server.address", "127.0.0.1",
             "--browser.gatherUsageStats", "false"],
            env=env,
        )

    print(f"\nBackend API   : http://{shown_host}:{API_PORT}/docs")
    if MOBILE:
        print(f"Mobile app    : http://{shown_host}:{API_PORT}/app/   (open in a phone browser to test)")
        print("\nIn the Android app, set the server address to:")
        print(f"  real phone on the same Wi-Fi : http://{shown_host}:{API_PORT}")
        print(f"  Android emulator             : http://10.0.2.2:{API_PORT}")
        print("If the phone cannot connect, allow Python through the Windows firewall (private networks).")
    else:
        print(f"Streamlit app : http://127.0.0.1:{UI_PORT}")
    print("Press Ctrl+C to stop.\n")

    procs = [p for p in (frontend, backend) if p is not None]
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
