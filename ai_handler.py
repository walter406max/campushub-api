import os
from io import BytesIO

from dotenv import load_dotenv
from google import genai
from groq import Groq
from pypdf import PdfReader

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")  # override in .env if this model name is wrong
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_DOCUMENT_CHARS = 30000  # keeps requests inside free-tier limits

gemini_client = None
groq_client = None

try:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        gemini_client = genai.Client(api_key=gemini_key)

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        groq_client = Groq(api_key=groq_key)
except Exception as e:
    print(f"Configuration warning: failed to initialise AI clients: {e}")


# ---------- Provider calls ----------
def _call_gemini(prompt: str) -> str:
    response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    if not response.text:
        raise ValueError("Gemini returned an empty response.")
    return response.text


def _call_groq(prompt: str) -> str:
    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=GROQ_MODEL,
    )
    text = completion.choices[0].message.content  # was: choices.message (crash)
    if not text:
        raise ValueError("Groq returned an empty response.")
    return text


def ask_study_assistant(prompt: str, preference: str = "gemini") -> dict:
    """Try the preferred provider first and fail over to the other one."""
    order = ("groq", "gemini") if preference.lower() == "groq" else ("gemini", "groq")
    notice = ""

    for name in order:
        client = gemini_client if name == "gemini" else groq_client
        if client is None:
            notice = f"{name.title()} is not configured, so a fallback provider was used."
            continue
        try:
            text = _call_gemini(prompt) if name == "gemini" else _call_groq(prompt)
            if notice:
                text = f"*{notice}*\n\n{text}"
            return {"provider": name.title(), "response": text}
        except Exception as error:
            print(f"{name} request failed: {error}")  # log server-side only
            notice = f"{name.title()} was unavailable, so a fallback provider was used."

    return {
        "provider": "Error",
        "response": "The AI service is unavailable right now. Please try again shortly.",
    }


# ---------- File reading ----------
def extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8", errors="ignore")


# ---------- Prompt builders ----------
def build_summary_prompt(text: str) -> str:
    return (
        "You are a study assistant for university students. Summarise the lecture notes "
        "below using clear headings and concise bullet points, then list the key terms "
        "with one-line definitions. Use only the content provided.\n\nNOTES:\n"
        + text[:MAX_DOCUMENT_CHARS]
    )


def build_quiz_prompt(text: str) -> str:
    return (
        "You are a study assistant for university students. Create a 5-question "
        "multiple-choice quiz (options A to D) from the lecture notes below. Put an "
        "answer key with short explanations at the end. Use only the content provided."
        "\n\nNOTES:\n" + text[:MAX_DOCUMENT_CHARS]
    )


def build_question_prompt(module_code: str, question: str) -> str:
    return (
        f"You are an academic tutor for the university module {module_code}. Answer the "
        f"student's question clearly and accurately, with a short example where useful. "
        f"If you are unsure, say so.\n\nQUESTION:\n{question}"
    )