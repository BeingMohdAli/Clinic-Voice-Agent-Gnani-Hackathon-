from dotenv import load_dotenv
from livekit import agents
import asyncio
import os
import aiohttp
import logging
import time
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, function_tool
from livekit.plugins import gnani, silero

load_dotenv()
logger = logging.getLogger("clinic-agent")

CLINIC_API = os.getenv("CLINIC_API_URL", "http://localhost:8000")
CLINIC_API_KEY = os.getenv("CLINIC_API_KEY", "dev-clinic-key")
if not os.getenv("GNANI_API_KEY"):
    logger.warning("GNANI_API_KEY is not set: Gnani speech models will fail. Add it to agent/.env")

PENDING_TTL_SECONDS = 180  # a booking waiting for "yes" expires after this many seconds


async def call_api(method: str, path: str, **kwargs):
    """Call the clinic backend. Returns (status_code, json_body)."""
    timeout = aiohttp.ClientTimeout(total=6)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.request(
            method,
            f"{CLINIC_API}{path}",
            headers={"Authorization": f"Bearer {CLINIC_API_KEY}"},
            **kwargs,
        ) as resp:
            return resp.status, await resp.json()


def speakable(text: str) -> str:
    """Spell out short forms that the voice reads badly."""
    return text.replace("डॉ.", "डॉक्टर").replace("Dr.", "Doctor")


def clean_phone(raw: str) -> str:
    """Keep a valid 10-digit Indian mobile number, or return ''."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else ""


class Receptionist(Agent):
    def __init__(self, room):
        super().__init__(
            instructions=(
                "You are the phone receptionist of Aarogya Demo Clinic, a demo clinic in Delhi. "
                "Speak in simple, polite Hindi written in Devanagari script. "
                "LANGUAGE RULE: reply in only ONE language per reply, the language of the caller's latest message. "
                "If the caller speaks Hindi, even with a few English words, reply fully in Hindi, written only in "
                "Devanagari, and write English words in Devanagari too (डॉक्टर, अपॉइंटमेंट, ओके). "
                "If the caller speaks English, reply fully in English with no Hindi words. "
                "The speech-to-text often writes English words in Devanagari, like 'डू यू हैव ए कार्डियोलॉजिस्ट'. "
                "If a sentence is English sounds written in Devanagari, treat it as English and reply in English. "
                "Never mix the two languages or scripts in one reply. "
                "You are a man: use masculine forms, like 'मैं बता सकता हूँ'. "
                "Keep every reply to one or two short sentences, because it is spoken aloud. "
                "Ask only one question at a time. "
                "You are not a doctor: never give medical advice. "
                "EMERGENCY RULE: if the caller mentions chest pain, trouble breathing, heavy bleeding, "
                "fainting or unconsciousness, a seizure, signs of a stroke (face drooping, slurred speech, "
                "weakness on one side), a serious injury, poisoning, or thoughts of suicide, do not ask "
                "questions and do not offer an appointment. Say firmly, in one or two sentences: "
                "'यह इमरजेंसी हो सकती है। कृपया अभी 112 पर कॉल करें या नज़दीकी अस्पताल की इमरजेंसी में जाइए।' "
                "For thoughts of suicide, also say they can call Tele-MANAS on 14416. "
                "Only go back to booking if the caller clearly says it is not an emergency. "
                "Never state doctors, fees, timings or the address from your own knowledge: "
                "always use the tools, and if a tool has no answer, say you do not know. "
                "Always say the whole word डॉक्टर or Doctor, never the short forms. "
                "Never say that an appointment is booked, cancelled or changed unless a tool result in this "
                "call says so. If you have not called the tool, you have not done it. "
                "BOOKING FLOW: call get_today first so you know the real date. "
                "Use list_doctors to find the doctor, then get_available_slots for a date, and offer only two "
                "or three times that a tool returned. "
                "Before booking you need the patient's name. ALWAYS ask for it yourself with a short question like "
                "'आपका नाम क्या है?' once the doctor and time are chosen. Never guess a name, never use a "
                "placeholder like 'patient' or 'caller', and never call request_booking until the caller has "
                "told you their name in this call. The phone number comes from the web page "
                "automatically: never ask for it, unless request_booking says it is missing. "
                "As soon as you have the doctor, slot and patient name, call request_booking immediately, "
                "which does NOT book yet. Do not ask the confirmation question before calling it. "
                "The tool result tells you what to ask: ask that ONE confirmation question, keep it under 20 words, "
                "and end it naturally, for example 'क्या मैं बुक कर दूँ?' or 'Shall I book it?'. "
                "Never say the words 'yes', 'no', 'हाँ' or 'नहीं' as options and never write them with a slash, "
                "because the question is spoken aloud. "
                "and STOP and wait. Only if the caller clearly says yes, call confirm_pending_action. "
                "If they say no or are unsure, call discard_pending_action. "
                "Never book, cancel or move anything without that yes. After a successful booking, say the doctor, day and time once and thank them. "
                "If a tool says the slot was taken, apologise and offer another time. "
                "CALLBACK: if you cannot help (billing, reports, complaints, a medical question, or a change that is "
                "too close to the appointment time), offer a callback from staff. If the caller agrees, ask only for "
                "their name and a short reason, then call request_callback. Never promise a time for the call. "
                "CANCEL AND RESCHEDULE: first call get_my_appointments to see the caller's appointments "
                "(never ask for the phone number; it comes from the web page). If there is more than one, "
                "ask which one by its TIME (never ask which doctor if they are all with the same doctor). To cancel, call request_cancel. To move one, use get_available_slots for the "
                "SAME doctor, offer two or three times, then call request_reschedule. These tools do NOT change "
                "anything yet: ask the ONE confirmation question the tool tells you (never read out 'yes/no' or 'हाँ/नहीं'), STOP and wait, and only after a clear "
                "yes call confirm_pending_action. If a change is refused because it is too close to the "
                "appointment time, tell the caller politely that it cannot be changed this late. "
            )
        )
        self._room = room
        self._offered = {}     # slots offered in this call: slot_id -> details
        self._user_turns = 0   # how many times the caller has finished speaking
        self._pending = None   # a change (book, cancel or move) waiting for the caller's yes
        self._my_appts = {}    # appointments shown to this caller: appointment_id -> details

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        self._user_turns += 1

    def note_agent_spoke(self) -> None:
        """Called when the agent has said something. The first thing said after a request_... tool
        is the confirmation question; only an answer AFTER that question counts as a yes."""
        if self._pending is not None and not self._pending.get("asked"):
            self._pending["asked"] = True
            self._pending["asked_turn"] = self._user_turns

    def _caller_phone(self) -> str:
        """The number typed on the web page, sent as a participant attribute."""
        for p in self._room.remote_participants.values():
            phone = (p.attributes or {}).get("phone", "")
            if phone:
                return phone
        return ""

    @function_tool
    async def list_doctors(self, context: RunContext, specialty: str = "") -> str:
        """List the hospital's doctors, with their fees.

        Use this whenever the caller asks which doctors or specialties are available.

        Args:
            specialty: Optional, for example "dentist" or "pediatrician". Leave empty for all doctors.
        """
        logger.info("tool list_doctors specialty=%r", specialty)
        try:
            status, body = await call_api("GET", "/doctors", params={"specialty": specialty} if specialty else None)
        except Exception:
            logger.exception("list_doctors failed")
            return "The clinic system is not reachable. Apologise and ask the caller to try again."
        if status != 200:
            return "The clinic system had a problem. Apologise and ask the caller to try again."
        if not body["doctors"]:
            return "There is no doctor with that specialty."
        return " ".join(
            f"doctor_id {d['id']}: {speakable(d['name_hi'])} ({speakable(d['name'])}), "
            f"{d['specialty_hi']}, fee {d['fee']} rupees."
            for d in body["doctors"]
        )

    @function_tool
    async def get_clinic_info(self, context: RunContext, topic: str) -> str:
        """Answer a general question about the hospital.

        Args:
            topic: One of hours, address, fees, what_to_bring, cancellation, payment, emergency.
        """
        logger.info("tool get_clinic_info topic=%r", topic)
        try:
            status, body = await call_api("GET", "/faqs", params={"topic": topic})
        except Exception:
            logger.exception("get_clinic_info failed")
            return "The clinic system is not reachable. Apologise and ask the caller to try again."
        if status != 200:
            return "There is no information on that topic. Do not guess."
        return body["faqs"][0]["answer_hi"]

    @function_tool
    async def get_today(self, context: RunContext) -> str:
        """Get today's date, the current time, and the dates of the next two weeks.

        Call this before talking about any date, so you never guess it.
        """
        try:
            status, body = await call_api("GET", "/today")
        except Exception:
            logger.exception("get_today failed")
            return "The clinic system is not reachable. Apologise and ask the caller to try again."
        if status != 200:
            return "The clinic system had a problem. Apologise and ask the caller to try again."
        days = "; ".join(
            f"{d['date']} {d['weekday']}/{d['weekday_hi']}" + (f" ({d['label']})" if d["label"] else "")
            for d in body["upcoming_days"]
        )
        return f"Now: {body['now_hi']}. Next days: {days}."

    @function_tool
    async def get_available_slots(self, context: RunContext, doctor_id: int, date: str) -> str:
        """Get the free appointment times of one doctor on one date.

        Args:
            doctor_id: The doctor's id from list_doctors.
            date: The date as YYYY-MM-DD, taken from get_today.
        """
        logger.info("tool get_available_slots doctor_id=%s date=%s", doctor_id, date)
        try:
            status, body = await call_api("GET", f"/doctors/{int(doctor_id)}/slots", params={"date": date})
        except Exception:
            logger.exception("get_available_slots failed")
            return "The clinic system is not reachable. Apologise and ask the caller to try again."
        if status != 200:
            return f"Could not get slots: {body['error']['message']}"
        slots = body["slots"]
        if not slots:
            text = f"{speakable(body['doctor_name_hi'])} has no free slots on {body['weekday_hi']} {date}."
            if body["next_available"]:
                text += f" The next free time is {body['next_available']['when_hi']}."
            return text

        slots = slots[:: max(1, len(slots) // 6)][:6]  # spread over the day, at most 6
        for s in slots:
            self._offered[s["slot_id"]] = {
                "doctor_id": body["doctor_id"],
                "doctor": speakable(body["doctor_name_hi"]),
                "date": body["date"],
                "weekday": body["weekday_hi"],
                "time": s["time_hi"],
            }
        listing = "; ".join(f"slot_id {s['slot_id']}: {s['time_hi']}" for s in slots)
        return (
            f"{speakable(body['doctor_name_hi'])}, {body['weekday_hi']} {body['date']}. "
            f"Free times: {listing}. Offer two or three of these."
        )

    @function_tool
    async def request_booking(
        self, context: RunContext, slot_id: int, patient_name: str, patient_phone: str = "", reason: str = ""
    ) -> str:
        """Start booking an appointment. This does NOT book it yet.

        Args:
            slot_id: A slot_id returned by get_available_slots in this call.
            patient_name: The patient's name as the caller said it.
            patient_phone: Only if the caller said it aloud: their 10-digit mobile number. Leave empty otherwise.
            reason: Optional short reason for the visit.
        """
        slot = self._offered.get(int(slot_id))
        if not slot:
            return "That slot was not offered. Call get_available_slots again and use one of its slot_ids."
        phone = self._caller_phone() or clean_phone(patient_phone)
        logger.info("caller_phone_from_page=%s", bool(self._caller_phone()))
        if not phone:
            return "The caller's phone number is missing. Ask the caller to say their 10-digit mobile number."
        name = " ".join(patient_name.split())
        if len(name) < 2 or name.lower() in {"आप", "जी", "मरीज़", "मरीज", "patient", "caller", "user", "unknown"}:
            return "That is not a real name. Ask the caller: 'आपका नाम क्या है?' and use exactly what they say."

        self._pending = {
            "action": "book", "slot_id": int(slot_id), "doctor_id": slot["doctor_id"], "name": name,
            "phone": phone, "reason": reason.strip()[:200],
            "turn": self._user_turns, "at": time.monotonic(),
        }
        logger.info("booking_requested slot_id=%s", slot_id)
        return (
            "Nothing is booked yet. Ask the caller ONE short confirmation question (do not say 'yes/no' or 'हाँ/नहीं') that repeats: "
            f"{slot['doctor']}, {slot['weekday']} {slot['date']}, {slot['time']}, "
            f"patient name {name}, phone number ending {' '.join(phone[-4:])}. Then wait for the answer."
        )

    @function_tool
    async def get_my_appointments(self, context: RunContext) -> str:
        """List the caller's upcoming appointments. Use it before cancelling or moving one,
        or when the caller asks what appointments they have."""
        phone = self._caller_phone()
        if not phone:
            return "The caller's phone number is missing. Ask the caller to say their 10-digit mobile number."
        logger.info("tool get_my_appointments")
        try:
            status, body = await call_api("GET", "/appointments", params={"phone": phone})
        except Exception:
            logger.exception("get_my_appointments failed")
            return "The clinic system is not reachable. Apologise and ask the caller to try again."
        if status != 200:
            return "The clinic system had a problem. Apologise and ask the caller to try again."
        if not body["appointments"]:
            return "This caller has no upcoming appointments."
        self._my_appts = {}
        lines = []
        for a in body["appointments"]:
            self._my_appts[a["appointment_id"]] = {"doctor_id": a["doctor_id"], "phone": phone,
                                                    "text": f"{speakable(a['doctor_name_hi'])}, {a['when_hi']}"}
            lines.append(f"appointment_id {a['appointment_id']}: {speakable(a['doctor_name_hi'])}, {a['when_hi']}.")
        return " ".join(lines)

    @function_tool
    async def request_cancel(self, context: RunContext, appointment_id: int) -> str:
        """Start cancelling an appointment. This does NOT cancel it yet.

        Args:
            appointment_id: An appointment_id returned by get_my_appointments in this call.
        """
        appt = self._my_appts.get(int(appointment_id))
        if not appt:
            return "That appointment was not listed. Call get_my_appointments first and use one of its ids."
        self._pending = {"action": "cancel", "appointment_id": int(appointment_id), "phone": appt["phone"],
                         "turn": self._user_turns, "at": time.monotonic()}
        logger.info("cancel_requested appointment_id=%s", appointment_id)
        return (
            "Nothing is cancelled yet. Ask the caller ONE short confirmation question (do not say 'yes/no' or 'हाँ/नहीं'): do they want to cancel "
            f"the appointment with {appt['text']}? Then wait for the answer."
        )

    @function_tool
    async def request_reschedule(self, context: RunContext, appointment_id: int, new_slot_id: int) -> str:
        """Start moving an appointment to another time with the SAME doctor. This does NOT move it yet.

        Args:
            appointment_id: An appointment_id returned by get_my_appointments in this call.
            new_slot_id: A slot_id returned by get_available_slots for the same doctor.
        """
        appt = self._my_appts.get(int(appointment_id))
        if not appt:
            return "That appointment was not listed. Call get_my_appointments first and use one of its ids."
        slot = self._offered.get(int(new_slot_id))
        if not slot:
            return "That slot was not offered. Call get_available_slots again and use one of its slot_ids."
        if slot["doctor_id"] != appt["doctor_id"]:
            return "The new time must be with the same doctor. Call get_available_slots for that doctor."
        self._pending = {"action": "reschedule", "appointment_id": int(appointment_id), "phone": appt["phone"],
                         "new_slot_id": int(new_slot_id), "turn": self._user_turns, "at": time.monotonic()}
        logger.info("reschedule_requested appointment_id=%s new_slot_id=%s", appointment_id, new_slot_id)
        return (
            "Nothing is moved yet. Ask the caller ONE short confirmation question (do not say 'yes/no' or 'हाँ/नहीं'): move the appointment with "
            f"{appt['text']} to {slot['weekday']} {slot['date']}, {slot['time']}? Then wait for the answer."
        )

    @function_tool
    async def request_callback(
        self, context: RunContext, patient_name: str, reason: str, preferred_time: str = ""
    ) -> str:
        """Ask clinic staff to call the caller back. Use it for anything you cannot handle:
        billing, reports, complaints, medical questions, or changes too close to the appointment.

        Args:
            patient_name: The caller's name.
            reason: A short reason for the callback, in the caller's words.
            preferred_time: Optional, when the caller would like the call.
        """
        phone = self._caller_phone()
        if not phone:
            return "The caller's phone number is missing. Ask the caller to say their 10-digit mobile number."
        logger.info("tool request_callback")
        try:
            status, body = await call_api("POST", "/callbacks", json={
                "patient_name": " ".join(patient_name.split()),
                "patient_phone": phone,
                "reason": reason.strip()[:300] or "callback requested",
                "preferred_time": preferred_time.strip()[:100] or None,
            })
        except Exception:
            logger.exception("request_callback failed")
            return "The clinic system is not reachable, so the callback was not saved. Apologise."
        logger.info("callback_done http_status=%s", status)
        if status == 201:
            return "The callback request is saved. Tell the caller that staff will call them back."
        return f"The callback was not saved: {body['error']['message']} Apologise and explain briefly."

    @function_tool
    async def confirm_pending_action(self, context: RunContext) -> str:
        """Carry out the booking, cancellation or move that the caller has just confirmed.

        Call this ONLY when the caller's latest message is a clear yes. Never call it
        in the same turn as the request_... tool.
        """
        pending = self._pending
        if pending is None:
            return "There is nothing waiting for confirmation."
        if time.monotonic() - pending["at"] > PENDING_TTL_SECONDS:
            self._pending = None
            return "That request expired. Ask the caller what they want to do."
        if not pending.get("asked") or self._user_turns <= pending["asked_turn"]:
            logger.warning("action_blocked reason=no_user_answer")
            return "The caller has not answered yet. Ask the confirmation question and wait."

        self._pending = None  # clear first, so it can never run twice
        action = pending["action"]
        try:
            if action == "book":
                status, body = await call_api("POST", "/appointments", json={
                    "patient_name": pending["name"],
                    "patient_phone": pending["phone"],
                    "doctor_id": pending["doctor_id"],
                    "slot_id": pending["slot_id"],
                    "reason": pending["reason"] or None,
                    "language": "hi",
                })
                ok_status = 201
            elif action == "cancel":
                status, body = await call_api(
                    "POST", f"/appointments/{pending['appointment_id']}/cancel",
                    json={"patient_phone": pending["phone"]})
                ok_status = 200
            else:
                status, body = await call_api(
                    "POST", f"/appointments/{pending['appointment_id']}/reschedule",
                    json={"patient_phone": pending["phone"], "new_slot_id": pending["new_slot_id"]})
                ok_status = 200
        except Exception:
            logger.exception("%s failed", action)
            return "The clinic system is not reachable, so nothing was changed. Apologise."
        logger.info("action_done action=%s http_status=%s", action, status)
        if status == ok_status:
            if action == "cancel":
                return "Cancelled. Tell the caller the appointment is cancelled, once, and thank them."
            verb = "Booked" if action == "book" else "Moved"
            return (
                f"{verb}: appointment_id {body['appointment_id']}, {speakable(body['doctor_name_hi'])}, "
                f"{body['when_hi']}. Tell the caller this once and thank them."
            )
        return f"Nothing was changed. Reason: {body['error']['message']} Explain briefly and offer another option."

    @function_tool
    async def discard_pending_action(self, context: RunContext) -> str:
        """Drop the waiting change when the caller says no or changes their mind."""
        self._pending = None
        return "Okay, nothing was changed."


server = AgentServer()


def prewarm(proc: agents.JobProcess):
    """Runs once when the agent starts, so each call does not have to load the voice-detection model."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    agent = Receptionist(room=ctx.room)
    session = AgentSession(
        # Gnani Prisma (speech-to-text); format="transcribe" writes spoken numbers as digits
        stt=gnani.STT(language="hi-IN", format="transcribe"),
        llm="openai/gpt-4.1-mini",
        # Gnani Timbre v2.5 (text-to-speech): a male Hindi voice
        tts=gnani.TTS(voice="Vikrant", model="timbre-v2.5", language="hi-IN", synthesize_method="websocket"),
        vad=ctx.proc.userdata["vad"],
        turn_handling={
            "turn_detection": MultilingualModel(),
            # Wait at least 0.3 s after the caller stops, and never more than 1.0 s.
            # The phone number is typed now, so we no longer need a long wait for digits.
            "endpointing": {"min_delay": 0.3, "max_delay": 1.0},
        },
        user_away_timeout=10,  # seconds of silence before the caller counts as "away"
    )

    @session.on("user_input_transcribed")
    def on_user_said(ev):
        if ev.is_final:
            logger.info("user_said: %s", ev.transcript)

    @session.on("conversation_item_added")
    def on_item_added(ev):
        if getattr(ev.item, "role", None) == "assistant" and ev.item.text_content:
            logger.info("agent_said: %s", ev.item.text_content)
            agent.note_agent_spoke()

    # If the caller goes quiet, check twice that they are still there, then say goodbye.
    presence_task = None

    async def check_presence():
        for _ in range(2):
            await session.generate_reply(
                instructions="The caller has been silent. In one short sentence, politely ask if they are still there."
            )
            await asyncio.sleep(8)
        await session.generate_reply(instructions="Say a short polite goodbye and that they can call again.")
        session.shutdown()

    @session.on("user_state_changed")
    def on_user_state(ev):
        nonlocal presence_task
        if ev.new_state == "away":
            presence_task = asyncio.create_task(check_presence())
        elif presence_task is not None:
            presence_task.cancel()  # the caller came back
            presence_task = None

    await session.start(room=ctx.room, agent=agent)
    await session.generate_reply(instructions="Greet the caller in Hindi and ask how you can help.")


if __name__ == "__main__":
    agents.cli.run_app(server)