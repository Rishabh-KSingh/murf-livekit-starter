import asyncio
import logging
import os
import sys

import livekit.api as api
from dotenv import load_dotenv

logger = logging.getLogger("trigger_outbound")

# 1. Load environment variables from .env.local
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_LOCAL_PATH = os.path.join(BACKEND_DIR, ".env.local")
if os.path.exists(ENV_LOCAL_PATH):
    load_dotenv(ENV_LOCAL_PATH)
else:
    load_dotenv()


def normalize_sip_call_to(destination: str) -> str:
    """Normalizes the destination for LiveKit's CreateSIPParticipant API.

    LiveKit expects SipCallTo to be a phone number (e.g. +91...) or a SIP username
    (e.g. 'rishabh_kisan1'), not the full 'sip:user@domain' URI scheme because
    the domain/address is already handled by the SIP Trunk configuration.
    """
    cleaned = destination.strip()
    if cleaned.lower().startswith("sip:"):
        cleaned = cleaned[4:]
    if "@" in cleaned:
        cleaned = cleaned.split("@")[0]
    return cleaned


async def trigger_outbound_call(
    sip_trunk_id: str | None = None,
    destination_number: str | None = None,
    room_name: str = "kisan-outbound-alert",
) -> api.SIPParticipantInfo | None:
    """Dispatches an outbound SIP call via LiveKit using a Generic SIP Trunk (e.g., Linphone).

    Reads SIP_TRUNK_ID and DESTINATION_NUMBER from .env.local and creates
    a SIP participant in the 'kisan-outbound-alert' room.
    """
    trunk_id = sip_trunk_id or os.getenv("SIP_TRUNK_ID")
    raw_destination = destination_number or os.getenv("DESTINATION_NUMBER")
    livekit_url = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")

    # Validation checks with informative error output
    if not livekit_url or not livekit_api_key or not livekit_api_secret:
        print("❌ ERROR: Missing LiveKit credentials.")
        print(
            "   Please ensure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are set in .env.local"
        )
        return None

    if not trunk_id or not str(trunk_id).strip():
        print("❌ ERROR: SIP_TRUNK_ID is not configured in .env.local.")
        print("   Please configure a valid Generic SIP Trunk ID (e.g. ST_xxxxxx).")
        return None

    if not raw_destination or not str(raw_destination).strip():
        print("❌ ERROR: DESTINATION_NUMBER is not configured in .env.local.")
        print(
            "   Please configure a valid destination (e.g. rishabh_kisan1 or sip:rishabh_kisan1@sip.linphone.org)."
        )
        return None

    # Normalize SIP URI / user to prevent LiveKit 400 invalid_argument error
    sip_user = normalize_sip_call_to(raw_destination)

    print("==================================================")
    print("📞 KisanMitra AI — Generic SIP (Linphone) Outbound Caller")
    print("==================================================")
    print(f"📡 SIP Trunk ID       : {trunk_id}")
    print(f"🌐 Target Destination : {raw_destination}")
    print(f"👤 Resolved SIP User  : {sip_user}")
    print(f"🏠 Target Room        : {room_name}")
    print("--------------------------------------------------")
    print(f"⏳ Dialing '{sip_user}' via LiveKit Generic SIP Trunk...")

    try:
        async with api.LiveKitAPI(
            url=livekit_url,
            api_key=livekit_api_key,
            api_secret=livekit_api_secret,
        ) as lkapi:
            # 1. Clean up any lingering ghost room/participants from previous calls
            try:
                await lkapi.room.delete_room(api.DeleteRoomRequest(room=room_name))
                await asyncio.sleep(0.3)
            except Exception:
                pass

            # 2. Explicitly dispatch a single AI Agent to the fresh room
            try:
                dispatch_req = api.CreateAgentDispatchRequest(
                    agent_name="my-agent",
                    room=room_name,
                )
                await lkapi.agent_dispatch.create_dispatch(dispatch_req)
                print(f"🤖 Agent 'my-agent' dispatched to room '{room_name}'.")
            except Exception as e:
                logger.debug(f"Agent dispatch notice: {e}")

            # 3. Create the SIP participant to place the outbound call immediately
            req = api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=sip_user,
                room_name=room_name,
                participant_identity=f"sip_{sip_user}",
                participant_name=f"Farmer ({sip_user})",
            )
            participant_info = await lkapi.sip.create_sip_participant(req)

            print("✅ Call successfully dispatched instantly!")
            print(f"   Participant ID       : {participant_info.participant_id}")
            print(f"   Participant Identity : {participant_info.participant_identity}")
            print(f"   Dialed User          : {sip_user}")
            print(f"   Room Assigned        : {room_name}")
            print("==================================================")
            return participant_info

    except Exception as exc:
        print(f"❌ ERROR: Failed to dispatch outbound call to {sip_user}: {exc}")
        print("==================================================")
        return None


def main() -> None:
    """Entrypoint to trigger the outbound SIP call from the command line."""
    custom_trunk = sys.argv[1] if len(sys.argv) > 1 else None
    custom_dest = sys.argv[2] if len(sys.argv) > 2 else None
    custom_room = sys.argv[3] if len(sys.argv) > 3 else "kisan-outbound-alert"

    asyncio.run(
        trigger_outbound_call(
            sip_trunk_id=custom_trunk,
            destination_number=custom_dest,
            room_name=custom_room,
        )
    )


if __name__ == "__main__":
    main()
