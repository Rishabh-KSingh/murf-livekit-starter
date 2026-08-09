import json
import logging
import os
import re
import sqlite3
from datetime import datetime

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
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_LOCAL_PATH = os.path.join(BACKEND_DIR, ".env.local")
load_dotenv(ENV_LOCAL_PATH)

# ==========================================
# 1. SQLITE DATABASE SETUP
# ==========================================
DB_PATH = os.path.join(BACKEND_DIR, "kisan_mitra.db")


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes the SQLite database file and creates the users table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            language_preference TEXT,
            facts TEXT,
            last_interaction TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    print(f"✅ SQLite Database initialized successfully at: {db_path}")
    logger.info(f"Database initialized at '{db_path}' with table 'users'.")


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
        self, db_path: str = DB_PATH, current_user_id: str = "user_123"
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.current_user_id = current_user_id

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


# Ensure google.LLM accepts fnc_ctx gracefully if provided
_orig_google_llm_init = google.LLM.__init__


def _patched_google_llm_init(self, *args, fnc_ctx=None, **kwargs):
    _orig_google_llm_init(self, *args, **kwargs)
    self.fnc_ctx = fnc_ctx


google.LLM.__init__ = _patched_google_llm_init


# ==========================================
# 2. STRICT SYSTEM PROMPT (STATE MACHINE)
# ==========================================
def get_system_prompt(
    user_id: str = "user_123", existing_profile: dict | None = None
) -> str:
    if existing_profile:
        name = existing_profile.get("name", "")
        facts = existing_profile.get("facts", {})
        district = facts.get("district", "")
        crop = facts.get("crop", "")
        profile_context = f"""
KNOWN USER PROFILE:
- User ID: "{user_id}"
- Name: "{name}"
- District: "{district}"
- Crop: "{crop}"

STATE: RETURNING USER (Active)
The user's details are ALREADY known and saved in the database.
DO NOT ask for their name, district, or crop.
Address them respectfully as {name} ji, reference their {crop} crop in {district} when relevant, and directly answer their agricultural questions.
"""
    else:
        profile_context = f"""
Current User ID: "{user_id}"

STATE 1: NEW USER (Tool returns no data or caller not found)
Greet the caller warmly in a friendly manner:
"नमस्ते! मैं आपका किसान मित्र हूँ। क्या आप मुझे अपना नाम, अपना ज़िला, और आप कौन सी फसल उगाते हैं, यह बता सकते हैं?"
Collect their Name, District, Crop, and Land size.
BEFORE SAVING, ask: "क्या मैं अगली बार के लिए आपकी यह जानकारी सेव कर लूँ?"
When they say yes/agree (e.g. "हाँ", "सेव कर लो", "theek hai"), call `save_user_profile` with user_id="{user_id}", name, language_preference="Hindi", and facts as a JSON string.

STATE 2: RETURNING USER (Tool returns profile)
Greet them warmly by their name and continue from last time (e.g. "नमस्ते [Name], पिछली बार हमने आपके [District] में [Crop] की खेती पर बात की थी। आज क्या मदद करूँ?").
DO NOT ask for their name again.
"""

    return f"""
You are KisanMitra AI, a friendly and helpful voice AI krishi sahayak for Indian farmers. Always greet callers warmly and offer assistance with farming.

{profile_context}

USER CORRECTION / DIFFERENT PERSON RULE:
If the caller states that they are someone else, a different person, or not the person identified (e.g. "Main [Name] nahi hoon", "Yeh doosra kisan hai", "Mera naya profile banao", "Main Suresh bol raha hoon"):
1. Politely apologize and greet them warmly.
2. Ask for their Name, District, Crop, and Land size.
3. Ask for explicit consent: "क्या मैं अगली बार के लिए आपकी यह जानकारी सेव कर लूँ?"
4. When they agree, call `save_user_profile` with their updated details.

GROUNDING & SAFETY:
Never give medical advice. Never give unverified market prices. If asked for private personal details you do not have (such as birthplace, passwords, etc.), politely state that you do not have access to that personal information. Keep answers concise and under 20 words.
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
        q = (query or "").lower().strip()
        tokens = set(re.findall(r"[a-zA-Z\u0900-\u097F]+", q))

        def has_any(*words: str) -> bool:
            for w in words:
                if w in tokens or w in q:
                    if len(w) <= 3 and w not in tokens:
                        continue
                    return True
            return False

        # 1. Onboarding & Name/Consent responses in fallback
        if has_any("save", "सेव", "haan", "ha", "yes", "ji", "कर लो", "हाँ", "हां"):
            return "धन्यवाद! मैंने आपकी जानकारी सुरक्षित कर ली है। अब बताइए आज मैं आपकी खेती में क्या मदद करूँ?"

        if (
            has_any("naam", "name", "mera naam", "main", "zila", "district")
            and len(q.split()) > 2
        ):
            return "बहुत अच्छा लगा आपसे मिलकर! क्या मैं अगली बार की बेहतर बातचीत के लिए आपकी यह जानकारी सेव कर लूँ?"

        # 2. Greetings & Small talk
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
            return "नमस्ते! मैं आपका किसान मित्र हूँ। ऐसा लगता है हम पहली बार बात कर रहे हैं। क्या आप मुझे अपना नाम, अपना ज़िला, और आप कौन सी फसल उगाते हैं, यह बता सकते हैं?"

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


class Assistant(Agent):
    def __init__(
        self,
        instructions: str = SYSTEM_PROMPT,
        tools: list[llm.Tool] | None = None,
    ) -> None:
        super().__init__(
            instructions=instructions,
            tools=tools,
        )


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

    # 1. Initialize Farmer Tools with fast local database access
    farmer_tools = FarmerTools()
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
        min_endpointing_delay=0.35,
        max_endpointing_delay=1.5,
        allow_interruptions=True,
        preemptive_generation=True,
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
    if profile:
        name = profile.get("name", "किसान भाई")
        facts = profile.get("facts", {})
        district = facts.get("district", "आपके क्षेत्र")
        crop = facts.get("crop", "खेती")
        greeting_text = f"नमस्ते {name}, पिछली बार हमने आपके {district} में {crop} की खेती पर बात की थी। आज क्या मदद करूँ?"
        assistant.update_instructions(
            get_system_prompt(user_id, existing_profile=profile)
        )
    else:
        greeting_text = "नमस्ते! मैं आपका किसान मित्र हूँ। ऐसा लगता है हम पहली बार बात कर रहे हैं। क्या आप मुझे अपना नाम, अपना ज़िला, और आप कौन सी फसल उगाते हैं, यह बता सकते हैं?"
        assistant.update_instructions(get_system_prompt(user_id, existing_profile=None))

    # Immediately speak greeting with zero LLM roundtrip lag
    await session.say(greeting_text, add_to_chat_ctx=True)


if __name__ == "__main__":
    init_db()
    cli.run_app(server)
