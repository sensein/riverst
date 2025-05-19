import datetime
import aiohttp
from typing import Any

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor, RTVIServerMessageFrame
from pipecat.processors.user_idle_processor import UserIdleProcessor
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat.frames.frames import EndFrame

from .video_processor import VideoProcessor
from .utils import save_audio_file
from .transcript_handler import TranscriptHandler
from .viseme import VisemeProcessor
from .bot_component_factory import BotComponentFactory
from .flow_component_factory import FlowComponentFactory

load_dotenv(override=True)
index = 0

async def run_bot(
    webrtc_connection: Any,
    config: dict,
    session_dir: str,
    audio_channels: int = 1,
    audio_sample_rate: int = 24000,
    audio_bit_depth: int = 2,
) -> None:
    """Main function that runs the Pipecat-based bot pipeline.

    Args:
        webrtc_connection (Any): The WebRTC connection instance.
        config (dict): Dictionary containing the bot configuration.
        session_dir (str): Directory to store session artifacts.
        audio_channels (int): Number of audio channels. Default is 1.
        audio_sample_rate (int): Sample rate in Hz. Default is 24000.
        audio_bit_depth (int): Bit depth for audio. Default is 2.
    """
    logger.info("Starting bot with config: {}", config)
    logger.info("Session directory: {}", session_dir)

    async with aiohttp.ClientSession() as session:
        # Instantiate the bot components using factory pattern
        factory = BotComponentFactory(
            modality=config["pipeline_modality"],
            llm_type=config["llm_type"],
            stt_type=config["stt_type"] if "stt_type" in config else None,
            tts_type=config["tts_type"] if "tts_type" in config else None,
            tts_params={"client_session": session} if "tts_type" in config and config["tts_type"] == "piper" else None,
            task_description=config.get("task_description", ""),
            user_description=config.get("user_description", ""),
            avatar_personality_description=config.get("avatar_personality_description", ""),
            avatar_system_prompt=config.get("avatar_system_prompt", ""),
            body_animations=config["body_animations"],
            languages=config["languages"] if "languages" in config else None,
            avatar=config["avatar"]
        )

        stt, llm, tts, tools, instruction, context, context_aggregator = await factory.build()

        # Setup WebRTC transport parameters
        transport_params = TransportParams(
            video_in_enabled=config.get("video_flag", False),
            video_out_enabled=config.get("video_flag", False),
            video_out_is_live=config.get("video_flag", False),
            video_out_width=config.get("video_out_width", 0),
            video_out_height=config.get("video_out_height", 0),
            video_out_framerate=config.get("video_out_framerate", 0),
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_filter=NoisereduceFilter(),
            vad_analyzer=SileroVADAnalyzer(),
            audio_in_passthrough=True,
            audio_out_10ms_chunks=4,
        )

        pipecat_transport = SmallWebRTCTransport(webrtc_connection=webrtc_connection, params=transport_params)

        # Audio processors for raw and viseme audio streams
        audiobuffer = AudioBufferProcessor(enable_turn_audio=True)
        viseme_audiobuffer = AudioBufferProcessor(
            enable_turn_audio=True,
            sample_rate=16000,
            buffer_size=0.5 * audio_channels * audio_sample_rate * audio_bit_depth,
        )

        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
        viseme_processor = VisemeProcessor()

        # Define animation trigger function callable by LLM
        async def handle_animation(function_name, tool_call_id, args, llm, context, result_callback):
            animation_id = args.get("animation_id")
            if animation_id:
                frame = RTVIServerMessageFrame(data={"type": "animation-event", "payload": {"animation_id": animation_id}})
                await rtvi.push_frame(frame)
            await result_callback({"status": "animation_triggered"})

        llm.register_function("trigger_animation", handle_animation)

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
        transcript_handler = TranscriptHandler(output_file=f"{session_dir}/transcript.json")

        if stt is not None and tts is not None:
            steps = [
                    pipecat_transport.input(),
                    rtvi,
                    stt,
                    transcript.user(),
                    context_aggregator.user(),
                    llm,
                    tts,
                    viseme_audiobuffer,
                    VideoProcessor(
                        transport_params.video_out_width, transport_params.video_out_height
                    ) if config.get("video_flag", False) else None,
                    pipecat_transport.output(),
                    audiobuffer,
                    transcript.assistant(),
                    # user_idle,
                    context_aggregator.assistant(),
                ]
        else:
            steps = [
                    pipecat_transport.input(),
                    rtvi,
                    context_aggregator.user(),
                    VideoProcessor(
                        transport_params.video_out_width, transport_params.video_out_height
                    ) if config.get("video_flag", False) else None,
                    llm,  # LLM
                    transcript.user(),
                    viseme_audiobuffer,
                    pipecat_transport.output(),
                    audiobuffer,
                    transcript.assistant(),
                    # user_idle,
                    context_aggregator.assistant(),
                ]

        pipeline = Pipeline([p for p in steps if p is not None])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(allow_interruptions=True, observers=[RTVIObserver(rtvi)]),
        )

        flow_manager = None
        if "advanced_flows" in config and config["advanced_flows"]:
            # Will initialize flow manager if advanced flows are enabled
            flow_factory = FlowComponentFactory(
                llm=llm,
                context_aggregator=context_aggregator,
                task=task,
                advanced_flows=config.get("advanced_flows", False),
                user_description=config.get("user_description", ""),
                flow_config_path=config.get("advanced_flows_config_path"),
                summary_prompt="Summarize the key moments of learning, words, and concepts discussed in the tutoring session so far. Keep it concise and focused on vocabulary learning.",
            )
            flow_manager = flow_factory.build()


        # Event handlers for data, transcripts, visemes, and UI events
        @transcript.event_handler("on_transcript_update")
        async def on_transcript_update(processor, frame):
            await transcript_handler.on_transcript_update(processor, frame)

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            global index
            path = f"{session_dir}/{index:06}__{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_USER.wav"
            success = await save_audio_file(audio, path, sr, ch)
            if success:
                index += 1

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            global index
            path = f"{session_dir}/{index:06}__{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_AGENT.wav"
            success = await save_audio_file(audio, path, sr, ch)
            if success:
                index += 1

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            await save_audio_file(audio, f"{session_dir}/session.wav", sr, ch)

        @viseme_audiobuffer.event_handler("on_track_audio_data")
        async def on_track_audio_data(_, user_audio, bot_audio, sr, ch):
            visemes = await viseme_processor.process_async(bot_audio, sr, ch)
            if visemes and not (len(visemes) == 1 and visemes[0].get("visemes") == [0]):
                frame = RTVIServerMessageFrame(data={"type": "visemes-event", "payload": visemes})
                await rtvi.push_frame(frame)

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            await rtvi.set_bot_ready()
            if flow_manager:
                await flow_manager.initialize()
            else:
                await task.queue_frames([context_aggregator.user().get_context_frame()])

        @pipecat_transport.event_handler("on_client_connected")
        async def on_client_connected(_, __):
            await viseme_audiobuffer.start_recording()
            await audiobuffer.start_recording()

        @pipecat_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(_, __):
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()

        @pipecat_transport.event_handler("on_client_closed")
        async def on_client_closed(_, __):
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()
            await task.cancel()

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
