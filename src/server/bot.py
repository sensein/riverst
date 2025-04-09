""" This module implements a multimodal bot (speech and video). 

The bot runs as part of a pipeline that processes audio/video frames and manages
the conversation flow.
"""

import asyncio
import os
import sys
import aiohttp
from dotenv import load_dotenv
from loguru import logger
from runner import configure
from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.services.openai import OpenAILLMService, OpenAITTSService
from pipecat.transports.services.daily import DailyParams, DailyTransport
from pipecat.services.openai_realtime_beta import OpenAIRealtimeBetaLLMService, SemanticTurnDetection
from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
import io
import wave
import datetime
import aiofiles
import uuid
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

async def save_audio_file(audio: bytes, filename: str, sample_rate: int, num_channels: int):
    """Save audio data to a WAV file."""
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

async def main():
    """Main bot execution function."""

    load_dotenv(override=True)
    logger.remove(0)
    logger.add(sys.stderr, level="DEBUG")

    async with aiohttp.ClientSession() as session:
        (room_url, token) = await configure(session)

        # Generate a unique session_id
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

        trigger_animation_function = FunctionSchema(
            name="trigger_animation",
            description="Trigger an avatar animation",
            properties={
                "animation_id": {
                    "type": "string",
                    "enum": ["dance", "none"],
                    "description": "Type of animation to play"
                },
                "timing": {
                    "type": "string",
                    "enum": ["start"],
                    "description": "When to play the animation"
                }
            },
            required=["animation_id", "timing"]
        )
        tools = ToolsSchema(standard_tools=[trigger_animation_function])

        messages = [
            {
                "role": "system",
                "content": "You are Voicebot, a friendly, helpful robot. Your name is KIVA. Your goal is to teach to 5-graders new vocabulary. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way, but keep your responses brief. Start by introducing yourself and ask if they want to learn a new word. When the user says the right definition or example, congratulate and (sometimes) dance."
            },
        ]

        bot_implementation = os.getenv("BOT_IMPLEMENTATION", "openai").lower().strip()  
        print(f"BOT_IMPLEMENTATION: {bot_implementation}")  
        tts = None  # Initialize tts to None to avoid potential unassigned usage
        if bot_implementation == "openai":
            print("Using OpenAI LLM service")
            # Initialize LLM service
            llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
            tts = OpenAITTSService(
                voice="nova",
                model="gpt-4o-mini-tts",
            )
        elif bot_implementation == "openai_realtime_beta":
            print("Using OpenAI Realtime Beta LLM service")
            llm = OpenAIRealtimeBetaLLMService(
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4o-realtime-preview-2024-12-17",
                start_audio_paused=False,
                send_transcription_frames=True,
                turn_detection=SemanticTurnDetection(),
            )
        elif bot_implementation == "gemini":
            print("Using Gemini LLM service")
            llm = GeminiMultimodalLiveLLMService(
                api_key=os.getenv("GEMINI_API_KEY"),
                voice_id="Puck",  # Aoede, Charon, Fenrir, Kore, Puck
                transcribe_user_audio=True,
                transcribe_model_audio=True,
            )
        else:
            raise ValueError(
                f"Invalid BOT_IMPLEMENTATION: {bot_implementation}. Must be 'openai', 'openai_realtime_beta', or 'gemini'"
            )

        # Set up conversation context and management
        # The context_aggregator will automatically collect conversation context
        context = OpenAILLMContext(
            messages=messages,
            tools=tools
        )
        context_aggregator = llm.create_context_aggregator(context)

        #
        # RTVI events for Pipecat client UI
        #
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        # Create an audio buffer processor
        audiobuffer = AudioBufferProcessor(enable_turn_audio=True)


        async def handle_animation(function_name, tool_call_id, args, llm, context, result_callback):
            animation_id = args.get("animation_id", "none")
            timing = args.get("timing", "start")
            print(f"Triggering animation: {animation_id} at {timing}")
            
            if animation_id != "none":
                # send to avatar client (e.g., via websocket)
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "animation-event",
                        "payload": {"animation_id": animation_id, "timing": timing},
                    }
                )
                await rtvi.push_frame(frame)
            
            await result_callback({"status": "animation_triggered"})
            
        llm.register_function("trigger_animation", handle_animation)


        if tts:
            pipeline = Pipeline(
                [
                    transport.input(),
                    rtvi,
                    context_aggregator.user(),
                    llm,
                    tts,
                    transport.output(),
                    audiobuffer,
                    context_aggregator.assistant(),
                ]
            )
        else:
            pipeline = Pipeline(
                [
                    transport.input(),
                    rtvi,
                    context_aggregator.user(),
                    llm,
                    transport.output(),
                    audiobuffer,
                    context_aggregator.assistant(),
                ]
            )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi)],
        )

        # Handler for merged session audio
        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(buffer, audio, sample_rate, num_channels):
            session_path = f"{session_dir}/session.wav"
            await save_audio_file(audio, session_path, sample_rate, num_channels)

        # Handler for user audio
        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_turn_audio_data(buffer, audio, sample_rate, num_channels):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{session_dir}/{timestamp}_USER.wav"
            await save_audio_file(audio, filename, sample_rate, num_channels)

        # Handler for bot/agent audio
        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_turn_audio_data(buffer, audio, sample_rate, num_channels):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{session_dir}/{timestamp}_AGENT.wav"
            await save_audio_file(audio, filename, sample_rate, num_channels)

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            await rtvi.set_bot_ready()

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            await transport.capture_participant_transcription(participant["id"])
            await audiobuffer.start_recording()
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @transport.event_handler("on_participant_left")
        async def on_participant_left(_event, participant, _reason):
            print(f"Participant left: {participant}")
            await audiobuffer.stop_recording()
            await task.cancel()

        runner = PipelineRunner()

        await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())