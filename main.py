import os
import threading
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import List

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

import models
import schemas
from ai_handler import (
    ask_study_assistant,
    build_question_prompt,
    build_quiz_prompt,
    build_summary_prompt,
    extract_text,
)
from database import Base, SessionLocal, engine, get_db
from google_auth import GOOGLE_PASSWORD_MARKER, router as google_router, user_payload
from security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "30"))  # AI requests per user per day (0 = unlimited)
_ai_usage = {}  # {(user_id, date): count}; per process, resets on restart
_ai_lock = threading.Lock()
bearer_scheme = HTTPBearer(auto_error=False)


def seed_events(db: Session):
    """Placeholder events so the page is not empty. Replace with real dates."""
    if db.query(models.Event).count():
        return
    today = date.today()
    db.add_all(
        [
            models.Event(title="Coursework submission window", type="Deadline", deadline=today + timedelta(days=7)),
            models.Event(title="Examination registration closes", type="Deadline", deadline=today + timedelta(days=14)),
            models.Event(title="Careers and industry expo", type="Event", deadline=today + timedelta(days=21)),
        ]
    )
    db.commit()


def ensure_columns():
    """create_all() never alters existing tables, so add columns introduced for the mobile app."""
    existing = {c["name"] for c in inspect(engine).get_columns("budget_items")}
    with engine.begin() as conn:
        if "client_id" not in existing:
            conn.execute(text("ALTER TABLE budget_items ADD COLUMN client_id VARCHAR(64)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_budget_items_client_id ON budget_items (client_id)"))


def enforce_ai_limit(user: models.StudentUser):
    """Simple daily quota so the free AI tiers are not drained by a few users."""
    if AI_DAILY_LIMIT <= 0:
        return
    today = date.today()
    with _ai_lock:
        for key in [k for k in _ai_usage if k[1] != today]:
            del _ai_usage[key]
        used = _ai_usage.get((user.id, today), 0)
        if used >= AI_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Daily AI limit reached ({AI_DAILY_LIMIT} requests). Try again tomorrow.",
            )
        _ai_usage[(user.id, today)] = used + 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    db = SessionLocal()
    try:
        seed_events(db)
    finally:
        db.close()
    yield


app = FastAPI(title="CampusHub - Core Backend", lifespan=lifespan)

# Streamlit talks to this API server-to-server, so CORS only matters for browser clients.
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=False,  # Bearer tokens, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(google_router)


# ---------- Auth dependency ----------
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.StudentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session has expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    user = db.get(models.StudentUser, user_id) if user_id else None
    if user is None:
        raise unauthorized
    return user


@app.get("/")
def check_health():
    return {"engine_status": "Operational", "active_university_nodes": ["MSU", "UZ", "NUST", "HIT", "GZU"]}


# --- 1. AUTH ---
@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserRegisterSchema, db: Session = Depends(get_db)):
    email = user.email.lower()
    if db.query(models.StudentUser).filter(models.StudentUser.email == email).first():
        raise HTTPException(status_code=400, detail="An account already exists for this email.")

    db_user = models.StudentUser(
        full_name=user.name.strip(),
        email=email,
        university=user.university,
        hashed_password=hash_password(user.password),
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An account already exists for this email.")
    return {"status": "success", "message": f"Account created for {db_user.full_name}."}


@app.post("/auth/login", response_model=schemas.LoginResponse)
def login_user(credentials: schemas.UserLoginSchema, db: Session = Depends(get_db)):
    user = db.query(models.StudentUser).filter(
        models.StudentUser.email == credentials.email.lower()
    ).first()
    # Same message for unknown email and wrong password (no account enumeration)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user_payload(user)}


@app.get("/auth/me", response_model=schemas.UserOut)
def read_me(user: models.StudentUser = Depends(get_current_user)):
    return user_payload(user)


@app.patch("/auth/me", response_model=schemas.UserOut)
def update_me(payload: schemas.ProfileUpdateSchema,
              user: models.StudentUser = Depends(get_current_user),
              db: Session = Depends(get_db)):
    user.university = payload.university
    db.commit()
    return user_payload(user)


# --- 2. AI ---
def run_ai(prompt: str, preference: str = "gemini") -> dict:
    result = ask_study_assistant(prompt, preference=preference)
    if result["provider"] == "Error":
        raise HTTPException(status_code=502, detail=result["response"])
    return result


def read_study_file(file: UploadFile) -> str:
    name = (file.filename or "").lower()
    if not name.endswith((".txt", ".pdf")):
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files are supported.")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (5 MB maximum).")

    try:
        text = extract_text(name, data)
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file.")
    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text found. Scanned PDFs are not supported.",
        )
    return text


@app.post("/study/ai-process")
def query_ai_partner(payload: schemas.ChatPromptSchema, user: models.StudentUser = Depends(get_current_user)):
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="The question cannot be blank.")
    enforce_ai_limit(user)
    return run_ai(payload.prompt, payload.provider_preference)


@app.post("/ai/ask", response_model=schemas.ResultOut)
def ai_ask(payload: schemas.AskSchema, user: models.StudentUser = Depends(get_current_user)):
    enforce_ai_limit(user)
    prompt = build_question_prompt(payload.module_code.strip().upper(), payload.question.strip())
    return {"result": run_ai(prompt)["response"]}


@app.post("/ai/summarize", response_model=schemas.ResultOut)
def ai_summarize(file: UploadFile = File(...), user: models.StudentUser = Depends(get_current_user)):
    enforce_ai_limit(user)
    return {"result": run_ai(build_summary_prompt(read_study_file(file)))["response"]}


@app.post("/ai/quiz", response_model=schemas.ResultOut)
def ai_quiz(file: UploadFile = File(...), user: models.StudentUser = Depends(get_current_user)):
    enforce_ai_limit(user)
    return {"result": run_ai(build_quiz_prompt(read_study_file(file)))["response"]}


# --- 3. BUDGET ---
@app.get("/income")
def get_income(user: models.StudentUser = Depends(get_current_user)):
    return {"income": user.income or 0.0}


@app.put("/income")
def set_income(payload: schemas.IncomeSchema, user: models.StudentUser = Depends(get_current_user),
               db: Session = Depends(get_db)):
    user.income = payload.income
    db.commit()
    return {"income": user.income}


@app.get("/expenses", response_model=List[schemas.ExpenseOut])
def list_expenses(user: models.StudentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(models.BudgetItem)
        .filter(models.BudgetItem.user_id == user.id)
        .order_by(models.BudgetItem.timestamp.desc())
        .all()
    )
    return [
        {"id": r.id, "client_id": r.client_id, "week": r.week, "category": r.category, "amount": r.amount}
        for r in rows
    ]


@app.post("/expenses", status_code=status.HTTP_201_CREATED)
def add_expense(payload: schemas.ExpenseCreateSchema, user: models.StudentUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if payload.client_id and _expense_exists(db, user.id, payload.client_id):
        return {"status": "success", "duplicate": True}  # a retried upload: already saved
    db.add(models.BudgetItem(
        user_id=user.id, amount=payload.amount, category=payload.category,
        week=payload.week, client_id=payload.client_id, is_synced=True,
    ))
    db.commit()
    return {"status": "success"}


def _expense_exists(db: Session, user_id: int, client_id: str) -> bool:
    return db.query(models.BudgetItem.id).filter(
        models.BudgetItem.user_id == user_id, models.BudgetItem.client_id == client_id
    ).first() is not None


@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, user: models.StudentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    row = db.query(models.BudgetItem).filter(
        models.BudgetItem.id == expense_id, models.BudgetItem.user_id == user.id
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found.")
    db.delete(row)
    db.commit()
    return {"status": "success"}


@app.post("/budget/sync-push")
def sync_offline_budget_data(items: List[schemas.BudgetEntrySchema],
                             user: models.StudentUser = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    try:
        new_rows, seen = [], set()
        for e in items:
            if e.client_id:
                if e.client_id in seen or _expense_exists(db, user.id, e.client_id):
                    continue  # already uploaded earlier (retry after a timeout)
                seen.add(e.client_id)
            new_rows.append(models.BudgetItem(user_id=user.id, amount=e.amount, category=e.category,
                                              week=e.week, client_id=e.client_id, is_synced=True))
        db.add_all(new_rows)
        db.commit()
    except SQLAlchemyError as err:
        db.rollback()
        print(f"Budget sync failed: {err}")
        raise HTTPException(status_code=500, detail="Synchronisation failed. Please try again.")
    return {"status": "success", "synchronized_records": len(new_rows), "skipped_duplicates": len(items) - len(new_rows)}


# --- 4. MARKETPLACE ---
@app.get("/marketplace", response_model=List[schemas.MarketplaceOut])
def get_marketplace_feed(user: models.StudentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(models.MarketplaceItem, models.StudentUser.full_name)
        .join(models.StudentUser, models.StudentUser.id == models.MarketplaceItem.seller_id)
        .order_by(models.MarketplaceItem.timestamp.desc())
        .all()
    )
    return [
        {"id": item.id, "title": item.title, "price": item.price,
         "contact": item.contact_details, "seller": seller, "timestamp": item.timestamp,
         "is_mine": item.seller_id == user.id}
        for item, seller in rows
    ]


@app.post("/marketplace", status_code=status.HTTP_201_CREATED)
def post_marketplace_listing(item: schemas.MarketplaceCreateSchema,
                             user: models.StudentUser = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    db.add(models.MarketplaceItem(
        title=item.title.strip(), price=item.price, contact_details=item.contact.strip(),
        seller_id=user.id, is_synced=True,
    ))
    db.commit()
    return {"status": "success", "message": f"Listed {item.title}."}


@app.delete("/marketplace/{item_id}")
def delete_marketplace_listing(item_id: int, user: models.StudentUser = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    row = db.query(models.MarketplaceItem).filter(
        models.MarketplaceItem.id == item_id, models.MarketplaceItem.seller_id == user.id
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    db.delete(row)
    db.commit()
    return {"status": "success"}


# --- 5. EVENTS ---
@app.get("/events", response_model=List[schemas.EventOut])
def list_events(user: models.StudentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Event)
        .filter(models.Event.deadline >= date.today())
        .order_by(models.Event.deadline)
        .all()
    )
# --- 6. FEEDBACK & ACCOUNT ---
@app.post("/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(payload: schemas.FeedbackSchema,
                    user: models.StudentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    db.add(models.Feedback(user_id=user.id, category=payload.category,
                           message=payload.message.strip()))
    db.commit()
    return {"status": "success"}


@app.post("/account/delete")
def delete_account(payload: schemas.DeleteAccountSchema,
                   user: models.StudentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    # 403, not 401, so the frontend does not mistake a wrong password for an expired session
    if user.hashed_password == GOOGLE_PASSWORD_MARKER:
        # Google-only account: there is no password, so confirm by typing DELETE
        if (payload.confirm_text or "").strip().upper() != "DELETE":
            raise HTTPException(status_code=403, detail="Type DELETE to confirm.")
    elif not verify_password(payload.password or "", user.hashed_password):
        raise HTTPException(status_code=403, detail="Incorrect password.")
    try:
        db.query(models.BudgetItem).filter(models.BudgetItem.user_id == user.id).delete(synchronize_session=False)
        db.query(models.MarketplaceItem).filter(models.MarketplaceItem.seller_id == user.id).delete(synchronize_session=False)
        db.query(models.Feedback).filter(models.Feedback.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
    except SQLAlchemyError as err:
        db.rollback()
        print(f"Account deletion failed: {err}")
        raise HTTPException(status_code=500, detail="Could not delete the account. Please try again.")
    return {"status": "success"}