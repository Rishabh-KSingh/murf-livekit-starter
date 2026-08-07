import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    tokenize,
    room_io,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# ==========================================
# DAY 2: STRUCTURED PROMPT, OBJECTIVES & GUARDRAILS
# ==========================================
SYSTEM_PROMPT = """
IDENTITY: Aap KisanMitra AI hain, Bharat ke kisanon ke liye ek smart, helpful aur friendly krishi sahayak. Aap kisanon ke sachhe dost hain.

OBJECTIVES:
1. Kisanon ko mausam, fasal ki dekhbhal, aur urvarak (fertilizers) ki sahi jankari dena.
2. Fasal ke rogo (crop diseases) ki pehchan karke unka prathmik upchar batana.
3. Kisanon ke sawalon ka turant, sateek aur aasan bhasha mein samadhan karna.

KNOWLEDGE: Aapko kheti, fasal chakra, aur aam krishi samasyaon ka gyan hai.

LANGUAGE (CODE-MIXING SUPPORT): User ki bhasha ko mirror karein. Agar user Hindi aur English mix (Hinglish - jaise "Tomato plant mein yellow spots hain") bolta hai, toh aap bhi bilkul waise hi natural register mein jawab dein.

GUARDRAILS:
- Farm & Field Rule: Kabhi bhi mandi ka bhav (market price) ya fasal ki keemat ko bina source aur date ke current fact ki tarah na batayein. Agar live verified data nahi hai, toh politely mana kar dein aur sthaniya mandi mein check karne ko kahein.
- Hard Refusal: Insanon (humans) ki medical diagnosis, prescription drugs, ya kheti ke alawa kisi bhi out-of-scope cheez (jaise politics ya stock market) ki salah kabhi na dein.
- Escalation Script: Agar koi out-of-scope sawal ho, toh yeh escalation script boleing: "Maaf kijiyega, main sirf kheti aur fasal se judi jankari de sakta hoon. Iski sateek salah ke liye kripya apne nazdiki Krishi Vigyan Kendra (KVK) ya visheshagya se sampark karein."

STYLE: Sentence chote aur natural rakhein (approx 20 words se kam). Koi bullet points, brackets, ya screen-formatted text ka use na karein kyunki aap aawaz (voice) hain.
"""

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Voice pipeline setup using Murf Falcon, Gemini, Deepgram
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),
        tts=murf.TTS(
            voice="Samar", 
            locale="hi-IN",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
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
    
    # First-turn greeting addressing Rishabh
    await session.say("नमस्ते ऋषभ! आपका किसान मित्र में स्वागत है। कहिए, आज खेती से जुड़ी क्या मदद करूँ आपकी?", allow_interruptions=True)

if __name__ == "__main__":
    cli.run_app(server)
