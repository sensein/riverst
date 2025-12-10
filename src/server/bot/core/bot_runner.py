import aiohttp
from typing import Any

from dotenv import load_dotenv
from loguru import logger
import os

# from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frameworks.rtvi import (
    RTVIConfig,
    RTVIObserver,
    RTVIProcessor,
)
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.processors.filters.stt_mute_filter import (
    STTMuteConfig,
    STTMuteFilter,
    STTMuteStrategy,
)

from ..processors.audio.resampling_helper import AudioResamplingHelper
from ..transport.configuration_manager import TransportConfigurationManager
from .pipeline_orchestrator import PipelineBuilder
from .event_manager import EventHandlerManager
from ..components.transcription import TranscriptHandler
from .component_factory import BotComponentFactory
from ..flows.flow_factory import FlowComponentFactory
from ..monitoring.metrics_logger import MetricsLoggerProcessor
from ..processors.video.buffer_processor import VideoBufferProcessor

load_dotenv(override=True)


async def run_bot(
    webrtc_connection: Any,
    config: dict,
    session_dir: str,
) -> None:
    """Main function that runs the Pipecat-based bot pipeline.

    Args:
        webrtc_connection (Any): The WebRTC connection instance.
        config (dict): Dictionary containing the bot configuration.
        session_dir (str): Directory to store session artifacts.
    """
    logger.info("Starting bot with config: {}", config)
    logger.info("Session directory: {}", session_dir)

    async with aiohttp.ClientSession():
        # Instantiate the bot components using factory pattern
        factory = BotComponentFactory(
            session_dir=session_dir,
            user_id=config["user_id"],
            modality=config["pipeline_modality"],
            llm_type=config["llm_type"],
            stt_type=config["stt_type"] if "stt_type" in config else None,
            tts_type=config["tts_type"] if "tts_type" in config else None,
            tts_params=None,
            short_term_memory=config.get("short_term_memory", False),
            long_term_memory=config.get("long_term_memory", False),
            task_description=config.get("task_description", ""),
            user_description=config.get("user_description", ""),
            avatar_personality_description=config.get(
                "avatar_personality_description", ""
            ),
            avatar_system_prompt=config.get("avatar_system_prompt", ""),
            body_animations=config["body_animations"],
            languages=config["languages"] if "languages" in config else None,
            avatar=config["avatar"],
        )

        components = await factory.build()
        stt = components.stt
        llm = components.llm
        tts = components.tts
        context_aggregator = components.context_aggregator
        allowed_animations = components.used_animations
        lipsync_processor = components.lipsync_processor
        metrics_logger = MetricsLoggerProcessor(session_dir=session_dir)

        # Setup WebRTC transport using configuration manager
        transport_manager = TransportConfigurationManager(config)
        pipecat_transport = transport_manager.setup_transport(webrtc_connection)

        # Setup audio buffer with resampling helper
        audiobuffer = AudioResamplingHelper.configure_audio_buffer_processor()

        video_buffer = VideoBufferProcessor(
            session_dir=session_dir,
            camera_out_width=config.get("video_out_width", 0),
            camera_out_height=config.get("video_out_height", 0),
        )

        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        # Tool registration will happen after task is initialized

        # User idle handler implementation moved to EventHandlerManager

        # user_idle = UserIdleProcessor(callback=handle_user_idle, timeout=15)
        # TODO: fix the user_idle processor
        # I commented it out for now because it seems to prompt the assistant with random messages
        transcript = TranscriptProcessor()
        transcript_handler = TranscriptHandler(
            output_file=os.path.join(session_dir, "transcript.json")
        )

        # Configure with one or more strategies
        stt_mute_processor = STTMuteFilter(
            config=STTMuteConfig(
                strategies={
                    STTMuteStrategy.FIRST_SPEECH,
                    # Mute only during the bot’s first speech utterance.
                    # Useful for introductions when you want the bot to complete its greeting before the user can speak.
                }
            ),
        )

        # Build pipeline using pipeline builder
        pipeline_builder = PipelineBuilder(config, session_dir)
        pipeline = pipeline_builder.build_pipeline(
            pipecat_transport=pipecat_transport,
            rtvi=rtvi,
            stt=stt,
            stt_mute_processor=stt_mute_processor,
            llm=llm,
            tts=tts,
            transcript=transcript,
            context_aggregator=context_aggregator,
            lipsync_processor=lipsync_processor,
            audiobuffer=audiobuffer,
            metrics_logger=metrics_logger,
            transport_params=transport_manager.create_transport_params(),
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,  # performance metrics
                enable_usage_metrics=True,  # usage metrics
                observers=[RTVIObserver(rtvi)],
            ),
            idle_timeout_secs=None,  # No idle timeout for the bot
            cancel_on_idle_timeout=False,  # Don't auto-cancel, just notify
        )

        # Register all tools through the factory after task is defined
        tool_handlers = factory.register_tools(llm=llm, rtvi=rtvi, task=task)

        # Will initialize flow manager if advanced flows are enabled
        flow_factory = FlowComponentFactory(
            llm=llm,
            context_aggregator=context_aggregator,
            task=task,
            advanced_flows=config.get("advanced_flows", False),
            flow_config_path=config.get("advanced_flows_config_path"),
            activity_variables_path=config.get("activity_variables_path"),
            user_activity_variables=(
                {"index": config.get("index")}
                if config.get("index") is not None
                else {}
            ),
            user_description=config.get("user_description", ""),
            enabled_animations=allowed_animations,
            end_conversation_handler=tool_handlers.get("end_conversation"),
            summary_prompt=(
                "Summarize the key moments of the session and concepts discussed so far. "
                "Keep it concise and focused on the activity goal and achievements."
            ),
        )
        flow_manager = flow_factory.build()

        # Setup event handlers using event handler manager
        event_manager = EventHandlerManager(session_dir)
        event_manager.register_all_handlers(
            transcript=transcript,
            transcript_handler=transcript_handler,
            audiobuffer=audiobuffer,
            rtvi=rtvi,
            pipecat_transport=pipecat_transport,
            task=task,
            flow_manager=flow_manager,
            context_aggregator=context_aggregator,
            metrics_logger=metrics_logger,
            video_buffer=video_buffer,
        )

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
