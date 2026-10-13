"""
CampusHub
Streamlit frontend. Requires streamlit>=1.37 and the FastAPI backend (main.py).
"""

import html
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONSTANTS
# ============================================================

API_URL = os.environ.get("CAMPUSHUB_API_URL", "http://localhost:8000").rstrip("/")
# Address the browser uses to reach the backend (the Google button links to it)
PUBLIC_API_URL = os.environ.get("CAMPUSHUB_PUBLIC_API_URL", API_URL).rstrip("/")
GOOGLE_LOGIN_URL = f"{PUBLIC_API_URL}/auth/google/login"
UNSET_UNIVERSITY = "Not set"
REQUEST_TIMEOUT = 15
AI_TIMEOUT = 90  # file summaries and quizzes can take a while

APP_DIR = Path(__file__).resolve().parent
FAVICON_FILE = APP_DIR / "favicon.jpg"

UNIVERSITIES = [
    "Midlands State University",
    "University of Zimbabwe",
    "National University of Science and Technology",
    "Harare Institute of Technology",
    "Great Zimbabwe University",
]

# Keep these lists identical to schemas.py in the backend
EXPENSE_CATEGORIES = ["Food", "Transport", "Data", "Printing", "Accommodation", "Other"]
WEEKS = ["Week 1", "Week 2", "Week 3", "Week 4"]
FEEDBACK_TYPES = ["Bug report", "Suggestion", "Compliment", "Other"]

NAV_PAGES = [
    "Dashboard",
    "Study Hub",
    "Budget Assistance",
    "Marketplace",
    "Events",
    "Settings",
]

SUPPORT_EMAIL = "support@campushub.example"  # replace with your real contact address
LEGAL_UPDATED = "30 September 2026"


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="CampusHub ",
    page_icon=str(FAVICON_FILE) if FAVICON_FILE.exists() else None,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# LEGAL TEXT  (templates: have them reviewed before public launch)
# ============================================================

PRIVACY_POLICY = f"""
**Last updated: {LEGAL_UPDATED}**

CampusHub is a student platform that combines study tools, a budget assistant,
a student marketplace and a campus events board. This policy explains what
information the app handles and why.

**1. Information we collect**
- **Account details:** your name, university email address, university and
  password. Your password is stored only as a salted hash, never in readable form.
- **Google sign-in:** if you choose it, Google shares your name and verified
  email address with us. We never receive your Google password.
- **Budget data:** the income figure you save and the expenses you log.
- **Marketplace listings:** item names, prices and the contact details you
  choose to publish.
- **Study content:** notes you upload and questions you ask the AI study partner.
- **Feedback:** messages you send from the Settings page.

**2. How we use your information**
- To create your account and keep you signed in.
- To provide the Study Hub, Budget Assistance, Marketplace and Events features.
- To improve the app using the feedback you send.

**3. AI processing**
When you summarise notes, generate a quiz or ask a question, the text is sent
to third-party AI providers (currently Google Gemini and Groq) to produce a
response. CampusHub does not keep a copy of uploaded files or AI responses.
The providers handle data under their own policies, so please do not upload
private or confidential material.

**4. Who can see your information**
- Marketplace listings, including the contact details you enter and your name
  as seller, are visible to other signed-in students.
- Your income, expenses and feedback are private to your account.
- We do not sell your personal information.

**5. Security**
Passwords are hashed and sessions use signed tokens that expire. No system is
completely secure, so please use a strong, unique password.

**6. Retention and deletion**
Your information is kept until you delete your account. You can do this at any
time under **Settings > Account**, which permanently removes your profile,
expenses, marketplace listings and feedback.

**7. Your rights**
You may ask to see, correct or delete the information we hold about you.
Contact us at {SUPPORT_EMAIL}.

**8. Changes**
We may update this policy. The date above shows when it last changed.
"""

USER_AGREEMENT = f"""
**Last updated: {LEGAL_UPDATED}**

By creating an account or using CampusHub you agree to these terms.

**1. Eligibility and accounts**
CampusHub is intended for university students. You are responsible for the
accuracy of your details and for keeping your password secure. Do not share
your account.

**2. Acceptable use**
You agree not to:
- post illegal, stolen, counterfeit or dangerous items in the Marketplace;
- harass, deceive or threaten other users;
- attempt to break, overload or gain unauthorised access to the service;
- upload material you do not have the right to share.

**3. Marketplace**
CampusHub only lets students list and find items. We are not a party to any
sale and do not inspect, guarantee or insure items. Meet in safe, public campus
locations and check items before paying.

**4. AI study tools**
AI output can be inaccurate or incomplete. Verify important information with
your lecturers and course materials. Follow your university's academic
integrity rules when using AI assistance for coursework.

**5. Budget Assistance**
The budget tools are for personal tracking only and are not financial advice.

**6. Your content**
You keep ownership of what you post. You give CampusHub permission to store and
display it as needed to run the service, for example showing your listing to
other students.

**7. Suspension and deletion**
We may suspend accounts that break these terms. You can delete your account at
any time under **Settings > Account**.

**8. Service and liability**
The service is provided "as is", without guarantees of uninterrupted operation.
To the extent the law allows, CampusHub is not liable for losses arising from
use of the service or from dealings between users.

**9. Changes and contact**
We may update these terms, and continued use means you accept the changes.
Questions: {SUPPORT_EMAIL}.
"""


# ============================================================
# API LAYER  (the only place that talks to the backend)
# ============================================================

class ApiError(Exception):
    """Raised when the backend cannot be reached or returns an error."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _error_message(response):
    """Extract a readable message from an error response."""
    try:
        body = response.json()
    except ValueError:
        return f"Request failed ({response.status_code})."

    if isinstance(body, dict):
        detail = body.get("detail") or body.get("message") or body.get("error")
        if isinstance(detail, str):
            return detail
        # FastAPI validation errors arrive as a list of dicts
        if isinstance(detail, list) and detail and isinstance(detail[0], dict):
            field = ".".join(str(part) for part in detail[0].get("loc", [])[1:])
            message = detail[0].get("msg", "Invalid input.")
            return f"{field}: {message}" if field else message
        if detail:
            return str(detail)
    return f"Request failed ({response.status_code})."


def api_request(method, path, *, json=None, files=None, auth=True, timeout=REQUEST_TIMEOUT):
    headers = {}
    token = st.session_state.get("auth_token")
    if auth and token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method,
            f"{API_URL}{path}",
            json=json,
            files=files,
            headers=headers,
            timeout=timeout,
        )
    except requests.Timeout:
        raise ApiError("The server took too long to respond. Please try again.") from None
    except requests.RequestException:
        raise ApiError("Cannot reach the server. Check that the backend is running.") from None

    if not response.ok:
        raise ApiError(_error_message(response), response.status_code)

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def api_register(name, email, university, password):
    return api_request(
        "POST",
        "/auth/register",
        json={"name": name, "email": email, "university": university, "password": password},
        auth=False,
    )


def api_login(email, password):
    data = api_request(
        "POST", "/auth/login", json={"email": email, "password": password}, auth=False
    )
    token = data.get("access_token") or data.get("token")
    if not token:
        raise ApiError("The server did not return a login token.")

    user = data.get("user")
    if not user:
        st.session_state.auth_token = token
        user = api_request("GET", "/auth/me")

    return token, user


def api_get_income():
    data = api_request("GET", "/income")
    return float(data.get("income", 0) or 0)


def api_set_income(amount):
    api_request("PUT", "/income", json={"income": float(amount)})


def api_get_expenses():
    rows = api_request("GET", "/expenses")
    if isinstance(rows, dict):
        rows = rows.get("items", [])
    records = []
    for row in rows:
        records.append(
            {
                "Week": row.get("week") or row.get("Week"),
                "Category": row.get("category") or row.get("Category"),
                "Amount": float(row.get("amount") or row.get("Amount") or 0),
            }
        )
    return pd.DataFrame(records, columns=["Week", "Category", "Amount"])


def api_add_expense(week, category, amount):
    api_request(
        "POST",
        "/expenses",
        json={"week": week, "category": category, "amount": float(amount)},
    )


def api_get_listings():
    rows = api_request("GET", "/marketplace")
    if isinstance(rows, dict):
        rows = rows.get("items", [])
    return rows


def api_add_listing(title, price, contact):
    api_request(
        "POST",
        "/marketplace",
        json={"title": title, "price": float(price), "contact": contact},
    )


def api_get_events():
    rows = api_request("GET", "/events")
    if isinstance(rows, dict):
        rows = rows.get("items", [])
    return rows


def api_ai_process_file(action, uploaded_file):
    path = "/ai/summarize" if action == "Summarize Notes" else "/ai/quiz"
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    data = api_request("POST", path, files=files, timeout=AI_TIMEOUT)
    return data.get("result", "")


def api_ai_ask(module_code, question):
    data = api_request(
        "POST",
        "/ai/ask",
        json={"module_code": module_code, "question": question},
        timeout=AI_TIMEOUT,
    )
    return data.get("result", "")


def api_send_feedback(category, message):
    api_request("POST", "/feedback", json={"category": category, "message": message})


def api_google_exchange(code):
    data = api_request("POST", "/auth/google/exchange", json={"code": code}, auth=False)
    token = data.get("access_token")
    user = data.get("user")
    if not token or not user:
        raise ApiError("The server did not return a login token.")
    return token, user


def api_update_university(university):
    return api_request("PATCH", "/auth/me", json={"university": university})


def api_delete_account(confirmation, has_password=True):
    body = {"password": confirmation} if has_password else {"confirm_text": confirmation}
    api_request("POST", "/account/delete", json=body)


# ============================================================
# ERROR HANDLING HELPERS
# ============================================================

def sign_out():
    # The theme and any flash message are deliberately kept across sign-out.
    for key in (
        "logged_in",
        "auth_token",
        "user_name",
        "user_email",
        "user_university",
        "timer_end",
        "timer_total",
        "timer_done",
        "nav_page",
        "user_has_password",
    ):
        st.session_state.pop(key, None)


def show_api_error(error):
    """Show an API error. An expired session returns the user to the login screen."""
    if getattr(error, "status_code", None) == 401 and st.session_state.get("logged_in"):
        sign_out()
        st.rerun()
    st.error(str(error))


def fetch(function, default, *args):
    """Call an API function; on failure show the error and return the default."""
    try:
        return function(*args)
    except ApiError as error:
        show_api_error(error)
        return default


# ============================================================
# THEME
# ============================================================

THEMES = {
    "light": {
        "bg": "#f5f8fc",
        "surface": "#ffffff",
        "surface-alt": "#e6edf6",
        "text": "#0f172a",
        "muted": "#475569",
        "border": "#e2e8f0",
        "input-bg": "#ffffff",
        "badge-bg": "#eff6ff",
        "badge-text": "#1e40af",
        "glow-a": "rgba(14,165,233,0.07)",
        "glow-b": "rgba(37,99,235,0.06)",
        "card-shadow": "rgba(15,23,42,0.04)",
        "card-shadow-hover": "rgba(15,23,42,0.10)",
        "sidebar-a": "#0f172a",
        "sidebar-b": "#172554",
    },
    "dark": {
        "bg": "#0b1220",
        "surface": "#131c2e",
        "surface-alt": "#1b2740",
        "text": "#e5edf8",
        "muted": "#9fb0c8",
        "border": "#243149",
        "input-bg": "#0f1829",
        "badge-bg": "#1b2a4a",
        "badge-text": "#93c5fd",
        "glow-a": "rgba(14,165,233,0.10)",
        "glow-b": "rgba(37,99,235,0.10)",
        "card-shadow": "rgba(0,0,0,0.35)",
        "card-shadow-hover": "rgba(0,0,0,0.55)",
        "sidebar-a": "#060b16",
        "sidebar-b": "#0f1a3a",
    },
}


def theme_css(theme):
    values = THEMES.get(theme, THEMES["light"])
    variables = "\n".join(f"--{name}: {value};" for name, value in values.items())
    scheme = "dark" if theme == "dark" else "light"
    return f"<style>:root {{ {variables} color-scheme: {scheme}; }}</style>"


BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, .stApp, .stMarkdown, p, label,
.stTextInput input, .stTextArea textarea, .stNumberInput input,
.stButton button, .stFormSubmitButton button, .stTabs button {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at top left, var(--glow-a), transparent 32%),
        radial-gradient(circle at bottom right, var(--glow-b), transparent 32%),
        var(--bg);
    color: var(--text);
}

/* Hide Streamlit chrome, but keep the header so the sidebar toggle stays visible */
#MainMenu, footer,
[data-testid="stDecoration"],
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],
.stAppDeployButton {
    display: none !important;
    visibility: hidden;
}
header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1240px;
    padding-top: 3.5rem;
    padding-bottom: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
}

/* Text colours (theme aware) */
.stApp p, .stApp label, .stApp li,
.stApp [data-testid="stMarkdownContainer"] {
    color: var(--text);
}
h1, h2, h3, h4, h5, h6 {
    color: var(--text);
    font-weight: 800;
    letter-spacing: -0.3px;
}
h1 { font-size: 2rem !important; margin-bottom: 0.25rem; }
h2 { font-size: 1.5rem !important; }
h3 { font-size: 1.15rem !important; }
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] * {
    color: var(--muted);
}

/* ---------------- Sidebar (curved, collapsible, mobile friendly) ---------------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--sidebar-a) 0%, var(--sidebar-b) 100%);
    border-right: 1px solid rgba(255,255,255,0.08);
    border-radius: 0 28px 28px 0;
    overflow: hidden;
    box-shadow: 8px 0 30px rgba(15,23,42,0.20);
}
/* Fixed width only while open, so collapsing still slides the sidebar away cleanly */
section[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 260px;
    max-width: 260px;
}
section[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
section[data-testid="stSidebar"] .stRadio label {
    padding: 9px 12px;
    border-radius: 12px;
    width: 100%;
    transition: background 0.2s ease;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.10);
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
    background: rgba(255,255,255,0.18);
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.18);
    box-shadow: none;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.16);
    transform: none;
}

/* Close (inside the sidebar) and open (when collapsed) controls: always visible */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] button {
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stExpandSidebarButton"] {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 14px;
    box-shadow: 0 6px 18px var(--card-shadow-hover);
    margin: 8px;
    z-index: 1000;
}

@media (max-width: 900px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 4rem;
    }
    section[data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 0;
        max-width: min(84vw, 300px);
        width: min(84vw, 300px) !important;
    }
}

/* ---------------- Buttons ---------------- */
.stButton > button,
.stFormSubmitButton > button {
    width: 100%;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, #0284c7, #2563eb);
    color: #ffffff;
    font-weight: 600;
    padding: 0.6rem 1rem;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover {
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(37,99,235,0.25);
}
.stButton > button p,
.stFormSubmitButton > button p {
    color: #ffffff;
}

/* ---------------- Inputs (theme aware) ---------------- */
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="textarea"],
div[data-baseweb="select"] > div {
    background: var(--input-bg) !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
    background: transparent !important;
    color: var(--text) !important;
    border-radius: 10px !important;
}
div[data-baseweb="select"] * {
    color: var(--text) !important;
}
div[data-baseweb="popover"] > div,
ul[role="listbox"],
li[role="option"] {
    background: var(--surface) !important;
    color: var(--text) !important;
}
li[role="option"]:hover {
    background: var(--surface-alt) !important;
}
.stNumberInput button {
    background: var(--input-bg);
    color: var(--text);
    border-color: var(--border);
}
[data-testid="stFileUploaderDropzone"] {
    background: var(--input-bg);
    border: 1px dashed var(--border);
    border-radius: 12px;
}
[data-testid="stFileUploaderDropzoneInstructions"] *,
[data-testid="stFileUploaderFile"] * {
    color: var(--text);
}
[data-testid="stFileUploaderDropzone"] button {
    background: var(--surface-alt);
    color: var(--text);
    border: 1px solid var(--border);
}
[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary * {
    color: var(--text);
}

/* ---------------- Tabs ---------------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: var(--surface-alt);
    padding: 5px;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px;
    padding: 8px 18px;
    height: auto;
}
.stTabs [aria-selected="true"] {
    background: var(--surface) !important;
    box-shadow: 0 3px 10px var(--card-shadow);
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none;
}

/* ---------------- Metrics and containers ---------------- */
[data-testid="stMetric"] {
    background: var(--surface);
    padding: 16px 18px;
    border-radius: 14px;
    border: 1px solid var(--border);
    box-shadow: 0 4px 14px var(--card-shadow);
}
[data-testid="stMetricValue"],
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
    color: var(--text);
}
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface);
    border-radius: 16px;
}

/* ---------------- Cards ---------------- */
.info-card, .event-card, .market-card {
    background: var(--surface);
    padding: 20px 22px;
    border-radius: 16px;
    border: 1px solid var(--border);
    box-shadow: 0 4px 14px var(--card-shadow);
    margin-bottom: 14px;
    transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}
.info-card:hover, .event-card:hover, .market-card:hover {
    box-shadow: 0 10px 26px var(--card-shadow-hover);
}
.info-card h3, .event-card h3, .market-card h3 {
    margin: 0 0 6px 0;
}
.info-card p, .event-card p, .market-card p {
    margin: 0 0 4px 0;
    color: var(--muted);
    line-height: 1.55;
}
.date-badge {
    text-align: right;
    padding: 12px 18px;
    border-radius: 12px;
    background: var(--badge-bg);
    white-space: nowrap;
}
.date-badge small {
    color: var(--muted);
    font-weight: 600;
}
.date-badge h3 {
    margin: 2px 0 0 0;
    color: var(--badge-text);
}

/* Clickable dashboard cards: the button is stretched invisibly over the card */
.nav-card {
    min-height: 150px;
    cursor: pointer;
}
.card-cta {
    display: inline-block;
    margin-top: 10px;
    font-weight: 600;
    color: var(--badge-text);
}
[class*="st-key-card_"] {
    position: relative;
    gap: 0;
}
[class*="st-key-card_"] .stButton {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    z-index: 2;
}
[class*="st-key-card_"] .stButton > button {
    width: 100%;
    height: 100%;
    min-height: 0;
    padding: 0;
    opacity: 0;
    cursor: pointer;
}
[class*="st-key-card_"]:hover .nav-card {
    transform: translateY(-4px);
    border-color: #2563eb;
    box-shadow: 0 14px 30px var(--card-shadow-hover);
}
[class*="st-key-card_"]:focus-within .nav-card {
    outline: 2px solid #2563eb;
}

/* Budget bars and table (plain HTML so they follow the theme) */
.bar-row {
    display: grid;
    grid-template-columns: 70px 1fr 96px;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
}
.bar-label, .bar-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
}
.bar-value { text-align: right; }
.bar-track {
    background: var(--surface-alt);
    border-radius: 999px;
    height: 12px;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #0284c7, #2563eb);
}
.table-wrap {
    max-height: 320px;
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
}
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
}
.data-table th {
    position: sticky;
    top: 0;
    background: var(--surface-alt);
    color: var(--text);
    text-align: left;
    padding: 10px 14px;
}
.data-table td {
    color: var(--text);
    padding: 9px 14px;
    border-top: 1px solid var(--border);
}

/* Danger zone (delete account) */
.st-key-danger_zone .stFormSubmitButton > button {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
}
.st-key-danger_zone .stFormSubmitButton > button:hover {
    box-shadow: 0 8px 20px rgba(220,38,38,0.30);
}

/* ---------------- Login layout ---------------- */
.st-key-brand_panel {
    background: linear-gradient(145deg, #0284c7 0%, #1e40af 100%);
    border-radius: 22px;
    padding: 44px 38px;
    min-height: 560px;
    box-shadow: 0 20px 50px rgba(15,23,42,0.16);
}
.st-key-brand_panel * {
    color: #ffffff !important;
}
.st-key-brand_panel h1 {
    font-size: 2.6rem !important;
    margin-bottom: 10px;
}
.st-key-brand_panel p {
    color: rgba(255,255,255,0.90) !important;
    line-height: 1.65;
    margin-bottom: 14px;
}
.brand-mark {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    background: rgba(255,255,255,0.16);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1.3rem;
    letter-spacing: 1px;
    margin-bottom: 22px;
}
.brand-feature {
    border-left: 3px solid rgba(255,255,255,0.45);
    padding-left: 14px;
    margin-bottom: 14px;
}
.brand-feature b {
    font-size: 1rem;
}
.brand-feature span {
    display: block;
    opacity: 0.88;
    font-size: 0.92rem;
}
.st-key-login_panel {
    background: var(--surface);
    border-radius: 22px;
    padding: 34px 38px;
    min-height: 560px;
    border: 1px solid var(--border);
    box-shadow: 0 20px 50px var(--card-shadow-hover);
}

@media (max-width: 900px) {
    .st-key-brand_panel, .st-key-login_panel {
        min-height: auto;
        padding: 26px 22px;
    }
}

/* ---------------- Loading screen ---------------- */
.loader-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: var(--bg);
}
.loader-ring {
    width: 58px;
    height: 58px;
    border-radius: 50%;
    border: 5px solid rgba(37,99,235,0.18);
    border-top-color: #2563eb;
    animation: campushub-spin 0.9s linear infinite;
}
.loader-overlay p {
    margin-top: 20px;
    font-weight: 600;
    color: var(--muted);
}
@keyframes campushub-spin {
    to { transform: rotate(360deg); }
}
</style>
"""

HIDE_SIDEBAR_CSS = """
<style>
section[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"] {
    display: none !important;
}
</style>
"""


# ============================================================
# HELPERS
# ============================================================

def valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def esc(value):
    """Escape text from the backend before placing it inside HTML."""
    return html.escape(str(value), quote=True)


def initialize_session():
    defaults = {
        "logged_in": False,
        "auth_token": "",
        "user_name": "",
        "user_email": "",
        "user_university": "",
        "timer_end": None,
        "timer_total": 0,
        "timer_done": False,
        "theme": "light",
        "user_has_password": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def info_card(title, body):
    return f"""
        <div class="info-card">
            <h3>{esc(title)}</h3>
            <p>{esc(body)}</p>
        </div>
    """


def loading_html(message):
    return (
        '<div class="loader-overlay">'
        '<div class="loader-ring"></div>'
        f"<p>{esc(message)}</p>"
        "</div>"
    )


def go_to(page):
    """Button callback: switch the sidebar navigation to another page."""
    st.session_state.nav_page = page


# ============================================================
# GOOGLE SIGN-IN
# ============================================================

GOOGLE_CSS = """
<style>
.google-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 100%;
    box-sizing: border-box;
    padding: 0.6rem 1rem;
    border-radius: 10px;
    border: 1px solid #dadce0;
    background: #ffffff;
    color: #3c4043 !important;
    font-weight: 600;
    text-decoration: none !important;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.google-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(15,23,42,0.18);
}
.google-btn svg { width: 20px; height: 20px; flex-shrink: 0; }
.or-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 18px 0 6px 0;
    color: var(--muted);
    font-size: 0.85rem;
}
.or-divider::before, .or-divider::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border);
}
</style>
"""

GOOGLE_G_SVG = (
    '<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
    '<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>'
    '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>'
    '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>'
    '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>'
    "</svg>"
)


def google_button(label):
    """'Continue with Google' button followed by an 'or' divider."""
    st.markdown(
        f'<a class="google-btn" href="{esc(GOOGLE_LOGIN_URL)}" target="_self">'
        f"{GOOGLE_G_SVG}<span>{esc(label)}</span></a>"
        '<div class="or-divider"><span>or use your email</span></div>',
        unsafe_allow_html=True,
    )


def handle_google_callback():
    """Finish a Google sign-in when the backend redirects back with ?google_code= or ?google_error=."""
    code = st.query_params.get("google_code")
    error = st.query_params.get("google_error")
    if not code and not error:
        return

    # Clear first so a page refresh cannot replay the one-time code
    st.query_params.clear()

    if error:
        st.session_state.flash_error = error
        return

    loader = st.empty()
    loader.markdown(loading_html("Signing you in with Google..."), unsafe_allow_html=True)
    try:
        token, user = api_google_exchange(code)
    except ApiError as err:
        loader.empty()
        st.session_state.flash_error = str(err)
        return

    st.session_state.logged_in = True
    st.session_state.auth_token = token
    st.session_state.user_name = user.get("name", "")
    st.session_state.user_email = user.get("email", "")
    st.session_state.user_university = user.get("university", "")
    st.session_state.user_has_password = user.get("has_password", False)

    loader.markdown(loading_html("Preparing your dashboard..."), unsafe_allow_html=True)
    time.sleep(0.9)
    st.rerun()


def complete_profile_page():
    """New Google users choose their university before entering the app."""
    _, centre, _ = st.columns([1, 1.4, 1])
    with centre:
        with st.container(key="login_panel"):
            st.markdown("### One last step")
            st.caption("Choose your university to finish setting up your CampusHub account.")

            with st.form("complete_profile_form"):
                university = st.selectbox("University", UNIVERSITIES)
                submitted = st.form_submit_button("Continue")

            if submitted:
                try:
                    api_update_university(university)
                except ApiError as error:
                    show_api_error(error)
                    return
                st.session_state.user_university = university
                st.rerun()

            if st.button("Log Out", key="profile_logout"):
                sign_out()
                st.rerun()


# ============================================================
# AUTHENTICATION
# ============================================================

def create_account():
    st.markdown("### Create your account")
    st.caption("Register as a student to access the CampusHub platform.")

    with st.form("create_account_form", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            full_name = st.text_input("Full name", placeholder="Enter your full name")
        with col_b:
            email = st.text_input("University email", placeholder="student@example.com")

        university = st.selectbox("University", UNIVERSITIES)

        col_c, col_d = st.columns(2)
        with col_c:
            password = st.text_input(
                "Create password", type="password", placeholder="Minimum 6 characters"
            )
        with col_d:
            confirm_password = st.text_input(
                "Confirm password", type="password", placeholder="Re-enter your password"
            )

        agree_terms = st.checkbox(
            "I agree to the CampusHub User Agreement and Privacy Policy "
            "(available under Settings after you sign in)."
        )
        submitted = st.form_submit_button("Create Account")

    if not submitted:
        return

    clean_name = full_name.strip()
    clean_email = email.strip().lower()

    if not clean_name:
        st.error("Enter your full name.")
        return
    if not clean_email:
        st.error("Enter your university email.")
        return
    if not valid_email(clean_email):
        st.error("Enter a valid email address.")
        return
    if not password:
        st.error("Create a password.")
        return
    if len(password) < 6:
        st.error("The password must contain at least 6 characters.")
        return
    if password != confirm_password:
        st.error("The passwords do not match.")
        return
    if not agree_terms:
        st.error("You must agree to the terms and conditions.")
        return

    try:
        with st.spinner("Creating your account..."):
            api_register(clean_name, clean_email, university, password)
    except ApiError as error:
        st.error(str(error))
        return

    st.success("Account created successfully. Open the Login tab to sign in.")


def login_user():
    st.markdown("### Welcome back")
    st.caption("Sign in to continue to your CampusHub dashboard.")

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("University email", placeholder="student@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Login to CampusHub")

    if not submitted:
        return

    clean_email = email.strip().lower()

    if not clean_email or not password:
        st.error("Enter both your email and password.")
        return

    # Full-screen loading circle while signing in
    loader = st.empty()
    loader.markdown(loading_html("Signing you in..."), unsafe_allow_html=True)

    try:
        token, user = api_login(clean_email, password)
    except ApiError as error:
        loader.empty()
        st.session_state.auth_token = ""
        st.error(str(error))
        return

    st.session_state.logged_in = True
    st.session_state.auth_token = token
    st.session_state.user_name = user.get("name", "")
    st.session_state.user_email = user.get("email", clean_email)
    st.session_state.user_university = user.get("university", "")
    st.session_state.user_has_password = user.get("has_password", True)

    # Keep the loader on screen while the dashboard loads
    loader.markdown(loading_html("Preparing your dashboard..."), unsafe_allow_html=True)
    time.sleep(0.9)
    st.rerun()


def authentication_page():
    _, centre, _ = st.columns([0.02, 0.96, 0.02])

    with centre:
        flash = st.session_state.pop("flash", None)
        if flash:
            st.success(flash)

        flash_error = st.session_state.pop("flash_error", None)
        if flash_error:
            st.error(flash_error)

        left, right = st.columns([1.0, 1.25], gap="large")

        with left:
            with st.container(key="brand_panel"):
                st.markdown(
                    """
                    <div class="brand-mark">CH</div>
                    <h1>CampusHub</h1>
                    <p style="font-size:1.1rem;">
                        Your CampusLife.Connected
                    </p>
                    <p>
                        CampusHub brings your academic, financial and student
                        activities together in one platform.
                    </p>
                    <div class="brand-feature">
                        <b>Study</b><span>Access your study tools.</span>
                    </div>
                    <div class="brand-feature">
                        <b>Connect</b><span>Interact with other students.</span>
                    </div>
                    <div class="brand-feature">
                        <b>Manage</b><span>Manage your campus life.</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with right:
            with st.container(key="login_panel"):
                login_tab, create_tab = st.tabs(["Login", "Signup"])
                with login_tab:
                    google_button("Sign in with Google")
                    login_user()
                with create_tab:
                    google_button("Sign up with Google")
                    st.caption(
                        "By continuing with Google you agree to the CampusHub User Agreement "
                        "and Privacy Policy (available under Settings after you sign in)."
                    )
                    create_account()


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

def sidebar_navigation():
    if not st.session_state.logged_in:
        return None

    st.sidebar.markdown(
        """
        <div style="text-align:center; padding:8px 5px 18px 5px;">
            <div style="font-size:22px; font-weight:800;">CampusHub</div>
            <div style="font-size:12px; opacity:0.75; margin-top:4px;">
                Your CampusLife.Connected
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        f"""
        <div style="background:rgba(255,255,255,0.08);
                    border:1px solid rgba(255,255,255,0.12);
                    border-radius:16px; padding:14px; margin-bottom:18px;">
            <div style="font-size:15px; font-weight:700;">
                {esc(st.session_state.user_name)}
            </div>
            <div style="font-size:11px; opacity:0.75; margin-top:5px; word-break:break-word;">
                {esc(st.session_state.user_email)}
            </div>
            <div style="font-size:11px; opacity:0.75; margin-top:4px;">
                {esc(st.session_state.user_university)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### Navigation")

    page = st.sidebar.radio(
        "CampusHub Menu",
        NAV_PAGES,
        key="nav_page",
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")

    if st.sidebar.button("Log Out", key="logout_button"):
        sign_out()
        st.rerun()

    return page


# ============================================================
# DASHBOARD
# ============================================================

def nav_card(key, title, body, page):
    """A dashboard card that opens another page when clicked."""
    with st.container(key=key):
        st.markdown(
            f"""
            <div class="info-card nav-card">
                <h3>{esc(title)}</h3>
                <p>{esc(body)}</p>
                <span class="card-cta">Open {esc(title)} &rarr;</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            f"Open {title}",
            key=f"go_{key}",
            on_click=go_to,
            args=(page,),
        )


PL_PURPLE = "#5b16f5"

BOTTOM_TABS = [
    ("Home", "Dashboard"),
    ("Study", "Study Hub"),
    ("Budget", "Budget Assistance"),
    ("Market", "Marketplace"),
]

DASH_CSS = """
<style>
/* ---------------- Dashboard (app-style home screen) ---------------- */
.pl-avatar {
    width: 44px; height: 44px; border-radius: 50%;
    border: 2.5px solid #5b16f5; color: #5b16f5;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1.1rem;
}
.pl-pill {
    display: inline-block; background: #5b16f5; color: #ffffff;
    font-weight: 600; font-size: 1.05rem;
    padding: 10px 20px; border-radius: 12px;
}
.pl-top-right {
    display: flex; align-items: center; justify-content: flex-end;
    gap: 16px; color: #5b16f5; font-weight: 600; font-size: 1.05rem;
}
.pl-bell { position: relative; display: inline-flex; }
.pl-dot {
    position: absolute; top: -2px; right: -3px;
    width: 11px; height: 11px; border-radius: 50%; background: #e5392d;
}

.pl-hero {
    background: linear-gradient(135deg, #5a0df5 0%, #6b17ff 100%);
    border-radius: 26px; padding: 26px 28px;
    box-shadow: 0 14px 34px rgba(91,22,245,0.28);
}
.pl-hero, .pl-hero * { color: #ffffff; }
.pl-hero-top {
    display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
}
.pl-hero-label { font-size: 1.25rem; font-weight: 700; opacity: 0.88; }
.pl-info {
    display: inline-flex; align-items: center; justify-content: center;
    width: 17px; height: 17px; border: 1.8px solid rgba(255,255,255,0.8);
    border-radius: 50%; font-size: 0.7rem; font-weight: 700; margin-left: 6px;
    vertical-align: middle;
}
.pl-add {
    background: #ffffff; border-radius: 14px; padding: 10px 18px;
    font-weight: 700; white-space: nowrap;
}
.pl-hero .pl-add { color: #5b16f5; }
.pl-hero-amount {
    font-size: 3.1rem; font-weight: 800; letter-spacing: -1px; line-height: 1.1; margin-top: 10px;
}
.pl-hero-delta { font-size: 1.1rem; font-weight: 700; margin-top: 6px; }

.pl-tile {
    display: flex; align-items: center; gap: 14px;
    background: var(--surface); border-radius: 16px;
    padding: 20px 20px; min-height: 40px;
    box-shadow: 0 4px 14px var(--card-shadow);
    border: 1px solid var(--border);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.pl-tile-icon { display: inline-flex; width: 28px; justify-content: center; flex-shrink: 0; }
.pl-tile-title { font-size: 1.15rem; color: var(--text); font-weight: 500; }
.pl-tile-value { font-size: 0.95rem; color: var(--text); font-weight: 700; margin-top: 2px; }
.pl-ring {
    width: 22px; height: 22px; border-radius: 50%;
    border: 3px solid #1d4ed8; display: inline-block;
}
.pl-plus {
    width: 24px; height: 24px; border-radius: 50%; background: #94a3b8;
    color: #ffffff; display: inline-flex; align-items: center; justify-content: center;
    font-weight: 800; line-height: 1; font-size: 1rem;
}

.pl-setup {
    display: flex; align-items: center; gap: 22px;
    background: var(--badge-bg); border-radius: 18px; padding: 22px 26px;
    box-shadow: 0 4px 14px var(--card-shadow);
    transition: transform 0.2s ease;
}
.pl-setup-text { flex: 1; }
.pl-setup-title { font-size: 1.6rem; font-weight: 800; color: #5b16f5; line-height: 1.2; }
.pl-setup-sub { font-size: 1.15rem; color: var(--text); }

.pl-card {
    background: var(--surface); border-radius: 20px; padding: 22px 26px 12px 26px;
    border: 1px solid var(--border);
    box-shadow: 0 4px 14px var(--card-shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.pl-card-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.pl-card-title {
    display: flex; align-items: center; gap: 12px;
    font-size: 1.45rem; font-weight: 800; color: var(--text);
}
.pl-big { font-size: 2.6rem; font-weight: 800; color: var(--text); letter-spacing: -1px; line-height: 1.15; margin-top: 8px; }
.pl-sub { font-size: 1.05rem; color: var(--muted); }
.pl-next { text-align: right; font-size: 1.1rem; color: var(--muted); max-width: 55%; }
.pl-row {
    display: flex; align-items: center; gap: 16px;
    padding: 18px 0; border-top: 1px solid var(--border); margin-top: 18px;
}
.pl-row + .pl-row { margin-top: 0; }
.pl-row-icon {
    width: 56px; height: 56px; border-radius: 50%; background: var(--badge-bg);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.pl-row-main { flex: 1; min-width: 0; }
.pl-row-title { font-size: 1.35rem; font-weight: 800; color: var(--text); }
.pl-row-right { text-align: right; }
.pl-more {
    text-align: center; border-top: 1px solid var(--border);
    padding: 16px 0 12px 0; font-size: 1.35rem; font-weight: 600; color: #5b16f5;
}

[class*="st-key-card_"]:hover .pl-tile,
[class*="st-key-card_"]:hover .pl-setup,
[class*="st-key-card_"]:hover .pl-card {
    transform: translateY(-3px);
    box-shadow: 0 12px 28px var(--card-shadow-hover);
}
[class*="st-key-card_"] { margin-bottom: 4px; }

/* Bottom tab bar: phones and narrow screens only */
.st-key-bottom_nav { display: none; }
@media (max-width: 900px) {
    .st-key-bottom_nav {
        display: block; position: fixed; left: 0; right: 0; bottom: 0; z-index: 999;
        background: var(--surface); border-top: 1px solid var(--border);
        padding: 6px 8px 12px 8px;
    }
    .st-key-bottom_nav .stButton > button {
        background: transparent; box-shadow: none; border: none;
        padding: 0.4rem 0.2rem;
    }
    .st-key-bottom_nav .stButton > button p {
        color: var(--muted); font-size: 0.8rem; font-weight: 600;
    }
    [class*="st-key-tab_on_"] .stButton > button p { color: #5b16f5; font-weight: 800; }
    .block-container { padding-bottom: 6rem; }
    .pl-hero-amount { font-size: 2.6rem; }
    .pl-next { max-width: 50%; font-size: 0.95rem; }
}
</style>
"""


def pl_svg(inner, color=PL_PURPLE, size=24, sw=2):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    )


ICON_CHEVRON = pl_svg('<path d="M9 6l6 6-6 6"/>', size=22, sw=2.6)
ICON_BELL = pl_svg('<path d="M4 5h16v11H9l-5 4z"/>', size=34, sw=2.2)
ICON_SPARKLE = pl_svg('<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>', size=26, sw=1.8)
ICON_TROPHY = pl_svg(
    '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H5v1a3 3 0 0 0 3 3"/>'
    '<path d="M16 6h3v1a3 3 0 0 1-3 3"/><path d="M12 13v4"/><path d="M9 20h6"/>',
    size=26, sw=1.8,
)
ICON_CLOUD = pl_svg('<path d="M7 18a4 4 0 0 1-.5-7.97A5.5 5.5 0 0 1 17 9a4.5 4.5 0 0 1 .5 9z"/>', size=30, sw=2)
ICON_CHART = pl_svg('<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>', color="#0f9d7a", size=24)
TILE_ICON_RING = '<span class="pl-ring"></span>'
TILE_ICON_PLUS = '<span class="pl-plus">+</span>'


def money_html(value):
    """Dollar amount for use inside HTML (&#36; avoids Streamlit treating $ as maths)."""
    sign = "-" if value < 0 else ""
    return f"{sign}&#36;{abs(value):,.2f}"


def setup_ring(done, total):
    circumference = 2 * 3.14159 * 22
    dash = circumference * (done / total if total else 0)
    return (
        '<svg width="56" height="56" viewBox="0 0 52 52">'
        '<circle cx="26" cy="26" r="22" fill="none" stroke="#b8cfdc" stroke-width="5" opacity="0.55"/>'
        f'<circle cx="26" cy="26" r="22" fill="none" stroke="{PL_PURPLE}" stroke-width="5" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circumference:.1f}" '
        'transform="rotate(-90 26 26)"/></svg>'
    )


def dash_card(key, html_block, page, label):
    """Markup plus an invisible button stretched over it, so the whole card is clickable."""
    with st.container(key=key):
        st.markdown(html_block, unsafe_allow_html=True)
        st.button(label, key=f"go_{key}", on_click=go_to, args=(page,))


def dash_tile(key, title, page, icon, value=None):
    value_html = f'<div class="pl-tile-value">{value}</div>' if value else ""
    dash_card(
        key,
        f'<div class="pl-tile"><span class="pl-tile-icon">{icon}</span>'
        f'<div><div class="pl-tile-title">{esc(title)}</div>{value_html}</div></div>',
        page,
        f"Open {title}",
    )


def dashboard_top_bar(initial, event_count):
    avatar_col, pill_col, _, bell_col = st.columns([0.6, 1.6, 4, 2], vertical_alignment="center")

    with avatar_col:
        dash_card(
            "card_top_avatar",
            f'<div class="pl-avatar">{esc(initial)}</div>',
            "Settings",
            "Open account settings",
        )
    with pill_col:
        dash_card("card_top_pill", '<span class="pl-pill">Account</span>', "Settings", "Open account")
    with bell_col:
        upcoming = f"<span>{event_count} upcoming</span>" if event_count else ""
        dot = '<span class="pl-dot"></span>' if event_count else ""
        dash_card(
            "card_top_bell",
            f'<div class="pl-top-right">{upcoming}<span class="pl-bell">{ICON_BELL}{dot}</span></div>',
            "Events",
            "Open events",
        )


def dashboard():
    empty = pd.DataFrame(columns=["Week", "Category", "Amount"])
    expenses = fetch(api_get_expenses, empty)
    listings = fetch(api_get_listings, [])
    events = fetch(api_get_events, [])
    income = fetch(api_get_income, 0.0)

    name = st.session_state.user_name
    initial = (name.strip()[:1] or "S").upper()

    total_spent = float(expenses["Amount"].sum())
    remaining = income - total_spent

    # Hero line: spending in the most recent week that has any
    note = ""
    if not expenses.empty:
        weekly = expenses.groupby("Week")["Amount"].sum().reindex(WEEKS, fill_value=0)
        active_weeks = [week for week in WEEKS if float(weekly[week]) > 0]
        if active_weeks:
            last = active_weeks[-1]
            note = f"&#9660; {money_html(float(weekly[last]))} spent in {esc(last)}"
    if not note:
        note = "Add your income and expenses to get started" if income <= 0 else "No spending logged yet"

    dashboard_top_bar(initial, len(events))

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ---- Hero card ----
    dash_card(
        "card_hero",
        f"""
        <div class="pl-hero">
            <div class="pl-hero-top">
                <span class="pl-hero-label">Your CampusHub balance<span class="pl-info">i</span></span>
                <span class="pl-add">+ Add expense</span>
            </div>
            <div class="pl-hero-amount">{money_html(remaining)}</div>
            <div class="pl-hero-delta">{note}</div>
        </div>
        """,
        "Budget Assistance",
        "Open Budget Assistance",
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ---- 2 x 2 tiles ----
    col_a, col_b = st.columns(2, gap="small")
    with col_a:
        dash_tile("card_tile_budget", "Budget", "Budget Assistance", TILE_ICON_RING, money_html(total_spent))
    with col_b:
        market_value = f"{len(listings)} listing{'s' if len(listings) != 1 else ''}"
        dash_tile("card_tile_market", "Marketplace", "Marketplace", ICON_CHART, market_value)

    col_c, col_d = st.columns(2, gap="small")
    with col_c:
        dash_tile("card_tile_study", "Study Hub", "Study Hub", TILE_ICON_PLUS)
    with col_d:
        if events:
            dash_tile("card_tile_events", "Events", "Events", TILE_ICON_RING, f"{len(events)} upcoming")
        else:
            dash_tile("card_tile_events", "Events", "Events", TILE_ICON_PLUS)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ---- Get set up ----
    steps = [
        (True, "Settings"),  # account created
        (st.session_state.user_university not in ("", UNSET_UNIVERSITY), "Settings"),
        (income > 0, "Budget Assistance"),
        (not expenses.empty, "Budget Assistance"),
        (any(str(item.get("seller", "")) == name for item in listings), "Marketplace"),
    ]
    done = sum(1 for completed, _ in steps if completed)
    if done < len(steps):
        next_page = next(page for completed, page in steps if not completed)
        dash_card(
            "card_setup",
            f"""
            <div class="pl-setup">
                {setup_ring(done, len(steps))}
                <div class="pl-setup-text">
                    <div class="pl-setup-title">Get set up</div>
                    <div class="pl-setup-sub">{done} of {len(steps)} complete</div>
                </div>
                {ICON_CHEVRON}
            </div>
            """,
            next_page,
            "Continue setup",
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ---- Budget summary card ----
    if events:
        nxt = events[0]
        next_text = f"Next deadline<br><b>{esc(nxt.get('title', ''))}</b><br>{esc(nxt.get('deadline', ''))}"
    else:
        next_text = "Next deadline<br>will be shown here"

    if not expenses.empty:
        by_category = expenses.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        top_name = esc(by_category.index[0])
        top_amount = money_html(float(by_category.iloc[0]))
    else:
        top_name, top_amount = "No expenses yet", money_html(0.0)

    dash_card(
        "card_budget_summary",
        f"""
        <div class="pl-card">
            <div class="pl-card-head">
                <div>
                    <div class="pl-card-title">{ICON_CLOUD}<span>Budget</span></div>
                    <div class="pl-big">{money_html(total_spent)}</div>
                    <div class="pl-sub">Spent since all time</div>
                </div>
                <div class="pl-next">{next_text}</div>
            </div>
            <div class="pl-row">
                <span class="pl-row-icon">{ICON_SPARKLE}</span>
                <div class="pl-row-main">
                    <div class="pl-row-title">Top category</div>
                    <div class="pl-sub">{top_name}</div>
                </div>
                <div class="pl-row-right">
                    <div class="pl-row-title">{top_amount}</div>
                    <div class="pl-sub">Since all time</div>
                </div>
            </div>
            <div class="pl-row">
                <span class="pl-row-icon">{ICON_TROPHY}</span>
                <div class="pl-row-main">
                    <div class="pl-row-title">Income left</div>
                    <div class="pl-sub">{money_html(remaining)} of {money_html(income)}</div>
                </div>
                {ICON_CHEVRON}
            </div>
            <div class="pl-more">See all expenses</div>
        </div>
        """,
        "Budget Assistance",
        "Open Budget Assistance",
    )


def bottom_nav(current):
    """Fixed bottom tab bar (shown on narrow screens only)."""
    with st.container(key="bottom_nav"):
        columns = st.columns(len(BOTTOM_TABS))
        for column, (label, page) in zip(columns, BOTTOM_TABS):
            with column:
                state = "on" if current == page else "off"
                st.button(label, key=f"tab_{state}_{label}", on_click=go_to, args=(page,))


# ============================================================
# STUDY HUB
# ============================================================

def render_timer():
    """Live countdown. Runs as a fragment so only this block refreshes."""
    end_time = st.session_state.timer_end
    total = st.session_state.timer_total

    if end_time is None:
        if st.session_state.get("timer_done"):
            st.progress(1.0, text="Session complete")
            st.success("Study session complete. Take a short break.")
        else:
            st.info("No study session is running.")
        return

    remaining = int((end_time - datetime.now()).total_seconds())

    if remaining <= 0:
        # Finish once, then rerun the whole app so the 1-second refresh stops
        st.session_state.timer_end = None
        st.session_state.timer_done = True
        st.rerun()

    elapsed_fraction = min(max(1 - remaining / total, 0.0), 1.0)
    minutes, seconds = divmod(remaining, 60)
    st.progress(elapsed_fraction, text=f"Time remaining: {minutes:02d}:{seconds:02d}")


def study_hub():
    st.title("Study Hub")
    st.write("Your central area for academic productivity.")

    timer_tab, materials_tab, partner_tab = st.tabs(
        ["Study Timer", "Study Materials", "AI Partner"]
    )

    # ---------------- Study timer ----------------
    with timer_tab:
        st.subheader("Lecture Reminder and Study Timer")

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown(
                """
                <div class="info-card">
                    <h3>Next Lecture</h3>
                    <p><b>CS201 Software Engineering</b></p>
                    <p>08:30 AM</p>
                    <p>Batanai Campus</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            with st.container(border=True):
                duration = st.number_input(
                    "Study duration (minutes)",
                    min_value=1,
                    max_value=180,
                    value=25,
                    key="timer_duration",
                )

                start_col, stop_col = st.columns(2)
                with start_col:
                    if st.button("Start Session", key="timer_start"):
                        st.session_state.timer_done = False
                        st.session_state.timer_total = int(duration) * 60
                        st.session_state.timer_end = datetime.now() + timedelta(
                            seconds=st.session_state.timer_total
                        )
                with stop_col:
                    if st.button("Stop Session", key="timer_stop"):
                        st.session_state.timer_end = None
                        st.session_state.timer_done = False

                active = (
                    st.session_state.timer_end is not None
                    and st.session_state.timer_end > datetime.now()
                )
                live_timer = st.fragment(render_timer, run_every=1 if active else None)
                live_timer()

    # ---------------- Study materials ----------------
    with materials_tab:
        st.subheader("Upload Study Material")

        uploaded_file = st.file_uploader("Upload lecture notes", type=["txt", "pdf"])

        if uploaded_file is not None:
            st.success(f"{uploaded_file.name} is ready to process.")

            ai_action = st.radio(
                "AI action",
                ["Summarize Notes", "Generate Quiz"],
                horizontal=True,
            )

            if st.button("Process Material", key="process_material"):
                try:
                    with st.spinner("Processing your material..."):
                        result = api_ai_process_file(ai_action, uploaded_file)
                except ApiError as error:
                    show_api_error(error)
                else:
                    if result:
                        st.markdown("#### Result")
                        st.markdown(result)
                    else:
                        st.info("The server returned an empty result.")

    # ---------------- AI partner ----------------
    with partner_tab:
        st.subheader("Ask Your AI Study Partner")

        module_code = st.text_input("Module code", placeholder="Example: CS101")
        student_query = st.text_area(
            "Your question", placeholder="Ask anything about your module..."
        )

        if st.button("Ask AI", key="ask_ai"):
            if not (module_code.strip() and student_query.strip()):
                st.error("Enter a module code and a question.")
            else:
                try:
                    with st.spinner("Thinking..."):
                        answer = api_ai_ask(module_code.strip().upper(), student_query.strip())
                except ApiError as error:
                    show_api_error(error)
                else:
                    if answer:
                        st.markdown("#### Answer")
                        st.markdown(answer)
                    else:
                        st.info("The server returned an empty answer.")


# ============================================================
# BUDGET ASSISTANCE
# ============================================================

def weekly_bars_html(weekly):
    """Weekly spending as themed HTML bars (native charts ignore the custom theme)."""
    peak = max(float(weekly.max()), 1.0)
    rows = ""
    for week, amount in weekly.items():
        amount = float(amount)
        rows += (
            '<div class="bar-row">'
            f'<span class="bar-label">{esc(week)}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{amount / peak * 100:.1f}%"></div></div>'
            f'<span class="bar-value">&#36;{amount:,.2f}</span>'
            "</div>"
        )
    return f'<div class="info-card">{rows}</div>'


def expenses_table_html(expenses):
    body = "".join(
        f"<tr><td>{esc(row.Week)}</td><td>{esc(row.Category)}</td>"
        f"<td>&#36;{row.Amount:,.2f}</td></tr>"
        for row in expenses.head(100).itertuples(index=False)
    )
    return (
        '<div class="table-wrap"><table class="data-table">'
        "<thead><tr><th>Week</th><th>Category</th><th>Amount</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def budget_tracker():
    st.title("Budget Assistance")
    st.caption(
        "Manual finance tracking is enabled. Automatic EcoCash or bank "
        "synchronization has not been connected."
    )

    saved_income = fetch(api_get_income, 0.0)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        with st.container(border=True):
            st.subheader("Log Finances")

            income_input = st.number_input(
                "Income total ($)",
                min_value=0.0,
                value=float(saved_income),
                step=1.0,
                key="budget_income",
            )

            if st.button("Save Income", key="save_income"):
                try:
                    api_set_income(income_input)
                    saved_income = income_input
                    st.success("Income saved.")
                except ApiError as error:
                    show_api_error(error)

            st.markdown("---")

            exp_amount = st.number_input(
                "Expense amount ($)",
                min_value=0.0,
                value=0.0,
                step=0.50,
                key="budget_amount",
            )

            cat_col, week_col = st.columns(2)
            with cat_col:
                exp_cat = st.selectbox("Expense category", EXPENSE_CATEGORIES)
            with week_col:
                exp_week = st.selectbox("Target week", WEEKS)

            if st.button("Add Expense", key="add_expense"):
                if exp_amount <= 0:
                    st.error("The expense amount must be greater than zero.")
                else:
                    try:
                        api_add_expense(exp_week, exp_cat, exp_amount)
                        st.success("Expense recorded successfully.")
                    except ApiError as error:
                        show_api_error(error)

    expenses = fetch(api_get_expenses, pd.DataFrame(columns=["Week", "Category", "Amount"]))
    total_spent = float(expenses["Amount"].sum())
    remaining = saved_income - total_spent

    with col2:
        st.subheader("Financial Summary")
        st.metric("Income", f"${saved_income:,.2f}")
        st.metric("Total Expenses", f"${total_spent:,.2f}")
        st.metric("Remaining Balance", f"${remaining:,.2f}")

    st.markdown("---")
    st.subheader("Weekly Spending")

    if expenses.empty:
        st.info("No expenses recorded yet.")
        return

    weekly_data = expenses.groupby("Week")["Amount"].sum().reindex(WEEKS, fill_value=0)

    chart_col, table_col = st.columns([1.2, 1], gap="large")
    with chart_col:
        st.markdown(weekly_bars_html(weekly_data), unsafe_allow_html=True)
    with table_col:
        st.markdown("**Expense history**")
        st.markdown(expenses_table_html(expenses), unsafe_allow_html=True)


# ============================================================
# MARKETPLACE
# ============================================================

def marketplace():
    st.title("Student Marketplace")
    st.caption("Buy and sell items within the student community.")

    browse_tab, sell_tab = st.tabs(["Browse Listings", "Sell an Item"])

    with sell_tab:
        st.subheader("Create Marketplace Listing")

        with st.form("sell_form", clear_on_submit=True):
            item_title = st.text_input(
                "Item name", placeholder="Example: Programming textbook"
            )
            col1, col2 = st.columns(2)
            with col1:
                item_price = st.number_input(
                    "Asking price ($)", min_value=0.0, value=0.0, step=1.0
                )
            with col2:
                item_contact = st.text_input(
                    "Contact details", placeholder="Phone / WhatsApp"
                )
            submitted = st.form_submit_button("Publish Listing")

        if submitted:
            if item_title.strip() and item_price > 0 and item_contact.strip():
                try:
                    api_add_listing(item_title.strip(), item_price, item_contact.strip())
                    st.success("Your listing has been published.")
                except ApiError as error:
                    show_api_error(error)
            else:
                st.error("Complete all listing fields.")

    # Browse renders after the sell form so a new listing appears immediately.
    with browse_tab:
        st.subheader("Available Campus Items")

        listings = fetch(api_get_listings, [])

        if not listings:
            st.info("No items have been listed yet.")
        else:
            columns = st.columns(2, gap="medium")
            for index, item in enumerate(listings):
                with columns[index % 2]:
                    st.markdown(
                        f"""
                        <div class="market-card">
                            <h3>{esc(item.get('title', ''))}</h3>
                            <p><b>Price:</b> &#36;{float(item.get('price', 0) or 0):,.2f}</p>
                            <p><b>Contact:</b> {esc(item.get('contact', ''))}</p>
                            <p><b>Seller:</b> {esc(item.get('seller', 'Student'))}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


# ============================================================
# EVENTS
# ============================================================

def events_page():
    st.title("Campus Events")
    st.write("Stay updated with university deadlines, activities and student events.")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    events = fetch(api_get_events, [])

    if not events:
        st.info("There are no upcoming events.")
        return

    for event in sorted(events, key=lambda e: str(e.get("deadline", ""))):
        st.markdown(
            f"""
            <div class="event-card">
                <div style="display:flex; justify-content:space-between;
                            align-items:center; gap:20px;">
                    <div>
                        <h3>{esc(event.get('title', ''))}</h3>
                        <p>Category: <b>{esc(event.get('type', ''))}</b></p>
                    </div>
                    <div class="date-badge">
                        <small>Date / Deadline</small>
                        <h3>{esc(event.get('deadline', ''))}</h3>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# SETTINGS
# ============================================================

def _on_theme_change():
    st.session_state.theme = "dark" if st.session_state.dark_mode_toggle else "light"


def settings_page():
    st.title("Settings")
    st.write("Manage your appearance, legal information, feedback and account.")

    appearance_tab, legal_tab, feedback_tab, account_tab = st.tabs(
        ["Appearance", "Privacy and Terms", "Feedback", "Account"]
    )

    # ---------------- Appearance ----------------
    with appearance_tab:
        st.subheader("Theme")
        st.toggle(
            "Dark mode",
            value=(st.session_state.theme == "dark"),
            key="dark_mode_toggle",
            on_change=_on_theme_change,
        )
        st.caption("Switch between the light and dark theme. The choice applies immediately.")

    # ---------------- Legal ----------------
    with legal_tab:
        st.subheader("Privacy Policy and User Agreement")
        with st.expander("Privacy Policy"):
            st.markdown(PRIVACY_POLICY)
        with st.expander("User Agreement"):
            st.markdown(USER_AGREEMENT)

    # ---------------- Feedback ----------------
    with feedback_tab:
        st.subheader("Send Feedback")
        st.caption("Report a problem, suggest an improvement or tell us what works well.")

        with st.form("feedback_form", clear_on_submit=True):
            category = st.selectbox("Feedback type", FEEDBACK_TYPES)
            message = st.text_area(
                "Your feedback",
                max_chars=1000,
                placeholder="Write your feedback here...",
            )
            submitted = st.form_submit_button("Send Feedback")

        if submitted:
            if len(message.strip()) < 5:
                st.error("Please write at least a few words of feedback.")
            else:
                try:
                    with st.spinner("Sending..."):
                        api_send_feedback(category, message.strip())
                    st.success("Thank you. Your feedback has been sent.")
                except ApiError as error:
                    show_api_error(error)

    # ---------------- Account ----------------
    with account_tab:
        st.subheader("Your account")
        st.markdown(
            f"""
            <div class="info-card">
                <h3>{esc(st.session_state.user_name)}</h3>
                <p>{esc(st.session_state.user_email)}</p>
                <p>{esc(st.session_state.user_university)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader("Delete account")
        st.warning(
            "Deleting your account permanently removes your profile, expenses, "
            "marketplace listings and feedback. This cannot be undone."
        )

        has_password = st.session_state.get("user_has_password", True)

        with st.container(key="danger_zone"):
            with st.form("delete_account_form", clear_on_submit=False):
                if has_password:
                    confirmation = st.text_input(
                        "Confirm your password", type="password",
                        placeholder="Enter your password",
                    )
                else:
                    confirmation = st.text_input(
                        "Type DELETE to confirm", placeholder="DELETE",
                    )
                understood = st.checkbox("I understand that this cannot be undone.")
                delete_clicked = st.form_submit_button("Delete My Account")

        if delete_clicked:
            if not confirmation:
                st.error("Enter your password to confirm." if has_password else "Type DELETE to confirm.")
            elif not understood:
                st.error("Tick the box to confirm you understand.")
            else:
                try:
                    with st.spinner("Deleting your account..."):
                        api_delete_account(confirmation, has_password)
                except ApiError as error:
                    show_api_error(error)
                else:
                    sign_out()
                    st.session_state.flash = "Your account has been deleted."
                    st.rerun()


# ============================================================
# APPLICATION ROUTER
# ============================================================

initialize_session()

if not st.session_state.logged_in:
    handle_google_callback()

needs_profile = st.session_state.logged_in and st.session_state.user_university in ("", UNSET_UNIVERSITY)

st.markdown(theme_css(st.session_state.theme) + BASE_CSS + GOOGLE_CSS + DASH_CSS, unsafe_allow_html=True)
if not st.session_state.logged_in or needs_profile:
    st.markdown(HIDE_SIDEBAR_CSS, unsafe_allow_html=True)

selected_page = None if needs_profile else sidebar_navigation()

if not st.session_state.logged_in:
    authentication_page()
elif needs_profile:
    complete_profile_page()
else:
    routes = {
        "Dashboard": dashboard,
        "Study Hub": study_hub,
        "Budget Assistance": budget_tracker,
        "Marketplace": marketplace,
        "Events": events_page,
        "Settings": settings_page,
    }
    routes.get(selected_page, dashboard)()
    bottom_nav(selected_page)
