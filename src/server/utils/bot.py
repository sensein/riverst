import asyncio
import datetime
import json
import os
import traceback
from typing import Any

import aiohttp
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.processors.filters.stt_mute_filter import (
    STTMuteConfig,
    STTMuteFilter,
    STTMuteStrategy,
)
from pipecat.processors.frameworks.rtvi import (
    RTVIConfig,
    RTVIObserver,
    RTVIProcessor,
    RTVIServerMessageFrame,
)
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.processors.user_idle_processor import UserIdleProcessor
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport

from .audio_analyzer import AudioAnalyzer
from .bot_component_factory import BotComponentFactory
from .flow_component_factory import FlowComponentFactory
from .metrics import MetricsLoggerProcessor
from .transcript_handler import TranscriptHandler
from .utils import save_audio_file
from .video_processor import VideoProcessor
from .animation_handler import AnimationHandler

load_dotenv(override=True)

async def run_bot(
    webrtc_connection: Any,
    config: dict,
    session_dir: str
) -> None:
    """Main function that runs the Pipecat-based bot pipeline.

    Args:
        webrtc_connection (Any): The WebRTC connection instance.
        config (dict): Dictionary containing the bot configuration.
        session_dir (str): Directory to store session artifacts.
    """
    logger.info("Starting bot with config: {}", config)
    logger.info("Session directory: {}", session_dir)

    async with aiohttp.ClientSession() as session:
        # Instantiate the bot components using factory pattern
        factory = BotComponentFactory(
            session_dir=session_dir,
            user_id=config["user_id"],
            modality=config["pipeline_modality"],
            llm_type=config["llm_type"],
            stt_type=config["stt_type"] if "stt_type" in config else None,
            tts_type=config["tts_type"] if "tts_type" in config else None,
            long_term_memory=config.get("long_term_memory", False),
            task_description=config.get("task_description", ""),
            user_description=config.get("user_description", ""),
            avatar_personality_description=config.get("avatar_personality_description", ""),
            avatar_system_prompt=config.get("avatar_system_prompt", ""),
            body_animations=config["body_animations"],
            languages=config["languages"] if "languages" in config else None,
            avatar=config["avatar"]
        )

        stt, llm, tools, instruction, context, context_aggregator, allowed_animations, animation_instruction = await factory.build()
        metrics_logger = MetricsLoggerProcessor(session_dir=session_dir)

        # Setup WebRTC transport parameters
        transport_params = TransportParams(
            video_in_enabled=config.get("video_flag", False),
            video_out_enabled=config.get("video_flag", False),
            video_out_is_live=config.get("video_flag", False),
            video_out_width=config.get("video_out_width", 0),
            video_out_height=config.get("video_out_height", 0),
            video_out_framerate=config.get("video_out_framerate", 0),
            audio_in_enabled=True,
            audio_out_enabled=False,
            audio_in_filter=NoisereduceFilter(),
            vad_analyzer=SileroVADAnalyzer(),
            audio_in_passthrough=True,
            # audio_out_10ms_chunks=4,
        )

        pipecat_transport = SmallWebRTCTransport(webrtc_connection=webrtc_connection, params=transport_params)

        # Audio processors for the raw audio stream
        audiobuffer = AudioBufferProcessor(enable_turn_audio=True)

        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
        
        def function_call_debug_wrapper(fn):
            async def wrapper(params: FunctionCallParams):
                args = params.arguments if isinstance(params, FunctionCallParams) else params
                logger.info("FUNCTION_DEBUG: Function '{}' called with args: {}", fn.__name__, json.dumps(args))
                try:
                    result = await fn(params)
                    logger.info("FUNCTION_DEBUG: Function '{}' completed successfully with result: {}", 
                               fn.__name__, json.dumps(result) if result else "None")
                    return result
                except Exception as e:
                    logger.error("FUNCTION_DEBUG: Error in function '{}': {}", fn.__name__, str(e))
                    logger.error("FUNCTION_DEBUG: {}", traceback.format_exc())
                    
                    result = {
                        "status": "error",
                        "message": f"Execution error in '{fn.__name__}': {str(e)}"
                    }
                    
                    if isinstance(params, FunctionCallParams):
                        await params.result_callback(result)
                    else:
                        return result
            return wrapper

        
        async def animation_handler_wrapper(params):
            """Wrapper for the animation handler to include RTVI instance."""
            return await AnimationHandler.handle_animation(params, rtvi=rtvi, allowed_animations=allowed_animations)

        llm.register_function("trigger_animation", function_call_debug_wrapper(animation_handler_wrapper))       

        async def handle_user_idle(_: UserIdleProcessor, retry_count: int) -> bool:
            """Handle user inactivity by escalating reminders and ending the session if needed.

            Args:
                _ (UserIdleProcessor): The user idle processor instance.
                retry_count (int): The current count of inactivity retries.

            Returns:
                bool: True if monitoring should continue, False if session has ended.
            """
            print(f"User idle handler triggered (retry_count={retry_count}).")
            if retry_count < 2:
                message = "The user has been quiet. Politely follow up on the same topic to keep the conversation going."
            elif retry_count < 4:
                message = "The user is still inactive. Ask if they'd like to continue our conversation."
            elif retry_count < 6:
                message = "Still no response from the user. Wait patiently and let them know you're available if needed."
            elif retry_count < 10:
                message = "No user input detected for a while. Consider ending the session politely if it continues. "
            else:
                # Final attempt: End the session
                print("User has been idle for a while. Actually ending the conversation.")
                await task.queue_frame(EndFrame())
                # TODO: handle the end of the conversation on the client side
                return False  # Stop monitoring

            context.add_message({
                "role": "assistant",
                "content": message,
            })
            await task.queue_frame(context_aggregator.assistant().get_context_frame())
            return True

        # user_idle = UserIdleProcessor(callback=handle_user_idle, timeout=15)
        # TODO: fix the user_idle processor
        # I commented it out for now because it seems to prompt the assistant with random messages
        transcript = TranscriptProcessor()
        transcript_handler = TranscriptHandler(output_file=os.path.join(session_dir, "transcript.json"))

        # Configure with one or more strategies
        stt_mute_processor = STTMuteFilter(
            config=STTMuteConfig(
                strategies={
                    STTMuteStrategy.FIRST_SPEECH, # Mute only during the bot’s first speech utterance. Useful for introductions when you want the bot to complete its greeting before the user can speak.
                }
            ),
        )

        if stt is not None:
            # Note: e2e is faster, but classic is still preferable for now
            steps = [
                    pipecat_transport.input(),
                    rtvi,
                    stt_mute_processor, # Add the mute processor before STT
                    stt,
                    transcript.user(),
                    context_aggregator.user(),
                    llm,
                    VideoProcessor(
                        transport_params.video_out_width, transport_params.video_out_height
                    ) if config.get("video_flag", False) else None,
                    pipecat_transport.output(),
                    audiobuffer,
                    transcript.assistant(),
                    # user_idle,
                    context_aggregator.assistant(),
                    metrics_logger,
                ]
        else:
            steps = [
                    pipecat_transport.input(),
                    rtvi,
                    context_aggregator.user(),
                    VideoProcessor(
                        transport_params.video_out_width, transport_params.video_out_height
                    ) if config.get("video_flag", False) else None,
                    stt_mute_processor, # Add the mute processor before LLM
                    llm,  # LLM
                    transcript.user(),
                    pipecat_transport.output(),
                    audiobuffer,
                    transcript.assistant(),
                    # user_idle,
                    context_aggregator.assistant(),
                    metrics_logger,
                ]

        pipeline = Pipeline([p for p in steps if p is not None])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(allow_interruptions=True, 
                                  enable_metrics=True,  # performance metrics
                                  enable_usage_metrics=True,  # usage metrics
                                  observers=[RTVIObserver(rtvi)]),
        )
        
        # Will initialize flow manager if advanced flows are enabled
        flow_factory = FlowComponentFactory(
            llm=llm,
            context_aggregator=context_aggregator,
            task=task,
            advanced_flows=config.get("advanced_flows", False),
            flow_config_path=config.get("advanced_flows_config_path"),
            session_variables_path=config.get("session_variables_path"),
            user_description=config.get("user_description", ""),
            enabled_animations=allowed_animations,
            summary_prompt="Summarize the key moments of the session and concepts discussed so far. Keep it concise and focused on the activity goal and achievements.",
        )
        flow_manager = flow_factory.build()

        # Event handlers for data, transcripts and UI events
        @transcript.event_handler("on_transcript_update")
        async def on_transcript_update(processor, frame):
            await transcript_handler.on_transcript_update(processor, frame)

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            audios_dir = os.path.join(session_dir, "audios")
            os.makedirs(audios_dir, exist_ok=True)
            path = f"{audios_dir}/{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_USER.wav"
            await save_audio_file(audio, path, sr, ch)

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            audios_dir = os.path.join(session_dir, "audios")
            os.makedirs(audios_dir, exist_ok=True)
            path = f"{audios_dir}/{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_AGENT.wav"
            await save_audio_file(audio, path, sr, ch)

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            # Note: this audio seems to be not very reliable (voices get overlapped)
            i = 0
            while os.path.exists(os.path.join(session_dir, f"session_{i}.wav")):
                i += 1
            session_wav = os.path.join(session_dir, f"session_{i}.wav")
            await save_audio_file(audio, session_wav, sr, ch)

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            await rtvi.set_bot_ready()
            if flow_manager:
                await flow_manager.initialize()
            else:
                await task.queue_frames([context_aggregator.user().get_context_frame()])


        @pipecat_transport.event_handler("on_client_connected")
        async def on_client_connected(_, __):
            await audiobuffer.start_recording()

        @pipecat_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(_, __):
            logger.info("Client disconnected")
            await audiobuffer.stop_recording()
            await task.cancel()
            await metrics_logger.aggregate_and_save()

            async def trigger_analysis_on_audios(audios_dir: str):
                try:
                    # Trigger analysis on all files in audios_dir without waiting for them
                    for filename in os.listdir(audios_dir):
                        if filename.endswith(".wav"):
                            filepath = os.path.join(audios_dir, filename)
                            # asyncio.create_task(AudioAnalyzer.analyze_audio(filepath))
                            await AudioAnalyzer.analyze_audio(filepath)
                except Exception as e:
                    logger.error(f"Error triggering analysis on audios: {e}")
                    
            audios_dir = f"{session_dir}/audios"
            asyncio.create_task(trigger_analysis_on_audios(audios_dir))

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
