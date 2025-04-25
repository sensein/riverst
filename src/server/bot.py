import os
import sys

import cv2
import numpy as np
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, InputImageRawFrame, OutputImageRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor, RTVIServerMessageFrame
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport

from pipecat.processors.user_idle_processor import UserIdleProcessor
import aiofiles
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import EndFrame, LLMMessagesFrame, TTSSpeakFrame

from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
import io
import wave
import datetime
import time
import asyncio
import uuid
import torch
from transformers import pipeline as transformers_pipeline
import json
from pipecat.services.openai import OpenAILLMService, OpenAITTSService
from pipecat.services.openai_realtime_beta import OpenAIRealtimeBetaLLMService, SemanticTurnDetection
from pipecat.services.ollama import OLLamaLLMService
from pipecat.services.piper import PiperTTSService
import aiohttp
from pipecat.services.whisper.stt import WhisperSTTService, Model

load_dotenv(override=True)


def build_llm_and_tts(bot_type: str, session: aiohttp.ClientSession):
    """Construct LLM and TTS services based on configuration.

    Args:
        bot_type (str): Selected bot backend implementation.
        session (aiohttp.ClientSession): HTTP session for API communication.

    Returns:
        tuple: (llm, tts)
    """
    llm, tts, stt = None, None, None
    bot_type = bot_type.lower().strip()

    if bot_type == "openai":
        stt = OpenAISTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-transcribe",
        )
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
            api_key=os.getenv("GOOGLE_API_KEY"),
            voice_id="Charon",
            transcribe_user_audio=True,
            transcribe_model_audio=True,
        )
        # sad story for now
        # https://github.com/pipecat-ai/pipecat-flows/issues/66
        # TODO: make sure to integate this when they implement it

    elif bot_type == "opensource":
        stt = WhisperSTTService()
        llm = OLLamaLLMService(model="llama3.2")
        tts = PiperTTSService(base_url="http://localhost:5001/", aiohttp_session=session)
        # TODO: check if this works now!!!

    else:
        raise ValueError(f"Invalid BOT_IMPLEMENTATION: {bot_type}")

    return llm, tts, stt


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


class EdgeDetectionProcessor(FrameProcessor):
    def __init__(self, camera_out_width, camera_out_height: int):
        super().__init__()
        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            # Convert bytes to NumPy array
            img = np.frombuffer(frame.image, dtype=np.uint8).reshape(
                (frame.size[1], frame.size[0], 3)
            )

            # perform edge detection
            img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)

            # convert the size if needed
            desired_size = (self._camera_out_width, self._camera_out_height)
            if frame.size != desired_size:
                resized_image = cv2.resize(img, desired_size)
                frame = OutputImageRawFrame(resized_image.tobytes(), desired_size, frame.format)
                await self.push_frame(frame)
            else:
                await self.push_frame(
                    OutputImageRawFrame(image=img.tobytes(), size=frame.size, format=frame.format)
                )
        else:
            await self.push_frame(frame, direction)


SYSTEM_INSTRUCTION = f"""
"You are KIVA Chatbot, a friendly, helpful robot.

Your goal is to demonstrate your vocabulary teching skills in a succinct way.

Your output will be converted to audio so don't include special characters in your answers.

Respond to what the user said in a creative and helpful way. Keep your responses brief. One or two sentences at most.

You are only allowed to call one function: 'trigger_animation', if you want to trigger a supported animation.

Start with a friendly greeting and ask how you can help the user.
"""


async def run_bot(webrtc_connection):

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
        def clean_visemes(visemes_durations, silence_viseme=0, silence_threshold=0.2, general_threshold=0.05):
            cleaned = []
            skip_next_unwanted_duration = 0.0

            for _, current in enumerate(visemes_durations):
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

    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
    session_dir = f"recordings/{session_id}"
    os.makedirs(session_dir, exist_ok=True)


    transport_params = TransportParams(
        camera_in_enabled=True,
        camera_out_enabled=True,
        camera_out_is_live=True,
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_filter=NoisereduceFilter(),

        vad_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
        vad_audio_passthrough=True,
        audio_out_10ms_chunks=4,
    )

    pipecat_transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection, params=transport_params
    )

    audiobuffer = AudioBufferProcessor(enable_turn_audio=True)
    viseme_audiobuffer = AudioBufferProcessor(enable_turn_audio=True,
                                        sample_rate=16000,
                                        buffer_size=0.2 * 1 * 24000 * 2 # sec * channels * sampling_rate * bit_depth
                                        )

    async with aiohttp.ClientSession() as session:
        bot_impl = os.getenv("BOT_IMPLEMENTATION", "opensource")
        print("bot_impl: ", bot_impl)
        llm, tts, stt = build_llm_and_tts(bot_impl, session=session)

        tools = ToolsSchema(standard_tools=[
            FunctionSchema(
                name="trigger_animation",
                description="Trigger an avatar animation (only one animation at a time).",
                properties={
                    "animation_id": {"type": "string", 
                                     "enum": ["dance", "wave", "i_dont_know", "none"],
                                     "description": "The animation ID to trigger."},
                    "timing": {"type": "string", 
                               "enum": ["start"],
                               "description": "The timing of the animation."},
                },
                required=["animation_id", "timing"],
            )
        ])

        messages=[
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTION,
            }
        ]

        context = OpenAILLMContext(
            messages=messages,
            tools=tools
        )

        context_aggregator = llm.create_context_aggregator(context=context)

        # RTVI events for Pipecat client UI
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

        llm.register_function("trigger_animation", handle_animation)

        async def handle_user_idle(user_idle: UserIdleProcessor, retry_count: int) -> bool:
            if retry_count == 1:
                # First attempt: Gentle reminder
                print("User has been idle for a while. Sending a gentle reminder #1.")
                context.add_message({
                    "role": "system",
                    "content": "The user has been quiet. Politely and briefly ask if they're still there."
                })
                await task.queue_frame(context_aggregator.assistant().get_context_frame())
                return True
            elif retry_count == 2:
                # Second attempt: Direct prompt
                print("User has been idle for a while. Sending a gentle reminder #2.")
                context.add_message({
                    "role": "system",
                    "content": "The user is still inactive. Ask if they'd like to continue our conversation."
                })
                await task.queue_frame(context_aggregator.assistant().get_context_frame())
                return True
            elif retry_count == 3:
                # Third attempt: Direct prompt #2
                print("User has been idle for a while. Ending the conversation.")
                context.add_message({
                    "role": "system",
                    "content": "The user is still inactive. It seems like they are busy right now. Wish them a nice day!"
                })
                await task.queue_frame(context_aggregator.assistant().get_context_frame())
                return True
            else:
                # Fourth attempt: End conversation
                print("User has been idle for a while. Actually ending the conversation.")
                await task.queue_frame(EndFrame())
                return False  # Stop monitoring

        # Create the processor
        user_idle = UserIdleProcessor(
            callback=handle_user_idle,
            timeout=10.0
        )

        if tts:
            pipeline = Pipeline(
                [
                    pipecat_transport.input(),
                    rtvi,
                    ParallelPipeline(
                        [
                            EdgeDetectionProcessor(
                                transport_params.camera_out_width, transport_params.camera_out_height
                            ),  # Sending the video back to the user
                            Pipeline([
                                stt,
                                context_aggregator.user(),
                                llm,
                                tts,
                                viseme_audiobuffer,
                            ])
                        ]
                    ),
                    pipecat_transport.output(),
                    audiobuffer,
                    user_idle,
                    context_aggregator.assistant(),
                ]

                # TODO: sometimes it lags (the audio). i don't know why
            )
        else:
            pipeline = Pipeline(
                [
                    pipecat_transport.input(),
                    context_aggregator.user(),
                    rtvi,
                    llm,  # LLM
                    EdgeDetectionProcessor(
                        transport_params.camera_out_width, transport_params.camera_out_height
                    ),  # Sending the video back to the user
                    viseme_audiobuffer,
                    pipecat_transport.output(),
                    audiobuffer,
                    user_idle,
                    context_aggregator.assistant(),
                ]
            )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_heartbeats=True,

                observers=[RTVIObserver(rtvi)],
            ),
        )

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
            logger.info(f"Viseme computation took {end_time - start_time:.6f} seconds")

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
            logger.info("Pipecat client ready.")
            await rtvi.set_bot_ready()
            # Kick off the conversation.
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @pipecat_transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("Pipecat Client connected")
            await viseme_audiobuffer.start_recording()
            await audiobuffer.start_recording()

        @pipecat_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("Pipecat Client disconnected")
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()

        @pipecat_transport.event_handler("on_client_closed")
        async def on_client_closed(transport, client):
            logger.info("Pipecat Client closed")
            await task.cancel()

        runner = PipelineRunner(handle_sigint=False)

        await runner.run(task)
