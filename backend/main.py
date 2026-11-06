"""Clinic appointment API (FastAPI + SQLite). Built for a Hindi voice agent.

Run:   uvicorn main:app --reload
Docs:  http://127.0.0.1:8000/docs

Every endpoint except /health needs the header:  Authorization: Bearer <CLINIC_API_KEY>
That key only stops random callers from using the API. Real patient login
and rate limiting come in a later phase.
"""
import contextlib
import datetime as dt
import os
import re
import secrets
import sqlite3
import unicodedata
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, field_validator

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TIME_FORMAT = "%Y-%m-%dT%H:%M"

BOOKING_LEAD_MINUTES = 30      # cannot book a slot starting in less than this
CHANGE_NOTICE_MINUTES = 60     # cannot cancel/reschedule closer than this
MAX_ACTIVE_APPOINTMENTS = 3    # per phone number

WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई",
             "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]


# ---------------------------------------------------------------- settings
def db_path() -> str:
    return os.getenv("CLINIC_DB_PATH", "clinic.db")


def api_key() -> str:
    return os.getenv("CLINIC_API_KEY", "dev-clinic-key")


def now_ist() -> dt.datetime:
    """Current India time without tzinfo (slots are stored the same way)."""
    return dt.datetime.now(IST).replace(tzinfo=None)


# ------------------------------------------------------------------ errors
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def fail(status: int, code: str, message: str):
    raise ApiError(status, code, message)


app = FastAPI(title="Clinic Appointment API", version="1.0")


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status,
                        content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    msg = str(first.get("msg", "invalid input")).removeprefix("Value error, ")
    field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query"))
    return JSONResponse(status_code=422, content={"error": {
        "code": "invalid_input", "message": f"{field}: {msg}" if field else msg}})


bearer = HTTPBearer(auto_error=False)  # also gives /docs a working Authorize button


def require_key(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if (not creds or creds.scheme.lower() != "bearer"
            or not secrets.compare_digest(creds.credentials, api_key())):
        fail(401, "unauthorized", "Missing or wrong API key.")


# ---------------------------------------------------------------- database
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=10, isolation_level=None)  # we manage transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextlib.contextmanager
def tx(conn: sqlite3.Connection):
    """All-or-nothing write. BEGIN IMMEDIATE takes the write lock up front,
    so two callers can never both read 'free' and both book the same slot."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def audit(conn, action: str, appointment_id: Optional[int], detail: str = ""):
    conn.execute("INSERT INTO audit_log (ts, actor, action, appointment_id, detail) VALUES (?,?,?,?,?)",
                 (now_ist().isoformat(timespec="seconds"), "agent", action, appointment_id, detail))


# ----------------------------------------------------------------- helpers
def normalize_phone(raw: str) -> str:
    """Return a 10-digit Indian mobile number or raise ValueError."""
    digits = re.sub(r"[\s\-()]", "", str(raw))
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError("phone number must be a 10-digit Indian mobile number")
    return digits


def clean_name(raw: str) -> str:
    name = " ".join(str(raw).split())
    if not 2 <= len(name) <= 60:
        raise ValueError("name must be 2 to 60 characters")
    for ch in name:
        if not (ch.isalpha() or unicodedata.category(ch).startswith("M") or ch in " .'-"):
            raise ValueError("name can contain only letters")
    return name


def phone_or_fail(raw: str) -> str:
    try:
        return normalize_phone(raw)
    except ValueError as e:
        fail(422, "invalid_input", f"patient_phone: {e}")


def mask(phone: str) -> str:
    return "******" + phone[-4:]


def parse_time(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, TIME_FORMAT)


def hindi_time(t: dt.datetime) -> str:
    """17:20 -> 'शाम 5 बजकर 20 मिनट' (easy for a TTS voice to read)."""
    h = t.hour
    period = "सुबह" if h < 12 else "दोपहर" if h < 16 else "शाम" if h < 19 else "रात"
    h12 = h % 12 or 12
    return f"{period} {h12} बजे" if t.minute == 0 else f"{period} {h12} बजकर {t.minute} मिनट"


def hindi_when(t: dt.datetime) -> str:
    return f"{WEEKDAYS_HI[t.weekday()]}, {t.day} {MONTHS_HI[t.month - 1]}, {hindi_time(t)}"


APPT_SELECT = """
SELECT a.id, a.patient_name, a.patient_phone, a.reason, a.language, a.status,
       d.id AS doctor_id, d.name AS doctor_name, d.name_hi AS doctor_name_hi,
       d.specialty, d.specialty_hi, s.id AS slot_id, s.start_time, s.end_time
FROM appointments a
JOIN doctors d ON d.id = a.doctor_id
JOIN slots s ON s.id = a.slot_id
"""


def appt_out(row) -> dict:
    start = parse_time(row["start_time"])
    return {
        "appointment_id": row["id"],
        "status": row["status"],
        "patient_name": row["patient_name"],
        "patient_phone_masked": mask(row["patient_phone"]),
        "reason": row["reason"],
        "doctor_id": row["doctor_id"],
        "doctor_name": row["doctor_name"],
        "doctor_name_hi": row["doctor_name_hi"],
        "specialty": row["specialty"],
        "specialty_hi": row["specialty_hi"],
        "slot_id": row["slot_id"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "weekday": WEEKDAYS_EN[start.weekday()],
        "when_hi": hindi_when(start),
    }


def get_owned_appointment(conn, appointment_id: int, phone: str):
    """Only the phone number that booked can see or change an appointment.
    A wrong phone gets the same 'not found' so nobody can probe ids."""
    row = conn.execute(APPT_SELECT + " WHERE a.id = ? AND a.patient_phone = ?",
                       (appointment_id, phone)).fetchone()
    if not row:
        fail(404, "not_found", "No appointment with this id for this phone number.")
    return row


# ------------------------------------------------------------------ models
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PhoneIn(_Strict):
    patient_phone: str

    @field_validator("patient_phone")
    @classmethod
    def _phone(cls, v):
        return normalize_phone(v)


class BookIn(PhoneIn):
    patient_name: str
    doctor_id: int
    slot_id: int
    reason: Optional[str] = None
    language: Literal["hi", "en"] = "hi"

    @field_validator("patient_name")
    @classmethod
    def _name(cls, v):
        return clean_name(v)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v):
        v = " ".join(v.split()) if v else None
        if v and len(v) > 200:
            raise ValueError("reason is too long (max 200 characters)")
        return v or None


class RescheduleIn(PhoneIn):
    new_slot_id: int


class CallbackIn(PhoneIn):
    patient_name: str
    reason: str
    preferred_time: Optional[str] = None

    @field_validator("patient_name")
    @classmethod
    def _name(cls, v):
        return clean_name(v)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v):
        v = " ".join(v.split())
        if not 1 <= len(v) <= 300:
            raise ValueError("reason must be 1 to 300 characters")
        return v

    @field_validator("preferred_time")
    @classmethod
    def _pref(cls, v):
        v = " ".join(v.split()) if v else None
        if v and len(v) > 100:
            raise ValueError("preferred_time is too long")
        return v or None


# --------------------------------------------------------- read endpoints
@app.get("/health")
def health():
    return {"status": "ok"}


protected = [Depends(require_key)]


@app.get("/today", dependencies=protected)
def today():
    """The agent calls this first so it can turn 'kal' or 'agle mangalwar' into a date."""
    now = now_ist()
    days = []
    for i in range(15):
        d = now.date() + dt.timedelta(days=i)
        days.append({
            "date": d.isoformat(),
            "weekday": WEEKDAYS_EN[d.weekday()],
            "weekday_hi": WEEKDAYS_HI[d.weekday()],
            "label": "today" if i == 0 else "tomorrow" if i == 1 else "",
        })
    return {
        "now": now.strftime(TIME_FORMAT),
        "date": now.date().isoformat(),
        "weekday": WEEKDAYS_EN[now.weekday()],
        "weekday_hi": WEEKDAYS_HI[now.weekday()],
        "now_hi": hindi_when(now),
        "upcoming_days": days,
    }


@app.get("/clinic", dependencies=protected)
def clinic(conn=Depends(get_db)):
    return dict(conn.execute("SELECT * FROM clinic WHERE id = 1").fetchone())


@app.get("/faqs", dependencies=protected)
def faqs(topic: Optional[str] = None, conn=Depends(get_db)):
    if topic:
        rows = conn.execute("SELECT * FROM faqs WHERE topic = ?", (topic.strip().lower(),)).fetchall()
        if not rows:
            known = [r["topic"] for r in conn.execute("SELECT topic FROM faqs")]
            fail(404, "not_found", f"Unknown topic. Known topics: {', '.join(known)}")
    else:
        rows = conn.execute("SELECT * FROM faqs ORDER BY id").fetchall()
    return {"faqs": [dict(r) for r in rows]}


@app.get("/doctors", dependencies=protected)
def doctors(specialty: Optional[str] = None, conn=Depends(get_db)):
    sql = "SELECT id, name, name_hi, specialty, specialty_hi, fee, languages FROM doctors WHERE active = 1"
    args: list = []
    if specialty:
        sql += " AND (LOWER(specialty) LIKE ? OR specialty_hi LIKE ?)"
        like = f"%{specialty.strip().lower()}%"
        args += [like, f"%{specialty.strip()}%"]
    return {"doctors": [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]}


@app.get("/doctors/{doctor_id}/slots", dependencies=protected)
def doctor_slots(doctor_id: int, date: str, limit: int = Query(default=30, ge=1, le=60),
                 conn=Depends(get_db)):
    doc = conn.execute("SELECT id, name, name_hi FROM doctors WHERE id = ? AND active = 1",
                       (doctor_id,)).fetchone()
    if not doc:
        fail(404, "not_found", "No such doctor.")
    try:
        day = dt.date.fromisoformat(date)
    except ValueError:
        fail(422, "invalid_input", "date: use YYYY-MM-DD, for example 2026-10-27")

    earliest = (now_ist() + dt.timedelta(minutes=BOOKING_LEAD_MINUTES)).strftime(TIME_FORMAT)
    rows = conn.execute(
        "SELECT id, start_time, end_time FROM slots WHERE doctor_id = ? AND status = 'free' "
        "AND start_time >= ? AND start_time >= ? AND start_time < ? ORDER BY start_time LIMIT ?",
        (doctor_id, earliest, f"{day.isoformat()}T00:00", f"{(day + dt.timedelta(days=1)).isoformat()}T00:00", limit),
    ).fetchall()
    slots = [{"slot_id": r["id"], "start_time": r["start_time"], "end_time": r["end_time"],
              "time_hi": hindi_time(parse_time(r["start_time"]))} for r in rows]

    next_available = None
    if not slots:
        nxt = conn.execute(
            "SELECT start_time FROM slots WHERE doctor_id = ? AND status = 'free' AND start_time >= ? "
            "AND start_time >= ? ORDER BY start_time LIMIT 1",
            (doctor_id, earliest, f"{day.isoformat()}T00:00")).fetchone()
        if nxt:
            t = parse_time(nxt["start_time"])
            next_available = {"date": t.date().isoformat(), "weekday": WEEKDAYS_EN[t.weekday()],
                              "when_hi": hindi_when(t)}
    return {"doctor_id": doc["id"], "doctor_name": doc["name"], "doctor_name_hi": doc["name_hi"],
            "date": day.isoformat(), "weekday": WEEKDAYS_EN[day.weekday()],
            "weekday_hi": WEEKDAYS_HI[day.weekday()], "slots": slots, "next_available": next_available}


# ------------------------------------------------------- booking endpoints
@app.post("/appointments", status_code=201, dependencies=protected)
def book(body: BookIn, conn=Depends(get_db)):
    now = now_ist()
    try:
        with tx(conn):
            slot = conn.execute(
                "SELECT s.*, d.active FROM slots s JOIN doctors d ON d.id = s.doctor_id WHERE s.id = ?",
                (body.slot_id,)).fetchone()
            if not slot or slot["doctor_id"] != body.doctor_id or not slot["active"]:
                fail(404, "not_found", "That slot does not exist for this doctor.")
            start = parse_time(slot["start_time"])
            if start < now + dt.timedelta(minutes=BOOKING_LEAD_MINUTES):
                fail(409, "too_soon", "That time is too soon or already past. Please pick a later slot.")
            if slot["status"] != "free":
                fail(409, "slot_taken", "That slot was just taken. Please pick another one.")

            active = conn.execute(
                "SELECT COUNT(*) FROM appointments a JOIN slots s ON s.id = a.slot_id "
                "WHERE a.patient_phone = ? AND a.status = 'booked' AND s.start_time >= ?",
                (body.patient_phone, now.strftime(TIME_FORMAT))).fetchone()[0]
            if active >= MAX_ACTIVE_APPOINTMENTS:
                fail(409, "limit_reached",
                     f"This number already has {MAX_ACTIVE_APPOINTMENTS} upcoming appointments.")
            clash = conn.execute(
                "SELECT 1 FROM appointments a JOIN slots s ON s.id = a.slot_id "
                "WHERE a.patient_phone = ? AND a.status = 'booked' AND s.start_time = ?",
                (body.patient_phone, slot["start_time"])).fetchone()
            if clash:
                fail(409, "time_clash", "This number already has an appointment at that time.")

            # Conditional update: succeeds only if the slot is still free
            if conn.execute("UPDATE slots SET status = 'booked' WHERE id = ? AND status = 'free'",
                            (body.slot_id,)).rowcount != 1:
                fail(409, "slot_taken", "That slot was just taken. Please pick another one.")
            stamp = now.isoformat(timespec="seconds")
            cur = conn.execute(
                "INSERT INTO appointments (patient_name, patient_phone, doctor_id, slot_id, reason, "
                "language, status, created_at, updated_at) VALUES (?,?,?,?,?,?, 'booked', ?, ?)",
                (body.patient_name, body.patient_phone, body.doctor_id, body.slot_id, body.reason,
                 body.language, stamp, stamp))
            appt_id = cur.lastrowid
            audit(conn, "book", appt_id, f"slot {body.slot_id}")
    except sqlite3.IntegrityError:
        fail(409, "slot_taken", "That slot was just taken. Please pick another one.")
    return appt_out(conn.execute(APPT_SELECT + " WHERE a.id = ?", (appt_id,)).fetchone())


@app.get("/appointments", dependencies=protected)
def list_appointments(phone: str, conn=Depends(get_db)):
    p = phone_or_fail(phone)
    rows = conn.execute(
        APPT_SELECT + " WHERE a.patient_phone = ? AND a.status = 'booked' AND s.start_time >= ? "
        "ORDER BY s.start_time", (p, now_ist().strftime(TIME_FORMAT))).fetchall()
    return {"appointments": [appt_out(r) for r in rows]}


@app.get("/appointments/{appointment_id}", dependencies=protected)
def get_appointment(appointment_id: int, phone: str, conn=Depends(get_db)):
    return appt_out(get_owned_appointment(conn, appointment_id, phone_or_fail(phone)))


@app.post("/appointments/{appointment_id}/cancel", dependencies=protected)
def cancel(appointment_id: int, body: PhoneIn, conn=Depends(get_db)):
    with tx(conn):
        row = get_owned_appointment(conn, appointment_id, body.patient_phone)
        if row["status"] != "booked":
            fail(409, "not_active", "This appointment is already cancelled.")
        if parse_time(row["start_time"]) < now_ist() + dt.timedelta(minutes=CHANGE_NOTICE_MINUTES):
            fail(409, "too_late", "Appointments can be cancelled only up to one hour before. "
                                  "Please ask for a callback instead.")
        conn.execute("UPDATE appointments SET status = 'cancelled', updated_at = ? "
                     "WHERE id = ? AND status = 'booked'",
                     (now_ist().isoformat(timespec="seconds"), appointment_id))
        conn.execute("UPDATE slots SET status = 'free' WHERE id = ?", (row["slot_id"],))
        audit(conn, "cancel", appointment_id, f"slot {row['slot_id']}")
    return appt_out(conn.execute(APPT_SELECT + " WHERE a.id = ?", (appointment_id,)).fetchone())


@app.post("/appointments/{appointment_id}/reschedule", dependencies=protected)
def reschedule(appointment_id: int, body: RescheduleIn, conn=Depends(get_db)):
    now = now_ist()
    try:
        with tx(conn):
            row = get_owned_appointment(conn, appointment_id, body.patient_phone)
            if row["status"] != "booked":
                fail(409, "not_active", "This appointment is cancelled.")
            if parse_time(row["start_time"]) < now + dt.timedelta(minutes=CHANGE_NOTICE_MINUTES):
                fail(409, "too_late", "Appointments can be changed only up to one hour before. "
                                      "Please ask for a callback instead.")
            new = conn.execute("SELECT * FROM slots WHERE id = ?", (body.new_slot_id,)).fetchone()
            if not new or new["doctor_id"] != row["doctor_id"]:
                fail(404, "not_found", "That slot does not exist for the same doctor.")
            if parse_time(new["start_time"]) < now + dt.timedelta(minutes=BOOKING_LEAD_MINUTES):
                fail(409, "too_soon", "That time is too soon or already past.")
            if new["id"] == row["slot_id"]:
                fail(409, "same_slot", "That is already your appointment time.")
            if conn.execute("UPDATE slots SET status = 'booked' WHERE id = ? AND status = 'free'",
                            (new["id"],)).rowcount != 1:
                fail(409, "slot_taken", "That slot was just taken. Please pick another one.")
            conn.execute("UPDATE slots SET status = 'free' WHERE id = ?", (row["slot_id"],))
            conn.execute("UPDATE appointments SET slot_id = ?, updated_at = ? WHERE id = ?",
                         (new["id"], now.isoformat(timespec="seconds"), appointment_id))
            audit(conn, "reschedule", appointment_id, f"slot {row['slot_id']} -> {new['id']}")
    except sqlite3.IntegrityError:
        fail(409, "slot_taken", "That slot was just taken. Please pick another one.")
    return appt_out(conn.execute(APPT_SELECT + " WHERE a.id = ?", (appointment_id,)).fetchone())


@app.post("/callbacks", status_code=201, dependencies=protected)
def request_callback(body: CallbackIn, conn=Depends(get_db)):
    """For anything the agent should not handle: medical questions, complaints, late changes."""
    with tx(conn):
        cur = conn.execute(
            "INSERT INTO callbacks (patient_name, patient_phone, reason, preferred_time, created_at) "
            "VALUES (?,?,?,?,?)",
            (body.patient_name, body.patient_phone, body.reason, body.preferred_time,
             now_ist().isoformat(timespec="seconds")))
        audit(conn, "callback", None, f"callback {cur.lastrowid}")
    return {"callback_id": cur.lastrowid, "status": "new"}