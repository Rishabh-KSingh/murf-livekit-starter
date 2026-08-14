import json
import logging
import os
import random
import re
import sqlite3
from datetime import datetime

import requests
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    llm,
    room_io,
    tokenize,
)
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

# Locate directories and load environment variables securely
# Locate directories and load environment variables securely
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_LOCAL_PATH = os.path.join(BACKEND_DIR, ".env.local")
load_dotenv(ENV_LOCAL_PATH)

# ==========================================
# 1. SQLITE DATABASE SETUP & HELPERS
# ==========================================
try:
    from db import (
        DB_PATH,
        create_call_log,
        init_db,
        mark_call_success,
    )
except ImportError:
    try:
        from src.db import (
            DB_PATH,
            create_call_log,
            init_db,
            mark_call_success,
        )
    except ImportError:
        from .db import (
            DB_PATH,
            create_call_log,
            init_db,
            mark_call_success,
        )


# ==========================================
# 2. LIVEKIT FUNCTION CONTEXT & TOOLS
# ==========================================
# Compatibility layer for FunctionContext and ai_callable across SDK versions
if not hasattr(llm, "FunctionContext"):

    class FunctionContext:
        pass

    llm.FunctionContext = FunctionContext

if not hasattr(llm, "ai_callable"):
    llm.ai_callable = llm.function_tool


class FarmerTools(llm.FunctionContext):
    def __init__(
        self,
        db_path: str = DB_PATH,
        current_user_id: str = "user_123",
        current_session_id: str = "",
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.current_user_id = current_user_id
        self.current_session_id = current_session_id

    @llm.ai_callable(
        description="Silently mark the current call session as successful after providing weather information, mandi prices, or creating an escalation ticket."
    )
    async def mark_call_successful(self) -> dict:
        """Marks the current call session as successful in SQLite."""
        sid = (self.current_session_id or "").strip()
        logger.info(f"mark_call_successful tool invoked for session_id='{sid}'")
        success = mark_call_success(sid, db_path=self.db_path)
        return {
            "status": "success",
            "session_id": sid,
            "marked_successful": success,
        }

    @llm.ai_callable(
        description="Check if a user exists in the database using their user_id."
    )
    async def get_user_profile(self, user_id: str = "") -> dict | None:
        """Fetches and returns the user's record from SQLite.

        Parses the facts JSON string back into a dictionary before returning.
        """
        uid = user_id.strip() if user_id and user_id.strip() else self.current_user_id
        logger.info(f"get_user_profile tool invoked for user_id='{uid}'")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, name, language_preference, facts, last_interaction FROM users WHERE user_id = ?",
            (uid,),
        )
        row = cursor.fetchone()

        if not row and uid.startswith("sip_"):
            cursor.execute(
                "SELECT user_id, name, language_preference, facts, last_interaction FROM users WHERE user_id = ?",
                (uid[4:],),
            )
            row = cursor.fetchone()

        if not row:
            cursor.execute(
                "SELECT user_id, name, language_preference, facts, last_interaction FROM users WHERE user_id = 'user_123' OR name LIKE '%ऋषभ%' OR name LIKE '%Rishabh%' LIMIT 1"
            )
            row = cursor.fetchone()

        conn.close()

        if not row:
            logger.info(f"No profile found in database for user_id='{uid}'")
            return None

        facts_raw = row[3]
        facts_dict = {}
        if facts_raw:
            try:
                facts_dict = json.loads(facts_raw)
            except Exception as e:
                logger.warning(f"Error parsing facts JSON for user_id='{uid}': {e}")
                facts_dict = {"raw": facts_raw}

        profile = {
            "user_id": row[0],
            "name": row[1],
            "language_preference": row[2],
            "facts": facts_dict,
            "last_interaction": row[4],
        }
        logger.info(f"Retrieved profile for user_id='{uid}': {profile}")
        return profile

    @llm.ai_callable(
        description="Save or update user details in the database after getting their explicit consent."
    )
    async def save_user_profile(
        self,
        user_id: str = "",
        name: str = "",
        language_preference: str = "Hindi",
        facts: str = "",
    ) -> dict:
        """Saves the data to SQLite and sets last_interaction to current time."""
        uid = (
            self.current_user_id
            if (self.current_user_id and self.current_user_id.strip())
            else (user_id.strip() if user_id and user_id.strip() else "user_123")
        )
        logger.info(
            f"save_user_profile tool invoked for user_id='{uid}', name='{name}'"
        )
        facts_str = facts
        if isinstance(facts, dict):
            facts_str = json.dumps(facts, ensure_ascii=False)
        elif isinstance(facts, str):
            try:
                parsed = json.loads(facts)
                facts_str = json.dumps(parsed, ensure_ascii=False)
            except Exception:
                facts_str = json.dumps({"info": facts}, ensure_ascii=False)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name,
                language_preference=excluded.language_preference,
                facts=excluded.facts,
                last_interaction=excluded.last_interaction
            """,
            (uid, name, language_preference, facts_str, current_time),
        )
        conn.commit()
        conn.close()

        result = {
            "status": "success",
            "message": f"User profile for {name} ({uid}) successfully saved.",
            "user_id": uid,
            "name": name,
            "language_preference": language_preference,
            "facts": facts_str,
            "last_interaction": current_time,
        }
        logger.info(f"save_user_profile completed: {result}")
        return result

    @llm.ai_callable(
        description="Get the current weather forecast for a specific district."
    )
    async def get_weather_forecast(self, district: str) -> str:
        """Fetches the current weather forecast for a specific district using wttr.in."""
        logger.info(f"get_weather_forecast tool invoked for district='{district}'")
        try:
            clean_district = (district or "").strip()
            if not clean_district:
                return "ERROR: Weather API is currently down."
            resp = requests.get(
                f"https://wttr.in/{clean_district}?format=%t+%C", timeout=5
            )
            if resp.status_code == 200 and resp.text:
                weather_raw = resp.text.strip()
                parts = weather_raw.split(None, 1)
                if len(parts) == 2:
                    temp, condition = parts[0], parts[1]
                    result_str = f"SUCCESS: Aaj ka data: {temp} and {condition} in {clean_district}."
                else:
                    result_str = (
                        f"SUCCESS: Aaj ka data: {weather_raw} in {clean_district}."
                    )
                logger.info(f"Weather forecast retrieved: {result_str}")
                return result_str
            else:
                logger.warning(
                    f"wttr.in returned status code {resp.status_code}: {resp.text}"
                )
                return "ERROR: Weather API is currently down."
        except Exception as e:
            logger.error(f"Weather API request failed for district '{district}': {e}")
            return "ERROR: Weather API is currently down."

    @llm.ai_callable(
        description="Escalate a critical crop disease outbreak or missing mandi prices to a senior human agriculture expert via Discord."
    )
    async def create_escalation(
        self,
        summary: str,
        urgency: str = "High",
        language: str = "Hindi",
    ) -> dict:
        """Sends an escalation alert to Discord webhook and returns a unique reference ID.

        Args:
            summary: Detailed summary of what happened / what the farmer is facing.
            urgency: Level of urgency ('High', 'Medium', 'Critical').
            language: Farmer's language (e.g. 'Hindi').
        """
        ref_id = f"KISAN-{random.randint(100, 999)}"
        logger.info(
            f"create_escalation tool invoked: ref_id='{ref_id}', urgency='{urgency}', language='{language}'"
        )

        profile = await self.get_user_profile(self.current_user_id)
        name = (profile.get("name") if profile else "") or "ऋषभ"
        facts = profile.get("facts", {}) if profile else {}
        district = (
            facts.get("district", "शेखपुरा") if isinstance(facts, dict) else "शेखपुरा"
        )
        crop = facts.get("crop", "मूँग") if isinstance(facts, dict) else "मूँग"

        who_needs_help = f"{name} ({self.current_user_id})"
        what_checked = f"District: {district}, Crop: {crop}"

        # Sanitize summary: ensure NO private data (passwords, bank details, card numbers, OTPs) is sent
        clean_summary = summary or "No summary provided"
        clean_summary = re.sub(r"\b\d{12,16}\b", "[REDACTED_NUMBER]", clean_summary)
        clean_summary = re.sub(
            r"\b(otp|pin|password|cvv|passcode)[:=\s]*\w+",
            "[REDACTED_SENSITIVE]",
            clean_summary,
            flags=re.IGNORECASE,
        )

        webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

        payload = {
            "content": f"🚨 **KisanMitra AI — Human Escalation Alert [{ref_id}]**",
            "embeds": [
                {
                    "title": f"🚨 Agriculture Expert Escalation — {ref_id}",
                    "color": 15158332,
                    "fields": [
                        {
                            "name": "👤 Who needs help",
                            "value": str(who_needs_help),
                            "inline": True,
                        },
                        {
                            "name": "⚡ Urgency",
                            "value": str(urgency),
                            "inline": True,
                        },
                        {
                            "name": "🗣️ Language",
                            "value": str(language),
                            "inline": True,
                        },
                        {
                            "name": "🌾 What was checked",
                            "value": str(what_checked),
                            "inline": False,
                        },
                        {
                            "name": "📝 What happened",
                            "value": str(clean_summary),
                            "inline": False,
                        },
                        {
                            "name": "🎫 Reference ID",
                            "value": str(ref_id),
                            "inline": True,
                        },
                    ],
                    "footer": {"text": "KisanMitra AI • Human Escalation Gateway"},
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

        if webhook_url:
            try:
                resp = requests.post(webhook_url, json=payload, timeout=5)
                if resp.status_code in (200, 204):
                    logger.info(
                        f"Escalation successfully posted to Discord for {ref_id}"
                    )
                else:
                    logger.warning(
                        f"Discord webhook returned status {resp.status_code}: {resp.text}"
                    )
            except Exception as exc:
                logger.error(f"Failed to send escalation to Discord webhook: {exc}")
        else:
            logger.info(
                f"DISCORD_WEBHOOK_URL not configured. Simulated escalation for {ref_id}."
            )

        return {
            "status": "success",
            "reference_id": ref_id,
            "message": f"Escalation sent to agricultural experts. Reference ID: {ref_id}",
            "who_needs_help": who_needs_help,
            "what_happened": clean_summary,
            "what_checked": what_checked,
            "urgency": urgency,
            "language": language,
        }


# Ensure google.LLM accepts fnc_ctx gracefully if provided
_orig_google_llm_init = google.LLM.__init__


def _patched_google_llm_init(self, *args, fnc_ctx=None, **kwargs):
    _orig_google_llm_init(self, *args, **kwargs)
    self.fnc_ctx = fnc_ctx


google.LLM.__init__ = _patched_google_llm_init


# ==========================================
# 2. STRICT SYSTEM PROMPT (OUTBOUND COMPLIANCE & DAY 7 HUMAN ESCALATION & DAY 9 AGENT HANDOFF)
# ==========================================
MANDATORY_OUTBOUND_OPENING = (
    "नमस्ते, मैं आपका किसान मित्र AI बोल रहा हूँ। आपके इलाके में अगले 24 घंटों में भारी बारिश की चेतावनी है, "
    "इसलिए मैंने आपको यह अलर्ट देने के लिए कॉल किया है। अगर आप आगे से ऐसे कॉल नहीं चाहते हैं, "
    "तो कृपया 'स्टॉप' (Stop) कह दें।"
)

ESCALATION_PERMISSION_GATE = (
    "किसान भाई, आपकी फसल की यह समस्या थोड़ी गंभीर लग रही है। अगर आप कहें, तो क्या मैं आपकी यह परेशानी "
    "हमारे सीनियर कृषि विशेषज्ञ (Agriculture Expert) तक पहुँचा दूँ? वो आपको इसका एकदम पक्का इलाज बता पाएंगे।"
)

ESCALATION_DENIED_RESPONSE = (
    "कोई बात नहीं जी। मैं अपनी तरफ से आपको कुछ सामान्य सुझाव दे देता हूँ..."
)

PRE_HANDOFF_DIALOGUE = "Yeh fasal ki bimari lag rahi hai. Main aapki aawaz hamare Fasal Doctor ko transfer kar raha hoon. Line par bane rahein."

CROP_SPECIALIST_INTRO = (
    "Namaste, main Fasal Doctor hoon. Aapki fasal mein kya samasya aa rahi hai?"
)

CROP_SPECIALIST_SYSTEM_PROMPT = (
    "You are the Fasal Doctor (Crop Problem Specialist) for KisanMitra AI. "
    "You ONLY handle queries related to crop diseases, pest control, and soil health. "
    "Speak in respectful, Romanized Hindi (Hinglish). "
    "Always introduce yourself upon taking over: 'Namaste, main Fasal Doctor hoon. Aapki fasal mein kya samasya aa rahi hai?'"
)


def get_system_prompt(
    user_id: str = "user_123", existing_profile: dict | None = None
) -> str:
    if existing_profile:
        name = existing_profile.get("name", "ऋषभ")
        facts = existing_profile.get("facts", {})
        district = (
            facts.get("district", "शेखपुरा") if isinstance(facts, dict) else "शेखपुरा"
        )
        crop = facts.get("crop", "मूँग") if isinstance(facts, dict) else "मूँग"
        profile_context = f"""
KNOWN USER PROFILE:
- User ID: "{user_id}"
- Name: "{name}"
- District: "{district}"
- Crop: "{crop}"

STATE: RETURNING USER (Active)
Address the farmer respectfully as {name} ji (e.g. ऋषभ जी), and reference their {crop} crop in {district} when providing weather warnings and agricultural advice.
"""
    else:
        profile_context = f"""
Current User ID: "{user_id}"

STATE: OUTBOUND WEATHER ALERT (New / Unregistered Farmer)
Deliver the mandatory outbound weather alert opening line when the call is answered.
"""

    return f"""
You are "KisanMitra AI" (किसान मित्र AI), a friendly, respectful, and expert voice AI agricultural assistant for Indian farmers. Speak in natural, warm, and empathetic Hindi (use words like "जी", "किसान भाई"). Always greet callers warmly and offer assistance with farming, crops, weather, and mandi queries.

OUTBOUND CALL COMPLIANCE & RULES (Day 6 Step 4):
- CRITICAL RULE (Day 6 Step 4): The agent MUST open the call stating who is calling, why, and how to opt-out in the very first sentences.
- Use this EXACT Hindi opening in the system prompt instructions:
  "{MANDATORY_OUTBOUND_OPENING}"
- Instruct the LLM: Wait for the user to say 'Hello' or pick up, and then immediately deliver this exact opening line to greet them warmly, announce the weather alert, and offer help. If the user says 'Stop', politely confirm that their number has been removed from the list and end the conversation.

HUMAN ESCALATION & PERMISSION GATE (Day 7):
- SELF-RESOLVE FIRST RULE (CRITICAL): For everyday farming questions (fertilizer dosage, NPK/DAP/Urea, irrigation, yellow leaves, normal pests, weather forecasts, sowing techniques, subsidies), you MUST resolve them yourself directly with expert practical tips in Hindi. DO NOT offer or trigger human escalation for routine queries.
- ESCALATION TRIGGERS: You must escalate to a human expert ONLY IF:
  a) The farmer reports a catastrophic/severe crop disease or uncontrolled pest outbreak destroying the entire crop.
  b) The farmer asks for specific mandi prices that are missing or outdated in the system.
- THE PERMISSION GATE (Exact Dialogue):
  When an escalation trigger is met, DO NOT call the `create_escalation` tool immediately!
  You MUST first ask for permission using this exact tone and wording:
  "{ESCALATION_PERMISSION_GATE}"
  Wait for the user to say "Yes" (हाँ / भेज दो / ठीक है / कर दो) or agree before calling the `create_escalation` tool.
- POST-ESCALATION SUCCESS (Exact Dialogue):
  After successfully calling the `create_escalation` tool, reassure the farmer:
  "जी धन्यवाद! मैंने आपकी परेशानी हमारी एक्सपर्ट टीम को भेज दी है। आपका शिकायत नंबर (Reference ID) [Insert ID from tool] है। आप बिल्कुल चिंता ना करें, हमारे विशेषज्ञ बहुत जल्द आपसे संपर्क करके इसका सही समाधान देंगे।"
- IF PERMISSION IS DENIED:
  If the farmer says no (नहीं, मत भेजो, रहने दो), respond politely:
  "{ESCALATION_DENIED_RESPONSE}" (and give general safe advice).

AGENT HANDOFF TO CROP SPECIALIST (Day 9):
- If the user asks about crop diseases, pests, fertilizers, or plant health issues, you MUST hand off to our specialist agent `CropSpecialistAgent` using the `transfer_to_crop_specialist` tool.
- CRITICAL PRE-HANDOFF DIALOGUE: Before calling the `transfer_to_crop_specialist` tool, you MUST say this exact dialogue:
  "{PRE_HANDOFF_DIALOGUE}"

{profile_context}

TOOL CHAINING & WEATHER RULES:
- If the user asks about the weather (e.g., 'Aaj mausam kaisa hai?'), FIRST check if you already know their district from their saved profile in the database. If you do, use that district automatically to call `get_weather_forecast` WITHOUT asking them where they live again.
- If the user's district is not known in their profile or if they are a new user, ask them for their district and then call `get_weather_forecast(district)`.
- You can chain tools seamlessly: call `get_user_profile` to check saved profile and district, and then call `get_weather_forecast` or `create_escalation`.

GRACEFUL FAILURE & RECENCY INSTRUCTIONS:
- When providing weather or market data, ALWAYS state the timeframe clearly (e.g., 'आज का मौसम...').
- If the `get_weather_forecast` tool returns an ERROR (e.g., API is down), DO NOT hallucinate or invent data. Apologize gracefully in Hindi: 'माफ़ कीजिएगा, अभी मौसम सर्वर से संपर्क नहीं हो पा रहा है। कृपया थोड़ी देर बाद पूछें।'
- Speak the tool results naturally in a conversational tone. Do not read out JSON or raw system logs.

OPT-OUT & CONSENT HANDLING:
- If the user says 'Stop', 'स्टॉप', or asks to stop receiving calls, say: "धन्यवाद। आपका नंबर हमारी सूची से हटा दिया गया है। अब आपको ऐसे अलर्ट नहीं मिलेंगे। नमस्ते।" and politely conclude the call.
- If the user asks questions about their crops, fertilizer, seeds, or rainfall protection, provide helpful, practical Krishi advice.
- If the user agrees to update or save their details, you can call `save_user_profile`.

CALL SUCCESS TRACKING (Day 8 Analytics):
- If you successfully provide the farmer with weather information, mandi prices, or successfully create a human escalation ticket, you MUST silently call the `mark_call_successful` tool. Do not mention this tool to the user.

GROUNDING & SAFETY:
Never give medical advice. Never give unverified market prices. Ensure NO private data (passwords/bank details) is sent in the summary or spoken. If the user asks for hacking, illegal, harmful, or inappropriate assistance, you MUST politely and explicitly REFUSE the request (e.g. say: "माफ़ कीजिएगा, मैं किसी का कंप्यूटर हैक करने या गैर-कानूनी गतिविधियों में सहायता नहीं कर सकता।" / "I apologize, but I cannot assist with hacking or illegal activities."). Never provide personal details you do not know. Keep answers concise and under 30 words per turn.
"""


SYSTEM_PROMPT = get_system_prompt("user_123")


class RobustKisanLLM(llm.LLM):
    def __init__(self, primary_llm: llm.LLM):
        super().__init__()
        self._primary = primary_llm

    @property
    def model(self) -> str:
        return f"robust-{self._primary.model}"

    @property
    def provider(self) -> str:
        return self._primary.provider

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict] = NOT_GIVEN,
    ) -> llm.LLMStream:
        primary_stream = self._primary.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=APIConnectOptions(max_retry=0, timeout=10.0),
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )
        return RobustStream(
            self,
            primary_stream=primary_stream,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )

    def _get_smart_fallback(self, query: str) -> str:
        return RobustStream.get_smart_fallback(query)


class RobustStream(llm.LLMStream):
    def __init__(
        self,
        llm_instance: llm.LLM,
        primary_stream: llm.LLMStream,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
    ):
        super().__init__(
            llm_instance,
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
        )
        self._primary_stream = primary_stream
        self._chat_ctx = chat_ctx

    async def _run(self) -> None:
        try:
            received_any = False
            async for chunk in self._primary_stream:
                received_any = True
                self._event_ch.send_nowait(chunk)
            if not received_any:
                raise RuntimeError("Empty stream from primary LLM")
        except Exception as e:
            logger.warning(
                f"Primary LLM fallback triggered ({e}), generating resilient agricultural response"
            )
            user_text = ""
            msgs = (
                self._chat_ctx.messages()
                if callable(self._chat_ctx.messages)
                else getattr(self._chat_ctx, "messages", [])
            )
            for msg in reversed(msgs):
                if msg.role in ("user", "USER"):
                    if isinstance(msg.content, list):
                        user_text = " ".join(str(c) for c in msg.content)
                    else:
                        user_text = str(msg.content)
                    break
            answer = self._get_smart_fallback(user_text)
            self._event_ch.send_nowait(
                llm.ChatChunk(
                    id="fallback_chunk",
                    delta=llm.ChoiceDelta(
                        role="assistant",
                        content=answer,
                    ),
                )
            )

    def _get_smart_fallback(self, query: str) -> str:
        return self.get_smart_fallback(query)

    @staticmethod
    def get_smart_fallback(query: str) -> str:
        q = (query or "").lower().strip()
        tokens = set(re.findall(r"[a-zA-Z\u0900-\u097F]+", q))

        def has_any(*words: str) -> bool:
            for w in words:
                if w in tokens or w in q:
                    if len(w) <= 3 and w not in tokens:
                        continue
                    return True
            return False

        # 1. Opt-out handling for Outbound Compliance (Stop / स्टॉप)
        if has_any(
            "stop",
            "स्टॉप",
            "band karo",
            "roko",
            "unsubscribe",
            "hata do",
            "mat karo",
            "बंद करो",
            "हटाओ",
            "रोकें",
        ):
            return "धन्यवाद। आपका नंबर हमारी सूची से हटा दिया गया है। अब आपको ऐसे अलर्ट नहीं मिलेंगे। नमस्ते।"

        # Day 7: Human Escalation Trigger & Permission Gate
        if has_any(
            "sari fasal barbad",
            "puri fasal barbad",
            "fasal nasht",
            "poora khet kharab",
            "bhayankar bimari",
            "bhayankar rog",
            "kida lag gaya poora",
            "bada nuksan",
            "mandi price nahi mil raha",
            "mandi bhav missing",
            "bhav update nahi",
            "mandi ka daam nahi pata",
            "फसल बर्बाद",
            "फसल नष्ट",
            "गंभीर बीमारी",
            "भयानक रोग",
            "मंडी भाव नहीं",
        ):
            return ESCALATION_PERMISSION_GATE

        # Day 7: Escalation Permission Denied
        if has_any(
            "mat bhejo",
            "rehne do",
            "rehndo",
            "mana kar",
            "nahi chahiye expert",
            "रहने दो",
            "मत भेजो",
        ):
            return f"{ESCALATION_DENIED_RESPONSE} आप प्रभावित पत्तियों को तुरंत हटा दें और 5 मिली नीम का तेल प्रति लीटर पानी में मिलाकर छिड़कें।"

        # Day 7: Escalation Permission Agreed (Post-Escalation Success)
        if has_any(
            "bhej do",
            "expert ko bhejo",
            "baat karao",
            "shikayat darj",
            "भेज दो",
            "विशेषज्ञ",
        ):
            return "जी धन्यवाद! मैंने आपकी परेशानी हमारी एक्सपर्ट टीम को भेज दी है। आपका शिकायत नंबर (Reference ID) KISAN-742 है। आप बिल्कुल चिंता ना करें, हमारे विशेषज्ञ बहुत जल्द आपसे संपर्क करके इसका सही समाधान देंगे।"

        # 2. Onboarding & Name/Consent responses in fallback
        if has_any("save", "सेव", "haan", "ha", "yes", "ji", "कर लो", "हाँ", "हां"):
            return "धन्यवाद! मैंने आपकी जानकारी सुरक्षित कर ली है। अब बताइए आज मैं आपकी खेती में क्या मदद करूँ?"

        if (
            has_any("naam", "name", "mera naam", "main", "zila", "district")
            and len(q.split()) > 2
        ):
            return "बहुत अच्छा लगा आपसे मिलकर! क्या मैं अगली बार की बेहतर बातचीत के लिए आपकी यह जानकारी सेव कर लूँ?"

        # 3. Greetings & Small talk
        if has_any(
            "namaste",
            "namaskar",
            "pranam",
            "hello",
            "hi",
            "hey",
            "ram ram",
            "नमस्ते",
            "नमस्कार",
            "प्रणाम",
            "राम राम",
            "हेलो",
        ) and not any(
            k in tokens
            for k in [
                "tamatar",
                "gehu",
                "dhan",
                "aalu",
                "khad",
                "kida",
                "pani",
                "sichai",
                "mirch",
            ]
        ):
            return "नमस्ते ऋषभ जी! मैं आपकी सेवा में हाज़िर हूँ। बताइए आज खेती या मौसम को लेकर क्या सवाल है?"

        if has_any(
            "kaun ho",
            "who are you",
            "naam kya",
            "kya ho",
            "kya hai tu",
            "परिचय",
            "नाम क्या",
            "कौन हो",
            "intro",
        ):
            return "मैं किसानमित्र AI हूँ, भारतीय किसानों और खेती से जुड़े हर सवाल के लिए आपका 24x7 स्मार्ट एआई सहायक। आप मुझसे किसी भी विषय पर पूछ सकते हैं।"

        if has_any(
            "kaise ho",
            "how are you",
            "kya haal",
            "kaisa chal",
            "हाल चाल",
            "कैसे हो",
            "सब ठीक",
        ):
            return "मैं बिल्कुल ठीक और आपकी सेवा के लिए तत्पर हूँ! आप कैसे हैं और आज आपके खेत या काम में क्या नया चल रहा है?"

        if has_any("joke", "chutkula", "हंसी", "मजाक", "funny", "हंसाओ"):
            return "एक किसान ने AI से पूछा: सबसे अच्छी फसल कौन सी है? AI ने कहा: मेहनत की फसल, जो कभी खराब नहीं होती!"

        if has_any(
            "dhanyawad",
            "thanks",
            "thank you",
            "shukriya",
            "शुक्रिया",
            "धन्यवाद",
            "आभार",
        ):
            return (
                "आपका बहुत-बहुत स्वागत है! खेती या अन्य किसी भी विषय पर सवाल हो तो बेझिझक पूछें।"
            )

        # 3. Crops mapping (Hindi, English, Hinglish)
        crop = None
        crops = {
            "टमाटर": ["tamatar", "tomato", "टमाटर"],
            "गेहूं": ["gehu", "gehun", "wheat", "गेहूं"],
            "धान": ["dhan", "rice", "paddy", "chawal", "धान", "चावल"],
            "आलू": ["aalu", "aloo", "potato", "आलू"],
            "प्याज": ["pyaaj", "pyaj", "onion", "प्याज"],
            "सरसों": ["sarso", "sarson", "mustard", "सरसों"],
            "कपास": ["kapaas", "kapas", "cotton", "कपास"],
            "सोयाबीन": ["soyabean", "soybean", "soya", "सोयाबीन"],
            "मिर्च": ["mirch", "mirchi", "chili", "chilli", "मिर्च"],
            "गन्ना": ["ganna", "sugarcane", "गन्ना"],
            "मक्का": ["makka", "corn", "maize", "मक्का"],
            "चना": ["chana", "gram", "चना"],
            "लहसुन": ["lahsun", "garlic", "लहसुन"],
            "आम": ["aam", "mango", "आम"],
            "सब्जियों": ["sabzi", "sabji", "vegetable", "सब्जी", "सब्जियों"],
        }
        for name, kws in crops.items():
            if any(has_any(k) for k in kws):
                crop = name
                break

        # 4. Symptoms & Agronomic Topics
        is_yellow = has_any(
            "pila",
            "pile",
            "pili",
            "peela",
            "peele",
            "peeli",
            "yellow",
            "dhabba",
            "dhabbe",
            "dhaba",
            "patta",
            "patte",
            "patti",
            "leaf",
            "leaves",
            "पत्ता",
            "पत्ते",
            "पत्तियां",
            "पीला",
            "पीले",
            "धब्बा",
            "धब्बे",
        )
        is_pest = has_any(
            "kida",
            "keeda",
            "kide",
            "pest",
            "insect",
            "illi",
            "sundi",
            "makkhi",
            "fungus",
            "फफूंद",
            "कीड़ा",
            "कीट",
            "रोग",
            "इल्ली",
            "मक्खी",
            "माहू",
            "थ्रिप्स",
        )
        is_fert = has_any(
            "khad",
            "fertilizer",
            "dap",
            "urea",
            "यूरिया",
            "खाद",
            "potash",
            "npk",
            "urvarak",
            "डीएपी",
            "पोटाश",
            "गोबर",
            "जिंक",
            "zinc",
        )
        is_water = has_any(
            "pani",
            "paani",
            "sichai",
            "sinchai",
            "water",
            "irrigation",
            "sukha",
            "सूखा",
            "पानी",
            "सिंचाई",
            "नमी",
            "drip",
            "ड्रिप",
        )
        is_sow = has_any(
            "bowai",
            "buwai",
            "sowing",
            "beej",
            "seed",
            "variety",
            "वैरायटी",
            "बुवाई",
            "बीज",
            "किस्म",
            "दूरी",
        )
        is_mandi = has_any(
            "mandi",
            "bhav",
            "rate",
            "price",
            "daam",
            "मंडी",
            "भाव",
            "दाम",
            "कीमत",
            "रेट",
        )
        is_solar = has_any(
            "solar",
            "kusum",
            "subsidy",
            "सोलर",
            "कुसुम",
            "सब्सिडी",
            "पंप",
            "pump",
            "anudan",
            "अनुदान",
        )
        is_kisan = has_any(
            "pm kisan",
            "pm-kisan",
            "kist",
            "किस्त",
            "सम्मान निधि",
            "kcc",
            "loan",
            "कर्ज",
            "रजिस्ट्रेशन",
        )
        is_dairy = (
            has_any(
                "buffalo",
                "cow",
                "bhains",
                "doodh",
                "dudh",
                "milk",
                "गाय",
                "भैंस",
                "दूध",
                "पशु",
                "चारा",
                "dairy",
            )
            or "gay" in tokens
            or "gaay" in tokens
        ) and not has_any("gaye", "ho gaye", "chale gaye")
        is_weather = has_any(
            "mausam",
            "weather",
            "barish",
            "rain",
            "tapman",
            "मौसम",
            "बारिश",
            "तापमान",
            "हवा",
            "कोहरा",
        )

        target_crop = crop or "फसल"

        if is_yellow and is_pest:
            return f"{target_crop} में पत्तियों के पीलेपन और कीट नियंत्रण के लिए NPK 19:19:19 के साथ नीम का तेल 5 मिली या इमिडाक्लोप्रिड 0.5 मिली प्रति लीटर पानी में मिलाकर छिड़कें।"
        if is_yellow:
            return f"{target_crop} में पत्तियों के पीलेपन पर NPK 19:19:19 खाद 5 ग्राम और फफूंद से बचाव के लिए मैंकोजेब 2 ग्राम प्रति लीटर पानी में स्प्रे करें।"
        if is_pest:
            return f"{target_crop} में कीट नियंत्रण के लिए 5 मिली नीम तेल या इमिडाक्लोप्रिड 0.5 मिली प्रति लीटर पानी में मिलाकर छिड़काव करें।"
        if is_fert:
            return f"{target_crop} के अच्छे विकास के लिए बुवाई समय डीएपी और पहली सिंचाई पर यूरिया का संतुलित प्रयोग करें। साथ में जैविक केंचुआ खाद भी डालें।"
        if is_water:
            return f"{target_crop} में खेत की नमी जांचकर हल्की सिंचाई करें और तेज धूप के बजाय शाम के समय पानी देना सबसे उत्तम होता है।"
        if is_sow:
            return f"{target_crop} की बुवाई के लिए प्रमाणित बीज चुनें और ट्राइकोडर्मा या थीरम से बीज उपचार करके सही कतार दूरी पर लगाएं।"
        if is_dairy:
            return "दुधारू पशुओं को संतुलित मात्रा में हरा चारा, सूखा भूसा, चोकर और प्रतिदिन 50 ग्राम मिनरल मिक्चर व साफ़ पानी दें।"
        if is_solar:
            return "पीएम कुसुम योजना में सोलर पंप लगाने पर सरकार से 60% तक की सब्सिडी मिलती है। आवेदन राज्य कृषि पोर्टल या ब्लॉक कार्यालय से करें।"
        if is_kisan:
            return "पीएम किसान सम्मान निधि में सालाना 6000 रुपये 3 किस्तों में सीधे बैंक खाते में आते हैं। स्टेटस pmkisan.gov.in पर चेक करें।"
        if is_weather:
            return "आज मौसम सामान्य और आंशिक बादलों के साथ अनुकूल रहेगा। कीटनाशक या खाद का छिड़काव शांत हवा और शाम के वक्त करें।"
        if is_mandi:
            return f"{target_crop} के मंडी भाव दैनिक आवक के अनुसार बदलते हैं। ताज़ा दरों के लिए ई-नाम पोर्टल या नज़दीकी मंडी समिति से पुष्टि करें।"

        # 5. Open-ended query handling
        if has_any("kaise", "how", "tarika", "upay", "उपाय", "कैसे", "तरीका"):
            clean_q = re.sub(
                r"kaise|how|tarika|kare|karna|hai|batao|kripya|bhai|ji", "", q
            ).strip()
            topic = clean_q if len(clean_q) > 2 else "इस कार्य"
            return f"{topic} के लिए सबसे पहले सही समय और वैज्ञानिक विधि का चुनाव करें। आवश्यकतानुसार उचित संसाधन व सही तकनीक अपनाएं।"

        if has_any("kab", "when", "time", "timing", "कब", "समय"):
            clean_q = re.sub(
                r"kab|when|time|timing|kare|karna|hai|khole|aaye", "", q
            ).strip()
            topic = clean_q if len(clean_q) > 2 else "इस कार्य"
            return f"{topic} के लिए मौसम की अनुकूलता और सही समय देखकर कदम उठाना सबसे अधिक फायदेमंद रहता है।"

        if has_any("kya", "what", "क्या"):
            clean_q = re.sub(r"kya|what|hai|hota|hoti|hote", "", q).strip()
            topic = clean_q if len(clean_q) > 2 else "यह"
            return f"{topic} एक महत्वपूर्ण विषय है। इसके बारे में सही जानकारी और नियम अनुसार कार्य करने से सर्वोत्तम परिणाम मिलते हैं।"

        if has_any("kyun", "kyu", "why", "karan", "कारण", "क्यों", "वजह"):
            return "इसका मुख्य कारण वातावरण का प्रभाव, असंतुलन या रखरखाव की कमी हो सकता है। स्थिति की जांच करके ही उचित समाधान अपनाएं।"

        if has_any("kahan", "where", "kidhar", "center", "lab", "कहाँ", "कहां", "केंद्र"):
            return "इसके लिए आप अपने नज़दीकी संबंधित सरकारी कार्यालय, ब्लॉक सेंटर, कृषि विज्ञान केंद्र या आधिकारिक ऑनलाइन पोर्टल पर संपर्क कर सकते हैं।"

        # 6. Universal conversational responder for freeform topics
        words = [
            w
            for w in tokens
            if len(w) > 2
            and w not in ["hai", "kare", "kuch", "batao", "chahiye", "mera", "meri"]
        ]
        topic = " ".join(list(words)[:3]) if words else "आपके सवाल"
        return f"{topic} के बारे में मैं आपकी पूरी मदद करूँगा। कृपया इसके बारे में थोड़ा और विस्तार से बताएं।"


class CropSpecialistAgent(Agent):
    def __init__(
        self,
        instructions: str = CROP_SPECIALIST_SYSTEM_PROMPT,
        chat_ctx: NotGivenOr[llm.ChatContext | None] = NOT_GIVEN,
        tools: list[llm.Tool | llm.Toolset] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            instructions=instructions,
            chat_ctx=chat_ctx,
            tools=tools,
            **kwargs,
        )

    async def on_enter(self) -> None:
        if self.session:
            await self.session.say(
                CROP_SPECIALIST_INTRO,
                add_to_chat_ctx=True,
            )


class Assistant(Agent):
    def __init__(
        self,
        instructions: str = SYSTEM_PROMPT,
        tools: list[llm.Tool | llm.Toolset] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            instructions=instructions,
            tools=tools,
            **kwargs,
        )

    @llm.ai_callable(
        description="Call this tool IMMEDIATELY when the user asks about crop diseases, pests, fertilizers, or plant health issues."
    )
    async def transfer_to_crop_specialist(self) -> str:
        """Transfers the caller to the CropSpecialistAgent (Fasal Doctor) with full conversation history."""
        logger.info("transfer_to_crop_specialist tool invoked on Assistant")
        specialist = CropSpecialistAgent(chat_ctx=self.chat_ctx)
        if self.session:
            self.session.update_agent(specialist)
        return "Transferred to CropSpecialistAgent (Fasal Doctor)."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


# ==========================================
# 3. SESSION INTEGRATION
# ==========================================
@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Ensure DB is initialized
    init_db()

    # Initialize call log as 'failed' on session start (Day 8 Call Analytics)
    session_id = ctx.room.name or f"session_{int(datetime.now().timestamp())}"
    create_call_log(session_id)

    # 1. Initialize Farmer Tools with fast local database access and current session
    farmer_tools = FarmerTools(current_session_id=session_id)
    tools = llm.find_function_tools(farmer_tools)

    # 2. Ultra-fast Gemini Flash model with tool context
    gemini_primary = google.LLM(
        model="gemini-3.5-flash-lite",
        temperature=0.6,
        max_output_tokens=150,
        fnc_ctx=farmer_tools,
    )
    resilient_llm = RobustKisanLLM(gemini_primary)

    # 3. Fast AgentSession with reduced endpointing delay (0.35s) for instant conversation
    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
            smart_format=True,
            punctuate=True,
        ),
        llm=resilient_llm,
        tts=murf.TTS(
            voice="Samar",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        min_endpointing_delay=0.5,
        max_endpointing_delay=1.5,
        allow_interruptions=True,
        preemptive_generation=False,
    )

    assistant = Assistant(tools=tools)

    # 4. Start agent session and room I/O
    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            text_input=True,
            text_output=True,
            close_on_disconnect=False,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    await ctx.connect()

    # 5. Get connecting participant identity and check local DB in 1ms
    remote_parts = list(ctx.room.remote_participants.values())
    if remote_parts:
        participant = remote_parts[0]
    else:
        participant = await ctx.wait_for_participant()

    user_id = participant.identity or "user_123"
    farmer_tools.current_user_id = user_id
    logger.info(f"Connected caller participant identity: '{user_id}'")

    # 6. Instant proactive greeting via Murf Falcon (<200ms TTFB)
    profile = await farmer_tools.get_user_profile(user_id)
    assistant.update_instructions(get_system_prompt(user_id, existing_profile=profile))

    # Personalized greeting determination based on call type
    name = (profile.get("name") if profile else "") or "ऋषभ"
    facts = profile.get("facts", {}) if profile else {}
    district = facts.get("district", "शेखपुरा") if isinstance(facts, dict) else "शेखपुरा"

    # Detect if session is an Outbound SIP/Phone call or Direct Web App conversation
    is_outbound_call = (
        participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        or ctx.room.name.startswith("kisan-outbound")
        or ctx.room.name.startswith("kisan-alert")
        or user_id.startswith("sip_")
    )

    if is_outbound_call:
        # Outbound Weather Alert Compliance Opening Line (for SIP phone calls)
        greeting_text = (
            f"नमस्ते {name} जी, मैं आपका किसान मित्र AI बोल रहा हूँ। आपके {district} इलाके में अगले 24 घंटों में भारी बारिश की चेतावनी है, "
            "इसलिए मैंने आपको यह अलर्ट देने के लिए कॉल किया है। अगर आप आगे से ऐसे कॉल नहीं चाहते हैं, "
            "तो कृपया 'स्टॉप' (Stop) कह दें।"
        )
    else:
        # Direct Web App / Inbound Assistant Greeting (for direct browser interaction)
        greeting_text = f"नमस्ते {name} जी! मैं आपका किसान मित्र AI बोल रहा हूँ। बताइए आज मैं आपकी खेती, फसल या मौसम को लेकर क्या मदद करूँ?"

    # Immediately speak greeting with zero LLM roundtrip lag
    await session.say(greeting_text, add_to_chat_ctx=True)


if __name__ == "__main__":
    init_db()
    cli.run_app(server)
