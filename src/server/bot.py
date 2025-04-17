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
from pipecat.frames.frames import BotSpeakingFrame, LLMFullResponseEndFrame, TTSSpeakFrame, LLMMessagesFrame
import time
from transformers import pipeline as transformers_pipeline
import torch
import numpy as np
import json

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

def clean_visemes(visemes_durations, silence_viseme=0, silence_threshold=0.2, general_threshold=0.05):
    cleaned = []
    skip_next_unwanted_duration = 0.0

    for i, current in enumerate(visemes_durations):
        vis = current["visemes"]
        dur = current["duration"]

        # Merge skipped durations
        if skip_next_unwanted_duration > 0:
            dur += skip_next_unwanted_duration

        # Short viseme or silence
        if (vis == [silence_viseme] and dur < silence_threshold) or dur < general_threshold:
            # Add the pause duration or short viseme duration to next non-silence viseme
            skip_next_unwanted_duration += dur
            continue

        if skip_next_unwanted_duration > 0:
            skip_next_unwanted_duration = 0.0

        cleaned.append({
            "visemes": vis,
            "duration": round(dur, 6)
        })

    return cleaned

async def main():
    """Main entry point for bot execution."""
    load_dotenv(override=True)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    last_activity_time = time.time()  # Initialize last activity time (global variable). 
    # This is used to track the last time anyone in the session spoke. 
    # If no one has spoken for X seconds (X is 15 seconds by default), the bot will generate a message to re-engage the user.
    idle_checker_task = None

    phoneme_viseme_map_file = "./assets/phoneme_viseme_map.json"
    with open(phoneme_viseme_map_file, "r") as f:
        phoneme_viseme_map = json.load(f)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    asr_pipeline = transformers_pipeline(
        "automatic-speech-recognition",
        model="bookbot/wav2vec2-ljspeech-gruut",
        device=device,
        torch_dtype=torch.float16
    )

    print("ASR pipeline loaded on device:", device)
    dummy_audio = np.random.rand(16000).astype(np.int16) * 2 - 1  # values in [-1, 1]
    _ = asr_pipeline(dummy_audio)
    print("ASR pipeline warmed up")

    async def process_visemes_in_thread(audio_bytes, sample_rate, num_channels, phoneme_viseme_map):
        try:
            waveform = np.frombuffer(audio_bytes, dtype=np.int16)

            with torch.inference_mode():
                phonemes = asr_pipeline(waveform.squeeze(), return_timestamps="char")

            visemes_durations = [
                {
                    "visemes": phoneme_viseme_map.get(chunk["text"], []),
                    "duration": round(chunk["timestamp"][1] - chunk["timestamp"][0], 2)
                }
                for chunk in phonemes["chunks"]
            ]

            cleaned_visemes_durations = clean_visemes(visemes_durations)
            # print("cleaned_visemes_durations: ", cleaned_visemes_durations)
            return cleaned_visemes_durations
        except Exception as e:
            print(f"Error processing audio: {e}")
            return None
        
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
                description="Trigger an avatar animation (only one animation at a time).",
                properties={
                    "animation_id": {"type": "string", "enum": ["dance", "wave", "i_dont_know", "none"]},
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
                    "Vocabulary should be from the book of Harry Potter (e.g., philosopher). "
                    "Your output will be converted to audio so don't include special characters or emojis in your answers. " 
                    "Respond to what the user said in a creative and helpful way, but keep your responses brief and concise. " 
                    "Start by introducing yourself and ask if they want to learn a new word. " 
                    "When the user says the right definition or example, congratulate and (sometimes) dance."
                    "When the user joins the room say hi and (sometimes) wave with the hand. "
                    "When you don't know something, you can do the i don't know animation. "
                    "Never say aloud the animation you are going to do. "
                    "You can run only one animation at a time. "
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
        viseme_audiobuffer = AudioBufferProcessor(enable_turn_audio=True,
                                           sample_rate=16000,
                                           buffer_size=0.2 * 1 * 24000 * 2 # sec * channels * sampling_rate * bit_depth
                                           )

        llm.register_function("trigger_animation", handle_animation)

        pipeline_steps = [
            transport.input(),
            rtvi,
            context_aggregator.user(),
            llm,
            tts if tts else None,
            viseme_audiobuffer,
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
                enable_usage_metrics=True
            ),
            observers=[RTVIObserver(rtvi)],
        )

        async def idle_checker(task, interval=1, base_timeout=15):
            global last_activity_time
            idle_counter = 1  # start at 1 to make first timeout = base_timeout
            max_idle_counter = 3  # cannot wait more than 45 seconds

            try:
                while True:
                    await asyncio.sleep(interval)
                    time_since_last = time.time() - last_activity_time
                    current_timeout = idle_counter * base_timeout
                    if time_since_last > current_timeout:
                        logger.info(f"Detected idle timeout after {time_since_last:.1f}s (last activity: {last_activity_time} and current time: {time.time()}, timeout is {current_timeout:.1f}s).")
                        context.add_message({
                            "role": "system",
                            "content": (
                                "The user has been inactive for a while. Based on the current topic, generate a short, friendly message "
                                "to re-engage them. Use the most recent question or word you were discussing as a reference point."
                            )
                        })
                        await task.queue_frame(context_aggregator.assistant().get_context_frame())
                        last_activity_time = time.time()
                        idle_counter += 1
                        if idle_counter > max_idle_counter:
                            idle_counter = 1
            except asyncio.CancelledError:
                logger.info("Idle checker task cancelled.")

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            await save_audio_file(audio, f"{session_dir}/session.wav", sr, ch)

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            global last_activity_time
            last_activity_time = time.time()
            #logger.debug(f"Updated last_activity_time at {last_activity_time} from user audio")
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_USER.wav"
            await save_audio_file(audio, f"{session_dir}/{name}", sr, ch)

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            global last_activity_time
            last_activity_time = time.time()
            #logger.debug(f"Updated last_activity_time at {last_activity_time} from bot audio")
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_AGENT.wav"
            await save_audio_file(audio, f"{session_dir}/{name}", sr, ch)

        @viseme_audiobuffer.event_handler("on_track_audio_data")
        async def on_track_audio_data(buffer, user_audio: bytes, bot_audio: bytes,
            sample_rate: int, num_channels: int):

            start_time = time.time()

            loop = asyncio.get_running_loop()
            visemes_durations = await loop.run_in_executor(
                None,
                lambda: asyncio.run(process_visemes_in_thread(bot_audio, sample_rate, num_channels, phoneme_viseme_map))
            )

            end_time = time.time()
            # logger.info(f"Viseme computation took {end_time - start_time:.6f} seconds")

            if visemes_durations and isinstance(visemes_durations, list) and len(visemes_durations) == 1 and visemes_durations[0]["visemes"] == [0]:
                # logger.info("Skipping visemes-event message due to empty or silent visemes.")
                return

            frame = RTVIServerMessageFrame(
                data={
                    "type": "visemes-event",
                    "payload": visemes_durations
                }
            )
            await rtvi.push_frame(frame)

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            await rtvi.set_bot_ready()

        @transport.event_handler("on_first_participant_joined")
        async def on_participant_joined(_, participant):
            await transport.capture_participant_transcription(participant["id"])
            await viseme_audiobuffer.start_recording()
            await audiobuffer.start_recording()
            global last_activity_time
            last_activity_time = time.time()
            idle_checker_task = asyncio.create_task(idle_checker(task))
        
        @transport.event_handler("on_participant_left")
        async def on_participant_left(_event, participant, _reason):
            print(f"Participant left: {participant}")
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()
            if idle_checker_task:
                idle_checker_task.cancel()
                await asyncio.gather(idle_checker_task, return_exceptions=True)
            await task.cancel()

        await PipelineRunner().run(task)


if __name__ == "__main__":
    asyncio.run(main())
