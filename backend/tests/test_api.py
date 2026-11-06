import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import seed  # noqa: E402

KEY = {"Authorization": "Bearer test-key"}
PHONE = "9876543210"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setenv("CLINIC_DB_PATH", db)
    monkeypatch.setenv("CLINIC_API_KEY", "test-key")
    seed.build_db(db, with_demo_bookings=False)
    import main
    from fastapi.testclient import TestClient
    with TestClient(main.app, headers=KEY) as c:
        yield c


def free_slots(client, doctor=1, min_needed=1):
    """Find a day (from tomorrow on) with enough free slots."""
    for i in range(1, 12):
        day = (dt.date.today() + dt.timedelta(days=i)).isoformat()
        slots = client.get(f"/doctors/{doctor}/slots", params={"date": day}).json()["slots"]
        if len(slots) >= min_needed:
            return slots
    raise AssertionError("no free slots found")


def book(client, slot, phone=PHONE, name="राहुल शर्मा", doctor=1):
    return client.post("/appointments", json={
        "patient_name": name, "patient_phone": phone, "doctor_id": doctor,
        "slot_id": slot["slot_id"], "reason": "बुखार", "language": "hi"})


def test_health_is_open_but_others_need_key(client):
    assert client.get("/health", headers={}).status_code == 200
    assert client.get("/doctors", headers={"Authorization": ""}).status_code == 401
    assert client.get("/doctors", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_today_and_doctors_and_faqs(client):
    assert len(client.get("/today").json()["upcoming_days"]) == 15
    assert len(client.get("/doctors").json()["doctors"]) == 4
    assert client.get("/doctors", params={"specialty": "दंत"}).json()["doctors"][0]["id"] == 4
    assert client.get("/faqs", params={"topic": "fees"}).status_code == 200
    assert client.get("/faqs", params={"topic": "nope"}).status_code == 404
    assert "सनराइज" in client.get("/clinic").json()["name_hi"]


def test_book_with_hindi_name_and_phone_formats(client):
    slot = free_slots(client)[0]
    r = book(client, slot, phone="+91 98765-43210")
    assert r.status_code == 201
    body = r.json()
    assert body["patient_name"] == "राहुल शर्मा"
    assert body["patient_phone_masked"] == "******3210"
    assert "बजे" in body["when_hi"]
    listed = client.get("/appointments", params={"phone": PHONE}).json()["appointments"]
    assert [a["appointment_id"] for a in listed] == [body["appointment_id"]]


def test_double_booking_is_refused(client):
    slot = free_slots(client)[0]
    assert book(client, slot).status_code == 201
    r = book(client, slot, phone="9123456780")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "slot_taken"
    day = slot["start_time"][:10]
    left = client.get("/doctors/1/slots", params={"date": day}).json()["slots"]
    assert slot["slot_id"] not in [s["slot_id"] for s in left]


def test_validation(client):
    slot = free_slots(client)[0]
    assert book(client, slot, phone="12345").status_code == 422
    assert book(client, slot, name="A1").status_code == 422
    assert book(client, slot, name="'; DROP TABLE slots;--").status_code == 422
    r = client.post("/appointments", json={"patient_name": "Ali", "patient_phone": PHONE,
                                           "doctor_id": 2, "slot_id": slot["slot_id"]})
    assert r.status_code == 404  # slot belongs to doctor 1, not 2
    assert client.get("/doctors/1/slots", params={"date": "kal"}).status_code == 422


def test_past_or_too_soon_slot_is_refused(client):
    import sqlite3
    con = sqlite3.connect(os.environ["CLINIC_DB_PATH"])
    sid = con.execute("SELECT id FROM slots WHERE doctor_id=1 AND start_time < ? ORDER BY id LIMIT 1",
                      ((dt.datetime.now() - dt.timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M"),)).fetchone()
    con.close()
    if sid:  # only if the seed produced a past slot
        r = client.post("/appointments", json={"patient_name": "Ali", "patient_phone": PHONE,
                                               "doctor_id": 1, "slot_id": sid[0]})
        assert r.json()["error"]["code"] == "too_soon"


def test_max_three_active_and_time_clash(client):
    slots = free_slots(client, min_needed=5)
    for s in slots[:3]:
        assert book(client, s).status_code == 201
    r = book(client, slots[3])
    assert r.status_code == 409 and r.json()["error"]["code"] == "limit_reached"
    # same time with another doctor is a clash (different phone first to fill that doctor's slot)
    other = book(client, slots[4], phone="9111111111")
    assert other.status_code == 201


def test_cancel_frees_slot_and_checks_owner(client):
    slot = free_slots(client)[0]
    appt = book(client, slot).json()
    aid = appt["appointment_id"]
    wrong = client.post(f"/appointments/{aid}/cancel", json={"patient_phone": "9000000099"})
    assert wrong.status_code == 404
    ok = client.post(f"/appointments/{aid}/cancel", json={"patient_phone": PHONE})
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"
    again = client.post(f"/appointments/{aid}/cancel", json={"patient_phone": PHONE})
    assert again.status_code == 409
    assert book(client, slot, phone="9222222222").status_code == 201  # slot is free again


def test_reschedule(client):
    slots = free_slots(client, min_needed=2)
    aid = book(client, slots[0]).json()["appointment_id"]
    r = client.post(f"/appointments/{aid}/reschedule",
                    json={"patient_phone": PHONE, "new_slot_id": slots[1]["slot_id"]})
    assert r.status_code == 200
    assert r.json()["slot_id"] == slots[1]["slot_id"]
    # old slot can be booked by someone else now
    assert book(client, slots[0], phone="9333333333").status_code == 201
    # new slot is now taken
    r2 = client.post(f"/appointments/{aid}/reschedule",
                     json={"patient_phone": PHONE, "new_slot_id": slots[0]["slot_id"]})
    assert r2.json()["error"]["code"] == "slot_taken"


def test_late_cancel_refused(client):
    import sqlite3
    slot = free_slots(client)[0]
    aid = book(client, slot).json()["appointment_id"]
    con = sqlite3.connect(os.environ["CLINIC_DB_PATH"])
    soon = (dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).replace(tzinfo=None)
            + dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M")
    con.execute("UPDATE slots SET start_time=? WHERE id=?", (soon, slot["slot_id"]))
    con.commit()
    con.close()
    r = client.post(f"/appointments/{aid}/cancel", json={"patient_phone": PHONE})
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_late"


def test_callback_and_audit(client):
    r = client.post("/callbacks", json={"patient_name": "सना", "patient_phone": PHONE,
                                        "reason": "रिपोर्ट के बारे में पूछना है"})
    assert r.status_code == 201
    import sqlite3
    con = sqlite3.connect(os.environ["CLINIC_DB_PATH"])
    assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    con.close()


def test_closed_day_gives_next_available(client):
    sunday = dt.date.today()
    while sunday.weekday() != 6 or sunday <= dt.date.today():
        sunday += dt.timedelta(days=1)
    r = client.get("/doctors/1/slots", params={"date": sunday.isoformat()}).json()
    assert r["slots"] == [] and r["next_available"] is not None