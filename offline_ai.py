"""
Offline AI layer for CampusHub.

Adds a local Ollama model WITHOUT editing ai_handler.py. offline_main.py calls
install_offline_ai() before main.py is imported, so main.py picks up the wrapped
ask_study_assistant() automatically.

Environment variables (all optional):
    OFFLINE_MODE     "1" (default) = use only the local model, never touch the internet
                     "0"           = try Gemini/Groq first, fall back to the local model
    OLLAMA_URL       default http://localhost:11434
    OLLAMA_MODEL     default llama3.2
    OLLAMA_NUM_CTX   default 8192 (context window; summaries of long notes need this)
    OLLAMA_TIMEOUT   default 180 seconds
"""

import os

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))


def offline_mode() -> bool:
    return os.getenv("OFFLINE_MODE", "1").strip() != "0"


def call_ollama(prompt: str) -> str:
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": OLLAMA_NUM_CTX},
        },
        timeout=OLLAMA_TIMEOUT,
    )
    response.raise_for_status()
    text = (response.json().get("response") or "").strip()
    if not text:
        raise ValueError("The local model returned an empty response.")
    return text


def install_offline_ai() -> None:
    """Wrap ai_handler.ask_study_assistant. Must run before `import main`."""
    import ai_handler

    if getattr(ai_handler, "_offline_installed", False):
        return

    original = ai_handler.ask_study_assistant

    def ask_study_assistant(prompt: str, preference: str = "gemini") -> dict:
        # Online-allowed mode: try the cloud providers first.
        if not offline_mode():
            result = original(prompt, preference=preference)
            if result.get("provider") != "Error":
                return result

        try:
            return {"provider": "Ollama", "response": call_ollama(prompt)}
        except requests.ConnectionError:
            message = (
                "The local AI model is not running. Start Ollama, then run: "
                f"ollama pull {OLLAMA_MODEL}"
            )
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                message = f"The local model is not installed. Run: ollama pull {OLLAMA_MODEL}"
            else:
                message = "The local AI model returned an error."
        except Exception as error:
            print(f"Ollama request failed: {error}")
            message = "The local AI model could not answer. Please try again."

        return {"provider": "Error", "response": message}

    ai_handler.ask_study_assistant = ask_study_assistant
    ai_handler._offline_installed = True
