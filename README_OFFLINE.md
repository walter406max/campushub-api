# CampusHub Offline Development Platform

This adds an offline layer **around** your existing code. Your files
(`main.py`, `ui.py`, `ai_handler.py`, `database.py`, `models.py`, `schemas.py`,
`security.py`) are not modified. Every route, screen and rule behaves the same.

## What is added

| File | Purpose |
|---|---|
| `offline_ai.py` | Wraps `ask_study_assistant` so AI runs on a local Ollama model |
| `offline_main.py` | Backend entry point: `uvicorn offline_main:app` (imports your `main.py`) |
| `run_offline.py` | Starts backend + Streamlit together, checks Ollama, stops both on Ctrl+C |
| `requirements-offline.txt` | All dependencies |
| `prepare_offline.sh` / `.bat` | Downloads packages into `wheels/` for installs with no internet |
| `.env.offline.example` | Settings template |

Copy all of these into the same folder as your existing code.

## One-time setup (needs internet once)

1. Install Python packages: `pip install -r requirements-offline.txt`
2. Install Ollama from https://ollama.com, then run: `ollama pull llama3.2`
3. Copy `.env.offline.example` to `.env` and set `SECRET_KEY`
4. Optional, for a fully offline reinstall later: run `prepare_offline.sh` (or `.bat`)

## Daily use (no internet needed)

```
python run_offline.py
```

- App: http://127.0.0.1:8501
- API docs: http://127.0.0.1:8000/docs

Or run the two parts yourself (two terminals, e.g. in PyCharm / Android Studio):

```
uvicorn offline_main:app --host 127.0.0.1 --port 8000
streamlit run ui.py
```

## Mobile app

See `mobile/README_MOBILE.md`. Start the backend for a phone with `python run_offline.py --mobile`.

## Modes

- `OFFLINE_MODE=1` (default): local SQLite database `campus_sync_offline.db` and the Ollama model only. Nothing is sent to Gemini, Groq or any remote database.
- `OFFLINE_MODE=0`: your original behaviour (Gemini, then Groq), with Ollama as a final fallback. Your `DATABASE_URL` from `.env` is respected.

## Model choice

`llama3.2` (3B) is light and runs on most laptops. For better summaries and quizzes
use a bigger model, e.g. `ollama pull llama3.1:8b` and set `OLLAMA_MODEL=llama3.1:8b`.
Quality is lower than Gemini, and first answers are slower on CPU (the app waits up to
90 seconds for file summaries; raise `AI_TIMEOUT` in `ui.py` only if you need to).

## Known limits (because your code is untouched)

- **Font:** `ui.py` loads Inter from Google Fonts. Offline the browser falls back to a system sans-serif. Everything else works.
- **Privacy Policy text** still names Gemini and Groq. Update it when you decide to ship offline-only.
- **`schemas.py` imports `ui`** (`from ui import FEEDBACK_TYPES`), which loads Streamlit inside the backend. It works, but if you ever see odd Streamlit warnings in the backend log, that is why. Moving the lists to a shared file would fix it, but I left it alone as you asked.
- The sign-in token and data live on this machine only; deleting `campus_sync_offline.db` resets all accounts.
