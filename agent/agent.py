from dotenv import load_dotenv
from livekit import agents
import asyncio
import os
import aiohttp
import logging
import time
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, function_tool, inference
from livekit.plugins import silero

load_dotenv()
logger = logging.getLogger("clinic-agent")

CLINIC_API = os.getenv("CLINIC_API_URL", "http://localhost:8000")
CLINIC_API_KEY = os.getenv("CLINIC_API_KEY", "dev-clinic-key")
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
                "You are the phone receptionist of Sir Ganga Ram City Hospital in Delhi. "
                "Speak in simple, polite Hindi written in Devanagari script. "
                "LANGUAGE RULE: reply in only ONE language per reply, the language of the caller's latest message. "
                "If the caller speaks Hindi, even with a few English words, reply fully in Hindi, written only in "
                "Devanagari, and write English words in Devanagari too (डॉक्टर, अपॉइंटमेंट, ओके). "
                "If the caller speaks English, reply fully in English with no Hindi words. "
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
                "Before booking you only need the patient's name. The phone number comes from the web page "
                "automatically: never ask for it, unless request_booking says it is missing. "
                "As soon as you have the doctor, slot and patient name, call request_booking immediately, "
                "which does NOT book yet. Do not ask the confirmation question before calling it. "
                "The tool result tells you what to ask: ask that ONE yes/no question, keep it under 20 words, "
                "and STOP and wait. Only if the caller clearly says yes, call confirm_pending_action. "
                "If they say no or are unsure, call discard_pending_action. "
                "Never book without that yes. After a successful booking, say the doctor, day and time once and thank them. "
                "If a tool says the slot was taken, apologise and offer another time. "
            )
        )
        self._room = room
        self._offered = {}     # slots offered in this call: slot_id -> details
        self._user_turns = 0   # how many times the caller has finished speaking
        self._pending = None   # a booking that is waiting for the caller's yes

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        self._user_turns += 1

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
        if len(name) < 2:
            return "Ask the caller for the patient's name."

        self._pending = {
            "slot_id": int(slot_id), "doctor_id": slot["doctor_id"], "name": name,
            "phone": phone, "reason": reason.strip()[:200],
            "turn": self._user_turns, "at": time.monotonic(),
        }
        logger.info("booking_requested slot_id=%s", slot_id)
        return (
            "Nothing is booked yet. Ask the caller ONE yes/no question that repeats: "
            f"{slot['doctor']}, {slot['weekday']} {slot['date']}, {slot['time']}, "
            f"patient name {name}, phone number ending {' '.join(phone[-4:])}. Then wait for the answer."
        )

    @function_tool
    async def confirm_pending_action(self, context: RunContext) -> str:
        """Book the appointment the caller has just confirmed.

        Call this ONLY when the caller's latest message is a clear yes. Never call it
        in the same turn as request_booking.
        """
        pending = self._pending
        if pending is None:
            return "There is nothing waiting for confirmation."
        if time.monotonic() - pending["at"] > PENDING_TTL_SECONDS:
            self._pending = None
            return "That request expired. Ask the caller what they want to do."
        if self._user_turns <= pending["turn"]:
            logger.warning("booking_blocked reason=no_user_answer")
            return "The caller has not answered yet. Ask the confirmation question and wait."

        self._pending = None  # clear first, so it can never run twice
        try:
            status, body = await call_api("POST", "/appointments", json={
                "patient_name": pending["name"],
                "patient_phone": pending["phone"],
                "doctor_id": pending["doctor_id"],
                "slot_id": pending["slot_id"],
                "reason": pending["reason"] or None,
                "language": "hi",
            })
        except Exception:
            logger.exception("booking failed")
            return "The clinic system is not reachable, so nothing was booked. Apologise."
        logger.info("booking_done http_status=%s", status)
        if status == 201:
            return (
                f"Booked: appointment_id {body['appointment_id']}, {speakable(body['doctor_name_hi'])}, "
                f"{body['when_hi']}. Tell the caller this once and thank them."
            )
        return f"Nothing was booked. Reason: {body['error']['message']} Explain briefly and offer another option."

    @function_tool
    async def discard_pending_action(self, context: RunContext) -> str:
        """Drop the waiting booking when the caller says no or changes their mind."""
        self._pending = None
        return "Okay, nothing was booked."


server = AgentServer()


def prewarm(proc: agents.JobProcess):
    """Runs once when the agent starts, so each call does not have to load the voice-detection model."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="hi"),
        llm="openai/gpt-4.1-mini",
        tts=inference.TTS(model="cartesia/sonic-3", voice="1259b7e3-cb8a-43df-9446-30971a46b8b0", language="hi"),
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
        if getattr(ev.item, "role", None) == "assistant":
            logger.info("agent_said: %s", ev.item.text_content)

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

    await session.start(room=ctx.room, agent=Receptionist(room=ctx.room))
    await session.generate_reply(instructions="Greet the caller in Hindi and ask how you can help.")


if __name__ == "__main__":
    agents.cli.run_app(server)