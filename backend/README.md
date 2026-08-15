# 🌾 KisanMitra AI — Backend Architecture & Service Guide
### Day 1 to Day 5 Engineering Details, Pipeline Specs & Deployment

The Python backend for **KisanMitra AI (किसान मित्र AI)**, powered by [LiveKit Agents v1.4](https://docs.livekit.io/agents), [Murf Falcon Streaming TTS](https://murf.ai/api/docs/text-to-speech/streaming), [Deepgram Nova-3 STT](https://developers.deepgram.com), and [Google Gemini](https://aistudio.google.com/).

---

## 🗓️ 5-Day Engineering Breakdown

### Day 1: Foundation & WebRTC Setup
- Initialized LiveKit Agents framework with `AgentServer` and `AgentSession`.
- Prewarmed Silero VAD (`prewarm()`) to prevent cold-start delays.
- Connected basic real-time loop: Deepgram STT $\rightarrow$ Google Gemini LLM $\rightarrow$ Murf Falcon TTS.

### Day 2: Murf Falcon Streaming, Latency & Noise Cancellation
- Integrated **Samar** voice with sentence-level streaming tokenization (`SentenceTokenizer(min_sentence_len=2)`).
- Enabled `text_pacing=True`, `allow_interruptions=True`, and `preemptive_generation=True`.
- Tuned endpointing delays (`min_endpointing_delay: 0.35s`, `max_endpointing_delay: 1.5s`) for instant turn-taking.
- Added LiveKit Background Voice Cancellation (`BVC` / `BVCTelephony`) to eliminate farm ambient noise.

### Day 3: Krishi Sahayak Persona & Agronomic Intelligence
- Built comprehensive Hindi/Hinglish knowledge base for 15+ crops (Wheat, Tomato, Paddy, Potato, Onion, Mustard, Cotton, Soybean, Chili, etc.).
- Integrated dosages for disease & pest control (NPK 19:19:19, Neem Oil, Imidacloprid, Mancozeb, Trichoderma).
- Added guidance for dairy farming, cattle feed, **PM-Kisan Samman Nidhi**, **PM-Kusum Solar Subsidies**, and **e-NAM Mandi Bhav**.

### Day 4: Persistent Memory & State-Machine (SQLite)
- Built local SQLite database (`kisan_mitra.db`) with table `users (user_id, name, language_preference, facts, last_interaction)`.
- **State 1 (New User):** Gathers details and requests explicit consent (*"क्या मैं अगली बार के लिए आपकी यह जानकारी सेव कर लूँ?"*) before persisting.
- **State 2 (Returning User):** Instantly identifies caller and speaks zero-roundtrip proactive greeting:
  > *"नमस्ते [Name] जी, पिछली बार हमने आपके [District] में [Crop] की खेती पर बात की थी। आज क्या मदद करूँ?"*
- Added user correction & multi-user support when a caller states they are someone else.

### Day 5: Live Tool Chaining, Resilient Fallbacks & Eval Tests
- Created `get_weather_forecast(district)` tool integrated with `wttr.in`.
- **Tool Chaining:** Automatically extracts farmer's district from SQLite when they ask *"आज मौसम कैसा है?"* and calls the weather tool without re-asking location.
- **Anti-Hallucination & Recency:** Clearly prefixes timeframe (*"आज का मौसम..."*) and returns graceful Hindi error messages if APIs drop.
- **RobustKisanLLM:** Sub-50ms local fallback engine ensuring zero dead air or dropped calls during LLM API timeouts or quota limits.
- Built test suites: `tests/test_day5.py` and `tests/test_agent.py`.

---

## 🏗️ Real-Time Voice Pipeline Architecture

```
Farmer speaks (Hindi/Hinglish)
       │
       ▼
[LiveKit Real-Time WebRTC Transport]
       │
       ▼
[Noise Cancellation (BVC / BVCTelephony)]
       │
       ▼
[Silero VAD + Multilingual Turn Detector]
       │
       ▼
[Deepgram Nova-3 STT (Multilingual)]
       │
       ▼
[KisanMitra AgentSession & State Machine]
   ├── [SQLite Memory (kisan_mitra.db)] ── Stores Name, District, Crop, Consent
   ├── [Weather Tool (wttr.in)] ──────────── Fetches Live District Forecasts
   ├── [Google Gemini 2.5/Flash-Lite] ────── LLM Function Calling & Reasoning
   └── [RobustKisanLLM Engine] ───────────── Local Resilient Fallback (<50ms)
       │
       ▼
[Murf Falcon Streaming TTS (Samar Voice, Conversational Style)]
       │
       ▼
Farmer hears instant natural Hindi response (<130ms TTFB)
```

---

## 🚀 Setup & Execution

### 1. Install Dependencies
```bash
cd backend
uv sync
uv run python src/agent.py download-files
```

### 2. Configure Environment (`backend/.env.local`)
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxx
LIVEKIT_API_SECRET=secretxxxxxxxxx
MURF_API_KEY=your_murf_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_gemini_api_key
```

### 3. Run Backend Worker
```bash
# Development mode with auto-reload:
uv run python src/agent.py dev

# Terminal voice testing (no browser required):
uv run python src/agent.py console

# Production worker:
uv run python src/agent.py start
```

---

## 🧪 Testing

```bash
uv run pytest
```
- `tests/test_day5.py`: Unit tests for weather tool, error handling, tool chaining, and DB persistence.
- `tests/test_agent.py`: LiveKit LLM-as-a-judge eval suite for friendliness, grounding, and safety refusals.

---

## 🚢 Docker & Production

```bash
docker build -t kisanmitra-backend .
docker run --env-file .env.local kisanmitra-backend
```
Deploy to Railway using the included `Dockerfile` and `railway.toml`.
