from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, RoomInputOptions
from livekit.plugins import (
    noise_cancellation,
)

from agent import Assistant
import os


load_dotenv(".env.local")
TTS_BASE_URL = os.getenv("TTS_BASE_URL")

print("Starting the Assistant...")

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()

    await session.start(
        room=ctx.room,
        agent=Assistant(TTS_BASE_URL=TTS_BASE_URL),
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` instead for best results
            noise_cancellation=noise_cancellation.BVC(), 
        ),
    )

    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))