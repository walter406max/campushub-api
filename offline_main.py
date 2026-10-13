"""
Offline entry point for the CampusHub backend.

Run instead of `main:app`:
    uvicorn offline_main:app --host 127.0.0.1 --port 8000

It sets offline-friendly defaults, patches the AI layer to use a local Ollama
model, then imports your unchanged main.py. If the mobile/www folder is next to
this file, the mobile app is also served at http://<host>:8000/app/ for testing
in a phone or desktop browser.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # first, so values in .env win over the defaults below

# Defaults only: anything you set in the shell or .env wins, except the database
# which is pinned to local SQLite while OFFLINE_MODE=1 so nothing reaches a remote server.
os.environ.setdefault("OFFLINE_MODE", "1")
os.environ.setdefault(
    "CORS_ORIGINS",
    # Streamlit, the Capacitor Android app (served as http://localhost), and local dev servers
    "http://localhost:8501,http://127.0.0.1:8501,http://localhost,https://localhost,"
    "capacitor://localhost,http://localhost:5173,http://127.0.0.1:5173",
)

if os.environ["OFFLINE_MODE"].strip() != "0":
    os.environ["DATABASE_URL"] = os.getenv(
        "OFFLINE_DATABASE_URL", "sqlite:///./campus_sync_offline.db"
    )

from offline_ai import install_offline_ai  # noqa: E402

install_offline_ai()  # must run BEFORE main is imported

from main import app  # noqa: E402,F401

# Serve the mobile web app from the backend (same origin, no CORS needed).
_www = Path(__file__).resolve().parent / "mobile" / "www"
if _www.is_dir():
    from fastapi.staticfiles import StaticFiles  # noqa: E402

    app.mount("/app", StaticFiles(directory=str(_www), html=True), name="mobile")
