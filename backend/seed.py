"""Create (or reset) the clinic database with FAKE data.

Run it once:   python seed.py

WARNING: this deletes the old clinic.db and starts again, so every booking
made so far is lost. Stop the API (uvicorn) before running it.
"""
import datetime as dt
import os
import random
import sqlite3
import sys

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))  # India has no daylight saving

DEFAULT_DB_PATH = "clinic.db"
SLOT_MINUTES = 20
BOOKING_WINDOW_DAYS = 14  # how many days ahead slots are created
TIME_FORMAT = "%Y-%m-%dT%H:%M"  # slot times are stored as local India time

SCHEMA = """
CREATE TABLE clinic (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    name_hi TEXT NOT NULL,
    address TEXT NOT NULL,
    address_hi TEXT NOT NULL,
    phone TEXT NOT NULL,
    hours TEXT NOT NULL,
    hours_hi TEXT NOT NULL
);

CREATE TABLE faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL UNIQUE,
    question_en TEXT NOT NULL,
    answer_en TEXT NOT NULL,
    question_hi TEXT NOT NULL,
    answer_hi TEXT NOT NULL
);

CREATE TABLE doctors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_hi TEXT NOT NULL,
    specialty TEXT NOT NULL,
    specialty_hi TEXT NOT NULL,
    fee INTEGER NOT NULL,
    languages TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'free' CHECK (status IN ('free', 'booked')),
    UNIQUE (doctor_id, start_time)
);
CREATE INDEX idx_slots_lookup ON slots (doctor_id, start_time, status);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id),
    slot_id INTEGER NOT NULL REFERENCES slots(id),
    reason TEXT,
    language TEXT NOT NULL DEFAULT 'hi',
    status TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_appointments_phone ON appointments (patient_phone, status);
-- Last line of defence against double-booking: the database itself refuses a
-- second active appointment for the same slot, even if the code has a bug.
CREATE UNIQUE INDEX uq_active_appointment_per_slot
    ON appointments (slot_id) WHERE status = 'booked';

CREATE TABLE callbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    reason TEXT NOT NULL,
    preferred_time TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'done')),
    created_at TEXT NOT NULL
);

-- Every change made through the API is recorded here
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    appointment_id INTEGER,
    detail TEXT
);
"""

CLINIC = {
    "name": "Sunrise Family Clinic",
    "name_hi": "सनराइज फैमिली क्लिनिक",
    "address": "12, Green Park Market, New Delhi",
    "address_hi": "12, ग्रीन पार्क मार्केट, नई दिल्ली",
    "phone": "011-4000-0000",
    "hours": "Monday to Saturday, 10 AM to 8 PM. Closed on Sundays.",
    "hours_hi": "सोमवार से शनिवार, सुबह 10 बजे से रात 8 बजे तक। रविवार को क्लिनिक बंद रहता है।",
}

FAQS = [
    (
        "hours",
        "When is the clinic open?",
        "We are open Monday to Saturday, 10 AM to 8 PM, and closed on Sundays. Each doctor sits at different times, so check the available slots.",
        "क्लिनिक कब खुलता है?",
        "क्लिनिक सोमवार से शनिवार, सुबह 10 बजे से रात 8 बजे तक खुलता है और रविवार को बंद रहता है। हर डॉक्टर के बैठने का समय अलग है, इसलिए उपलब्ध स्लॉट देख लें।",
    ),
    (
        "address",
        "Where is the clinic?",
        "The clinic is at 12, Green Park Market, New Delhi.",
        "क्लिनिक कहाँ है?",
        "क्लिनिक 12, ग्रीन पार्क मार्केट, नई दिल्ली में है।",
    ),
    (
        "fees",
        "What is the consultation fee?",
        "The consultation fee is between 400 and 700 rupees, depending on the doctor.",
        "कंसल्टेशन फीस कितनी है?",
        "डॉक्टर के अनुसार कंसल्टेशन फीस चार सौ से सात सौ रुपये तक है।",
    ),
    (
        "what_to_bring",
        "What should I bring to the appointment?",
        "Please bring old prescriptions, any reports, and a photo ID, and arrive ten minutes early.",
        "अपॉइंटमेंट पर क्या लाना होगा?",
        "कृपया पुराने पर्चे, रिपोर्ट और कोई फोटो पहचान पत्र साथ लाएँ, और दस मिनट पहले पहुँचें।",
    ),
    (
        "cancellation",
        "Can I cancel or change my appointment?",
        "Yes, you can cancel or reschedule up to one hour before the appointment.",
        "क्या मैं अपॉइंटमेंट कैंसिल या बदल सकता हूँ?",
        "जी हाँ, आप अपॉइंटमेंट से एक घंटा पहले तक उसे कैंसिल या बदल सकते हैं।",
    ),
    (
        "payment",
        "How can I pay?",
        "We accept cash, UPI and cards.",
        "भुगतान कैसे कर सकते हैं?",
        "हम नकद, यूपीआई और कार्ड स्वीकार करते हैं।",
    ),
    (
        "emergency",
        "What should I do in an emergency?",
        "We are not an emergency service. In an emergency, call 112 or go to the nearest hospital right away.",
        "इमरजेंसी में क्या करें?",
        "हम इमरजेंसी सेवा नहीं हैं। इमरजेंसी में तुरंत एक सौ बारह पर कॉल करें या नज़दीकी अस्पताल जाएँ।",
    ),
]

# weekday: Monday=0 ... Sunday=6. Each block is (start "HH:MM", end "HH:MM").
MON_SAT = range(0, 6)
DOCTORS = [
    {
        "id": 1,
        "name": "Dr. Meera Sharma",
        "name_hi": "डॉ. मीरा शर्मा",
        "specialty": "General Physician",
        "specialty_hi": "जनरल फिजिशियन",
        "fee": 500,
        "languages": "Hindi, English",
        "schedule": {d: [("10:00", "13:00"), ("17:00", "20:00")] for d in MON_SAT},
    },
    {
        "id": 2,
        "name": "Dr. Rahul Verma",
        "name_hi": "डॉ. राहुल वर्मा",
        "specialty": "Pediatrician",
        "specialty_hi": "बाल रोग विशेषज्ञ",
        "fee": 600,
        "languages": "Hindi, English",
        "schedule": {0: [("10:00", "14:00")], 2: [("10:00", "14:00")], 4: [("10:00", "14:00")], 5: [("10:00", "13:00")]},
    },
    {
        "id": 3,
        "name": "Dr. Anjali Gupta",
        "name_hi": "डॉ. अंजलि गुप्ता",
        "specialty": "Dermatologist",
        "specialty_hi": "त्वचा रोग विशेषज्ञ",
        "fee": 700,
        "languages": "Hindi, English",
        "schedule": {1: [("16:00", "20:00")], 3: [("16:00", "20:00")], 5: [("16:00", "20:00")]},
    },
    {
        "id": 4,
        "name": "Dr. Imran Khan",
        "name_hi": "डॉ. इमरान खान",
        "specialty": "Dentist",
        "specialty_hi": "दंत चिकित्सक",
        "fee": 400,
        "languages": "Hindi, English, Urdu",
        "schedule": {d: [("11:00", "14:00"), ("16:00", "19:00")] for d in MON_SAT},
    },
]

# Obviously fake people, used only to make the demo calendar look busy
FAKE_PATIENTS = [
    ("Rohan Mehta", "9000000001"),
    ("Sana Ali", "9000000002"),
    ("Vikram Singh", "9000000003"),
    ("Neha Joshi", "9000000004"),
    ("Arjun Nair", "9000000005"),
    ("Pooja Yadav", "9000000006"),
]


def now_ist_naive() -> dt.datetime:
    return dt.datetime.now(IST).replace(tzinfo=None)


def _slot_times(day: dt.date, start: str, end: str):
    """Yield (start, end) datetimes for every slot inside one block."""
    h, m = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    cursor = dt.datetime.combine(day, dt.time(h, m))
    limit = dt.datetime.combine(day, dt.time(eh, em))
    step = dt.timedelta(minutes=SLOT_MINUTES)
    while cursor + step <= limit:
        yield cursor, cursor + step
        cursor += step


def _remove_old_database(path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


def build_db(
    path: str = DEFAULT_DB_PATH,
    today: dt.date | None = None,
    with_demo_bookings: bool = True,
) -> dict:
    """Delete the old database and create a fresh one. Returns simple counts."""
    today = today or now_ist_naive().date()
    _remove_old_database(path)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)

    conn.execute(
        "INSERT INTO clinic (id, name, name_hi, address, address_hi, phone, hours, hours_hi) "
        "VALUES (1, :name, :name_hi, :address, :address_hi, :phone, :hours, :hours_hi)",
        CLINIC,
    )
    conn.executemany(
        "INSERT INTO faqs (topic, question_en, answer_en, question_hi, answer_hi) VALUES (?, ?, ?, ?, ?)",
        FAQS,
    )

    for doc in DOCTORS:
        conn.execute(
            "INSERT INTO doctors (id, name, name_hi, specialty, specialty_hi, fee, languages) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc["id"], doc["name"], doc["name_hi"], doc["specialty"], doc["specialty_hi"], doc["fee"], doc["languages"]),
        )
        for offset in range(BOOKING_WINDOW_DAYS + 1):
            day = today + dt.timedelta(days=offset)
            for block_start, block_end in doc["schedule"].get(day.weekday(), []):
                for start, end in _slot_times(day, block_start, block_end):
                    conn.execute(
                        "INSERT INTO slots (doctor_id, start_time, end_time) VALUES (?, ?, ?)",
                        (doc["id"], start.strftime(TIME_FORMAT), end.strftime(TIME_FORMAT)),
                    )

    booked = 0
    if with_demo_bookings:
        rng = random.Random(42)  # fixed seed: the same "busy" slots every time
        now_text = now_ist_naive().isoformat(timespec="seconds")
        first_day = (today + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT id, doctor_id FROM slots WHERE start_time >= ? ORDER BY id", (first_day,)
        ).fetchall()
        for slot_id, doctor_id in rows:
            if rng.random() < 0.25:
                name, phone = rng.choice(FAKE_PATIENTS)
                conn.execute("UPDATE slots SET status = 'booked' WHERE id = ?", (slot_id,))
                conn.execute(
                    "INSERT INTO appointments (patient_name, patient_phone, doctor_id, slot_id, reason, "
                    "language, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'hi', 'booked', ?, ?)",
                    (name, phone, doctor_id, slot_id, "demo data", now_text, now_text),
                )
                booked += 1

    conn.commit()
    counts = {
        "doctors": conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0],
        "slots": conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0],
        "demo_bookings": booked,
    }
    conn.close()
    return counts


if __name__ == "__main__":
    db_path = os.getenv("CLINIC_DB_PATH", DEFAULT_DB_PATH)
    try:
        result = build_db(db_path)
    except PermissionError:
        print("Could not replace the old database. Stop the API (uvicorn) and run this again.")
        sys.exit(1)
    print(f"{db_path} created with fake data: {result}")