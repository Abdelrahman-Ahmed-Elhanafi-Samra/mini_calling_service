
from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import os
import weakref
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp
from livekit import rtc
from livekit.agents import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    tokenize,
    tts,
    utils,
)
# from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    NotGivenOr,
)
from livekit.agents.utils import is_given
from livekit.plugins.elevenlabs import logger,TTSEncoding, TTSModels


_Encoding = Literal["mp3", "pcm"]
_DefaultEncoding: TTSEncoding = "mp3_22050_32"
DEFAULT_VOICE_ID = "male"
API_BASE_URL_V1 = os.getenv("XTTS_BASE_URL", "http://31.130.207.73:8020")
AUTHORIZATION_HEADER = "xi-api-key"
WS_INACTIVITY_TIMEOUT = 300


def _sample_rate_from_format(output_format: TTSEncoding) -> int:
    return int(output_format.split("_")[1])


def _encoding_from_format(output_format: TTSEncoding) -> _Encoding:
    if output_format.startswith("mp3"):
        return "mp3"
    elif output_format.startswith("pcm"):
        return "pcm"
    raise ValueError(f"Unknown format: {output_format}")


@dataclass
class VoiceSettings:
    stability: float
    similarity_boost: float
    style: NotGivenOr[float] = NOT_GIVEN
    speed: NotGivenOr[float] = NOT_GIVEN
    use_speaker_boost: NotGivenOr[bool] = NOT_GIVEN


@dataclass
class Voice:
    id: str
    name: str
    category: str


@dataclass
class _TTSOptions:
    api_key: str
    voice_id: str
    voice_settings: NotGivenOr[VoiceSettings]
    model: TTSModels | str
    language: NotGivenOr[str]
    base_url: str
    encoding: TTSEncoding
    sample_rate: int
    streaming_latency: NotGivenOr[int]
    word_tokenizer: tokenize.WordTokenizer
    chunk_length_schedule: NotGivenOr[list[int]]
    enable_ssml_parsing: bool
    inactivity_timeout: int


class TTS(tts.TTS):
    def __init__(
        self,
        *,
        voice_id: str = DEFAULT_VOICE_ID,
        voice_settings: NotGivenOr[VoiceSettings] = NOT_GIVEN,
        model: TTSModels | str = "xtts_v2",
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        streaming_latency: NotGivenOr[int] = NOT_GIVEN,
        inactivity_timeout: int = WS_INACTIVITY_TIMEOUT,
        word_tokenizer: NotGivenOr[tokenize.WordTokenizer] = NOT_GIVEN,
        enable_ssml_parsing: bool = False,
        chunk_length_schedule: NotGivenOr[list[int]] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        language: NotGivenOr[str] = NOT_GIVEN,
    ) -> None:
        if not is_given(encoding):
            encoding = _DefaultEncoding

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=_sample_rate_from_format(encoding),
            num_channels=1,
        )

        elevenlabs_api_key = api_key if is_given(api_key) else os.environ.get("XTTS_API_KEY", "1234567890")
        if not elevenlabs_api_key:
            raise ValueError("Missing API key")

        if not is_given(word_tokenizer):
            word_tokenizer = tokenize.basic.WordTokenizer(ignore_punctuation=True)

        self._opts = _TTSOptions(
            voice_id=voice_id,
            voice_settings=voice_settings,
            model=model,
            api_key=elevenlabs_api_key,
            base_url=base_url if is_given(base_url) else API_BASE_URL_V1,
            encoding=encoding,
            sample_rate=self.sample_rate,
            streaming_latency=streaming_latency,
            word_tokenizer=word_tokenizer,
            chunk_length_schedule=chunk_length_schedule,
            enable_ssml_parsing=enable_ssml_parsing,
            language=language,
            inactivity_timeout=inactivity_timeout,
        )
        self._session = http_session
        self._streams = weakref.WeakSet()

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()
        return self._session

    async def list_voices(self) -> list[Voice]:
        async with self._ensure_session().get(
            f"{self._opts.base_url}/speakers_list",
            headers={AUTHORIZATION_HEADER: self._opts.api_key},
        ) as resp:
            data = await resp.json()
            return [Voice(id=spk, name=spk, category="custom") for spk in data]

    def synthesize(self, text: str, conn_options: Any = DEFAULT_API_CONNECT_OPTIONS) -> tts.ChunkedStream:
        
        return ChunkedStream(
            tts=self,
            input_text=text,
            conn_options=DEFAULT_API_CONNECT_OPTIONS,
            opts=self._opts,
            session=self._ensure_session(),
        )


class ChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: TTS,
        input_text: str,
        opts: _TTSOptions,
        conn_options: Any,
        session: aiohttp.ClientSession,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._opts, self._session = opts, session

    async def _run(self) -> None:
        request_id = utils.shortuuid()
        decoder = utils.codecs.AudioStreamDecoder(
            sample_rate=self._opts.sample_rate, num_channels=1
        )

        try:
            async with self._session.get(
                _synthesize_url(self._opts, self._input_text),
                headers={AUTHORIZATION_HEADER: self._opts.api_key},
            ) as resp:
                if not resp.content_type.startswith("audio/"):
                    content = await resp.text()
                    logger.error("XTTS returned non-audio data: %s", content)
                    return

                async for chunk, _ in resp.content.iter_chunks():
                    decoder.push(chunk)

                decoder.end_input()
                emitter = tts.SynthesizedAudioEmitter(
                    event_ch=self._event_ch, request_id=request_id
                )
                async for frame in decoder:
                    emitter.push(frame)
                emitter.flush()
        except Exception as e:
            raise APIConnectionError() from e


def _synthesize_url(opts: _TTSOptions, text: str) -> str:
    import urllib.parse
    safe_text = urllib.parse.quote(text)
    speaker_param = f"{opts.voice_id}.wav" if not opts.voice_id.endswith(".wav") else opts.voice_id
    lang = opts.language if opts.language else "en"
    return (
        f"{opts.base_url}/tts_stream?"
        f"text={safe_text}&speaker_wav={speaker_param}&language={lang}"
    )