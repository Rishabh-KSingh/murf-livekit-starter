<div align="center">

# 🌾 KisanMitra AI
### Real-Time Voice AI Krishi Sahayak (भारत का स्मार्ट कृषि सहायक)

*Powered by Murf Falcon TTS, Deepgram Nova-3, Google Gemini & LiveKit Agents*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Murf Falcon](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api/docs/text-to-speech/streaming)
[![LiveKit Agents](https://img.shields.io/badge/Transport-LiveKit%20v1.4-002cf2)](https://docs.livekit.io)
[![Deepgram](https://img.shields.io/badge/STT-Deepgram%20Nova--3-13EF93?logo=deepgram&logoColor=black)](https://deepgram.com)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini%20Flash-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2014-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

</div>

## 📖 Table of Contents

- [📌 Project Overview](#-project-overview)
- [🗓️ 5-Day Engineering Journey](#️-5-day-engineering-journey)
- [🏗️ Complete System Architecture](#️-complete-system-architecture)
- [✨ Core Features Deep-Dive](#-core-features-deep-dive)
- [🧠 State Machine & SQLite Database Schema](#-state-machine--sqlite-database-schema)
- [🛠️ Tool Specifications & Automatic Chaining](#️-tool-specifications--automatic-chaining)
- [🛡️ Resilient LLM Fallback Engine](#️-resilient-llm-fallback-engine-robustkisanllm)
- [📂 Repository Directory Structure](#-repository-directory-structure)
- [🚀 Step-by-Step Quickstart Guide](#-step-by-step-quickstart-guide)
- [🚢 Production Deployment](#-production-deployment-railway-vercel--docker)
- [⚙️ Configuration & Customization](#️-configuration--customization)
- [📚 References & Documentation](#-references--documentation)

---

## 📌 Project Overview

**KisanMitra AI (किसान मित्र AI)** is a production-grade, ultra-low-latency Voice AI Agricultural Assistant designed specifically for Indian farmers. 

Built on the **LiveKit Agents v1.4** framework, KisanMitra provides real-time, bi-directional voice conversations in Hindi and Hinglish by synchronizing:

1. 🗣️ **Murf Falcon TTS** — The fastest streaming TTS (<130ms TTFB) with natural Indian conversational pacing (`Samar` voice).
2. 🎙️ **Deepgram Nova-3 STT** — Multilingual speech-to-text with smart punctuation and high accuracy for Indian regional accents.
3. 🧠 **Google Gemini 2.5/Flash-Lite** — Fast reasoning with function calling for tool execution.
4. 💾 **Persistent SQLite Memory** — State machine for farmer onboarding, consent-based profile storage, and proactive zero-roundtrip greetings.
5. 🌩️ **Intelligent Tool Chaining** — Live weather data fetching (`wttr.in`) with automated district resolution from memory.
6. 🛡️ **Resilient Local Fallback Engine (`RobustKisanLLM`)** — Sub-50ms local agronomic response engine ensuring 0% call dropouts during LLM API timeouts or rate limits.

---

## 🗓️ 5-Day Engineering Journey

```mermaid
timeline
    title KisanMitra AI 5-Day Evolution
    Day 1 : Foundation & Setup : LiveKit Agents SDK v1.4, WebRTC Audio Loop, Deepgram STT, Gemini LLM, Murf Falcon TTS
    Day 2 : Voice Tuning & Latency : Samar Voice, Sentence Tokenizer, <150ms TTFB, BVC Noise Cancellation
    Day 3 : Krishi Sahayak Persona : 15+ Crops, Disease/Pest Dosages, NPK Fertilizers, PM-Kisan & Kusum Subsidies
    Day 4 : Persistent Memory (SQLite) : User Profiles, Consent-Based Saving, State Machine, Proactive Greetings
    Day 5 : Tool Chaining & Resilience : wttr.in Weather API, Auto District Lookup, RobustKisanLLM Fallback, Pytest Suite

flowchart TD
    User([🎙️ Farmer Speaks - Hindi / Hinglish]) -->|WebRTC Audio Stream| LK[LiveKit Real-Time Gateway]
    LK -->|Audio Buffer| NC[LiveKit Noise Cancellation - BVC]
    NC -->|Denoised Audio| VAD[Silero VAD + Multilingual Turn Detector]
    VAD -->|Voice Activity Stream| STT[Deepgram Nova-3 STT]
    
    STT -->|Transcript| Agent[KisanMitra Assistant / AgentSession]
    
    subgraph Core Intelligence & Memory Layer
        Agent <-->|Read / Write Profile| DB[(SQLite: kisan_mitra.db)]
        Agent <-->|Live Forecast API| Wttr[wttr.in Weather API]
        Agent <-->|Reasoning & Tool Calls| LLM[Google Gemini 2.5/Flash-Lite]
        LLM -.->|Fallback on API Timeout| Robust[RobustKisanLLM Engine]
    end
    
    Agent -->|Response Text Stream| TTS[Murf Falcon TTS - Samar Voice]
    TTS -->|Synthesized Audio Stream| LK
    LK -->|Audio Output| Speaker([🔊 Farmer Hears Natural Audio <130ms])

    style User fill:#2D3748,stroke:#4A5568,color:#fff
    style LK fill:#002cf2,stroke:#3B82F6,color:#fff
    style STT fill:#13EF93,stroke:#10B981,color:#000
    style LLM fill:#4285F4,stroke:#60A5FA,color:#fff
    style DB fill:#F59E0B,stroke:#D97706,color:#000
    style Wttr fill:#3B82F6,stroke:#2563EB,color:#fff
    style TTS fill:#6366F1,stroke:#818CF8,color:#fff
    style Speaker fill:#2D3748,stroke:#4A5568,color:#fff
    style Robust fill:#10B981,stroke:#059669,color:#fff

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    language_preference TEXT DEFAULT 'Hindi',
    facts TEXT, -- JSON: {"district": "Patna", "crop": "Potato", "land_size": "2 acres"}
    last_interaction TIMESTAMP
);

stateDiagram-v2
    [*] --> Connect: Farmer Joins WebRTC Room
    Connect --> CheckDB: Lookup user_id in SQLite
    
    CheckDB --> State1_NewUser: Profile Not Found
    CheckDB --> State2_ReturningUser: Profile Exists
    
    state State1_NewUser {
        [*] --> GreetNew: "नमस्ते! मैं आपका किसान मित्र हूँ..."
        GreetNew --> CollectInfo: Gather Name, District, Crop, Land Size
        CollectInfo --> AskConsent: "क्या मैं अगली बार के लिए आपकी यह जानकारी सेव कर लूँ?"
        AskConsent --> SaveProfile: Farmer Agrees
        SaveProfile --> DBWrite: Call save_user_profile()
        DBWrite --> [*]
    }
    
    state State2_ReturningUser {
        [*] --> ProactiveGreet: "नमस्ते [Name], पिछली बार हमने..."
        ProactiveGreet --> ServeQuery: Answer Crop / Weather Questions
        ServeQuery --> [*]
    }

murf-livekit-starter/
├── backend/
│   ├── src/agent.py              # Core logic: State machine, Tools, LLM fallback
│   ├── tests/                    # Pytest suite for evals and tool chaining
│   ├── kisan_mitra.db            # SQLite persistent database
│   └── Dockerfile                # Production Docker container
├── frontend/
│   ├── app/                      # Next.js UI, LiveKit Room & token generation
│   ├── components/agents-ui/     # Voice visualizers, audio bars & mic controls
│   └── app-config.ts             # Theme, accent colors, and branding
├── start_app.sh                  # All-in-one run script (macOS/Linux)
├── start_app.ps1                 # All-in-one run script (Windows)
└── README.md                     # Complete project documentation

# macOS/Linux
chmod +x start_app.sh
./start_app.sh

# Windows (PowerShell)
.\start_app.ps1
