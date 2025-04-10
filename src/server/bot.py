"""Multimodal bot implementation for real-time speech and video processing.

This module defines a bot that uses a combination of LLMs and TTS engines to teach vocabulary
in a conversational setting. It integrates audio processing, room setup, and animation triggering.
"""

import asyncio
import os
import sys
import datetime
import uuid
import io
import wave

import aiofiles
import aiohttp
from dotenv import load_dotenv
from loguru import logger

from runner import configure
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor, RTVIServerMessageFrame
from pipecat.services.openai import OpenAILLMService, OpenAITTSService
from pipecat.services.openai_realtime_beta import OpenAIRealtimeBetaLLMService, SemanticTurnDetection
from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService
from pipecat.services.ollama import OLLamaLLMService
from pipecat.services.piper import PiperTTSService
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema


async def save_audio_file(audio: bytes, filename: str, sample_rate: int, num_channels: int):
    """Save audio data to a WAV file.

    Args:
        audio (bytes): Audio byte stream.
        filename (str): Output filename.
        sample_rate (int): Audio sample rate.
        num_channels (int): Number of audio channels.
    """
    if len(audio) > 0:
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            async with aiofiles.open(filename, "wb") as file:
                await file.write(buffer.getvalue())
        logger.info(f"Audio saved to {filename}")


def build_llm_and_tts(bot_type: str, session: aiohttp.ClientSession):
    """Construct LLM and TTS services based on configuration.

    Args:
        bot_type (str): Selected bot backend implementation.
        session (aiohttp.ClientSession): HTTP session for API communication.

    Returns:
        tuple: (llm, tts)
    """
    llm, tts = None, None
    bot_type = bot_type.lower().strip()

    if bot_type == "openai":
        llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
        tts = OpenAITTSService(voice="nova", model="gpt-4o-mini-tts")

    elif bot_type == "openai_realtime_beta":
        llm = OpenAIRealtimeBetaLLMService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-realtime-preview-2024-12-17",
            start_audio_paused=False,
            send_transcription_frames=True,
            turn_detection=SemanticTurnDetection(),
        )

    elif bot_type == "gemini":
        llm = GeminiMultimodalLiveLLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            voice_id="Charon",
            transcribe_user_audio=True,
            transcribe_model_audio=True,
        )

    elif bot_type == "opensource":
        llm = OLLamaLLMService(model="llama3.2")
        tts = PiperTTSService(base_url="http://localhost:5001/", aiohttp_session=session)

    else:
        raise ValueError(f"Invalid BOT_IMPLEMENTATION: {bot_type}")

    return llm, tts


async def main():
    """Main entry point for bot execution."""
    load_dotenv(override=True)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    async with aiohttp.ClientSession() as session:
        room_url, token = await configure(session)
        session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
        session_dir = f"recordings/{session_id}"
        os.makedirs(session_dir, exist_ok=True)

        transport = DailyTransport(
            room_url,
            token,
            "Avatar",
            DailyParams(
                audio_out_enabled=True,
                camera_out_enabled=False,
                audio_in_filter=NoisereduceFilter(),
                vad_enabled=True,
                vad_audio_passthrough=True,
                vad_analyzer=SileroVADAnalyzer(),
                transcription_enabled=True,
            ),
        )

        tools = ToolsSchema(standard_tools=[
            FunctionSchema(
                name="trigger_animation",
                description="Trigger an avatar animation",
                properties={
                    "animation_id": {"type": "string", "enum": ["dance", "none"]},
                    "timing": {"type": "string", "enum": ["start"]},
                },
                required=["animation_id", "timing"],
            )
        ])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Voicebot, a friendly, helpful robot. Your name is KIVA. Your goal is to teach to 5-graders new vocabulary." 
                    "Your output will be converted to audio so don't include special characters or emojis in your answers. " 
                    "Respond to what the user said in a creative and helpful way, but keep your responses brief. " 
                    "Start by introducing yourself and ask if they want to learn a new word. " 
                    "When the user says the right definition or example, congratulate and (sometimes) dance."
                ),
            },
        ]

        bot_impl = os.getenv("BOT_IMPLEMENTATION", "openai")
        llm, tts = build_llm_and_tts(bot_impl, session)

        context = OpenAILLMContext(messages=messages, tools=tools)
        context_aggregator = llm.create_context_aggregator(context)

        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        async def handle_animation(function_name, tool_call_id, args, llm, context, result_callback):
            """Trigger avatar animation from LLM function call.

            Args:
                function_name (str): Name of the function.
                tool_call_id (str): Tool call ID.
                args (dict): Arguments for the function.
                llm (BaseLLM): Language model instance.
                context (OpenAILLMContext): LLM context.
                result_callback (Callable): Callback for returning result.
            """
            animation_id = args.get("animation_id", "none")
            timing = args.get("timing", "start")
            print(f"Triggering animation: {animation_id} at {timing}")

            if animation_id != "none":
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "animation-event",
                        "payload": {"animation_id": animation_id, "timing": timing},
                    }
                )
                await rtvi.push_frame(frame)

            await result_callback({"status": "animation_triggered"})


        audiobuffer = AudioBufferProcessor(enable_turn_audio=True)

        llm.register_function("trigger_animation", handle_animation)

        pipeline_steps = [
            transport.input(),
            rtvi,
            context_aggregator.user(),
            llm,
            tts if tts else None,
            transport.output(),
            audiobuffer,
            context_aggregator.assistant(),
        ]
        pipeline = Pipeline([step for step in pipeline_steps if step])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi)],
        )

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            await save_audio_file(audio, f"{session_dir}/session.wav", sr, ch)

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_USER.wav"
            await save_audio_file(audio, f"{session_dir}/{name}", sr, ch)

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_AGENT.wav"
            await save_audio_file(audio, f"{session_dir}/{name}", sr, ch)

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            await rtvi.set_bot_ready()

        @transport.event_handler("on_first_participant_joined")
        async def on_participant_joined(_, participant):
            await transport.capture_participant_transcription(participant["id"])
            await audiobuffer.start_recording()
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @transport.event_handler("on_participant_left")
        async def on_participant_left(_event, participant, _reason):
            print(f"Participant left: {participant}")
            await audiobuffer.stop_recording()
            await task.cancel()

        await PipelineRunner().run(task)


if __name__ == "__main__":
    asyncio.run(main())
