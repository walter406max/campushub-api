"""
Google sign-in for CampusHub (OAuth 2.0 authorization-code flow, handled by the backend).

Flow
1. Browser opens  GET /auth/google/login            -> redirect to Google
2. Google calls   GET /auth/google/callback         -> we verify the ID token, find or create
                                                       the user, then redirect to the frontend
                                                       with a one-time code (?google_code=...)
3. Frontend calls POST /auth/google/exchange        -> swaps the code for our normal JWT

The one-time code keeps the real access token out of URLs and browser history.
Note: codes live in process memory. With several backend workers, store them in the DB or Redis.

Environment variables (.env):
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    BACKEND_PUBLIC_URL   (default http://localhost:8000)  - must match the redirect URI in Google Cloud
    FRONTEND_URL         (default http://localhost:8501)
"""

import hmac
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import jwt
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from security import ALGORITHM, SECRET_KEY, create_access_token

load_dotenv()
log = logging.getLogger("campushub.google")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Audiences accepted for ID tokens from the Android app. The app asks Google for a token for the
# WEB client id (serverClientId), so normally this is just GOOGLE_CLIENT_ID.
GOOGLE_MOBILE_AUDIENCES = [a for a in [GOOGLE_CLIENT_ID, os.getenv("GOOGLE_ANDROID_CLIENT_ID", "")] if a]
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000").rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8501").rstrip("/")

REDIRECT_URI = f"{BACKEND_PUBLIC_URL}/auth/google/callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

NONCE_COOKIE = "campushub_google_nonce"
STATE_LIFETIME_MINUTES = 10
CODE_LIFETIME_SECONDS = 60

# Stored in hashed_password for accounts created through Google. It is not a valid
# "pbkdf2_sha256$..." string, so verify_password() always rejects it: no password login.
GOOGLE_PASSWORD_MARKER = "!google"

router = APIRouter(prefix="/auth/google", tags=["google"])


def user_payload(user: models.StudentUser) -> dict:
    return {
        "name": user.full_name,
        "email": user.email,
        "university": user.university,
        "has_password": user.hashed_password != GOOGLE_PASSWORD_MARKER,
    }


# ---------- One-time exchange codes ----------
_codes: Dict[str, Tuple[int, float]] = {}
_codes_lock = threading.Lock()


def _store_code(user_id: int) -> str:
    now = time.time()
    code = secrets.token_urlsafe(32)
    with _codes_lock:
        for key in [k for k, (_, exp) in _codes.items() if exp <= now]:
            del _codes[key]
        _codes[code] = (user_id, now + CODE_LIFETIME_SECONDS)
    return code


def _consume_code(code: str) -> Optional[int]:
    with _codes_lock:
        entry = _codes.pop(code, None)  # pop = single use
    if entry and entry[1] > time.time():
        return entry[0]
    return None


# ---------- Helpers ----------
def _fail(message: str) -> RedirectResponse:
    """Send the browser back to the frontend with a readable error."""
    response = RedirectResponse(f"{FRONTEND_URL}/?{urlencode({'google_error': message})}", status_code=303)
    response.delete_cookie(NONCE_COOKIE)
    return response



def _find_or_create_google_user(db: Session, claims: dict) -> Optional[models.StudentUser]:
    """Shared by the web callback and the mobile endpoint."""
    email = (claims.get("email") or "").strip().lower()
    user = db.query(models.StudentUser).filter(models.StudentUser.email == email).first()
    if user is None:
        name = (claims.get("name") or email.split("@")[0]).strip()[:100] or "Student"
        user = models.StudentUser(
            full_name=name,
            email=email,
            university=schemas.UNSET_UNIVERSITY,  # the user picks it right after signing in
            hashed_password=GOOGLE_PASSWORD_MARKER,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:  # two requests raced to create the same account
            db.rollback()
            user = db.query(models.StudentUser).filter(models.StudentUser.email == email).first()
    return user


# ---------- Routes ----------
@router.get("/login")
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return _fail("Google sign-in is not configured on the server.")

    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {
            "purpose": "google_oauth",
            "nonce": nonce,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_LIFETIME_MINUTES),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{AUTH_URL}?{urlencode(params)}", status_code=303)
    # The nonce cookie ties the callback to the browser that started the flow (login-CSRF protection)
    response.set_cookie(
        NONCE_COOKIE,
        nonce,
        max_age=STATE_LIFETIME_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=BACKEND_PUBLIC_URL.startswith("https"),
    )
    return response


@router.get("/callback")
def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if error:
        return _fail("Google sign-in was cancelled.")
    if not code or not state:
        return _fail("Google sign-in failed. Please try again.")

    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return _fail("The sign-in attempt expired. Please try again.")

    cookie_nonce = request.cookies.get(NONCE_COOKIE, "")
    if (
        payload.get("purpose") != "google_oauth"
        or not cookie_nonce
        or not hmac.compare_digest(cookie_nonce, str(payload.get("nonce", "")))
    ):
        return _fail("The sign-in attempt could not be verified. Please try again.")

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        claims = google_id_token.verify_oauth2_token(
            token_response.json()["id_token"], google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception as err:
        log.warning("Google token exchange failed: %s", err)
        return _fail("Could not verify your Google account. Please try again.")

    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        return _fail("Your Google email address is not verified.")

    user = _find_or_create_google_user(db, claims)
    if user is None:
        return _fail("Could not create your account. Please try again.")

    response = RedirectResponse(
        f"{FRONTEND_URL}/?{urlencode({'google_code': _store_code(user.id)})}", status_code=303
    )
    response.delete_cookie(NONCE_COOKIE)
    return response


@router.post("/exchange", response_model=schemas.LoginResponse)
def google_exchange(payload: schemas.GoogleExchangeSchema, db: Session = Depends(get_db)):
    user_id = _consume_code(payload.code)
    user = db.get(models.StudentUser, user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Google sign-in link expired. Please try again.",
        )
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user_payload(user)}


@router.post("/mobile", response_model=schemas.LoginResponse)
def google_mobile(payload: schemas.GoogleMobileSchema, db: Session = Depends(get_db)):
    """Android app flow: the Google SDK on the phone returns an ID token; we verify it and sign in."""
    if not GOOGLE_MOBILE_AUDIENCES:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on the server.")
    try:
        claims = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), GOOGLE_MOBILE_AUDIENCES
        )
    except Exception as err:
        log.warning("Mobile Google token rejected: %s", err)
        raise HTTPException(status_code=401, detail="Could not verify your Google account. Please try again.")

    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Your Google email address is not verified.")

    user = _find_or_create_google_user(db, claims)
    if user is None:
        raise HTTPException(status_code=500, detail="Could not create your account. Please try again.")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user_payload(user)}
