from dotenv import load_dotenv

from livekit.agents import Agent
from livekit.plugins import (
    groq,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from TTS.local_tts import TTS as LocalTTS

from livekit.agents.tts import StreamAdapter

from livekit.agents import tokenize
import os

import logging
from Tools import calendar_test

logger = logging.getLogger(__name__)



# groq_api_key = os.getenv("GROQ_API_KEY")

class Assistant(Agent):
    def __init__(self, TTS_BASE_URL) -> None:
        logger.info(f"TTS_BASE_URL: {TTS_BASE_URL}")
        super().__init__(
            instructions="You are a helpful voice AI assistant.",
            llm=groq.LLM(model="openai/gpt-oss-120b"),
            stt=groq.STT(model="whisper-large-v3"), 
            tts=StreamAdapter(
                tts=LocalTTS(
                    voice_id="female",
                    language="en",
                    base_url=TTS_BASE_URL
                ),
                sentence_tokenizer=tokenize.basic.SentenceTokenizer()
            ),
            vad=silero.VAD.load(),
            turn_detection=MultilingualModel(),
        )