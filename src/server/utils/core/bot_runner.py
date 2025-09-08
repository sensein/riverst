import aiohttp
import json
import traceback
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
from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.filters.stt_mute_filter import (
    STTMuteConfig,
    STTMuteFilter,
    STTMuteStrategy,
)

from ..processors.audio.resampling_helper import AudioResamplingHelper
from ..transport.configuration_manager import TransportConfigurationManager
from .pipeline_orchestrator import PipelineBuilder
from ..handlers.event_manager import EventHandlerManager
from ..handlers.transcript_handler import TranscriptHandler
from .component_factory import BotComponentFactory
from .flow_factory import FlowComponentFactory
from ..monitoring.metrics_logger import MetricsLoggerProcessor
from ..handlers.animation_handler import AnimationHandler
from ..handlers.conversation_handler import EndConversationHandler
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

    async with aiohttp.ClientSession() as session:
        # Instantiate the bot components using factory pattern
        factory = BotComponentFactory(
            session_dir=session_dir,
            user_id=config["user_id"],
            modality=config["pipeline_modality"],
            llm_type=config["llm_type"],
            stt_type=config["stt_type"] if "stt_type" in config else None,
            tts_type=config["tts_type"] if "tts_type" in config else None,
            tts_params=(
                {"client_session": session}
                if "tts_type" in config and config["tts_type"] == "piper"
                else None
            ),
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

        (
            stt,
            llm,
            tts,
            _,
            _,
            context,
            context_aggregator,
            allowed_animations,
            _,
            lipsync_processor,
        ) = await factory.build()
        metrics_logger = MetricsLoggerProcessor(session_dir=session_dir)

        # Setup WebRTC transport using configuration manager
        transport_manager = TransportConfigurationManager()
        transport_params, pipecat_transport = transport_manager.setup_transport(
            webrtc_connection, config
        )

        # Setup audio buffer with resampling helper
        resampling_helper = AudioResamplingHelper()
        audiobuffer = resampling_helper.create_audio_buffer_processor()

        video_buffer = VideoBufferProcessor(
            session_dir=session_dir,
            camera_out_width=config.get("video_out_width", 0),
            camera_out_height=config.get("video_out_height", 0),
        )

        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        def function_call_debug_wrapper(fn):
            async def wrapper(params: FunctionCallParams):
                args = (
                    params.arguments
                    if isinstance(params, FunctionCallParams)
                    else params
                )
                logger.info(
                    "FUNCTION_DEBUG: Function '{}' called with args: {}",
                    fn.__name__,
                    json.dumps(args),
                )
                try:
                    result = await fn(params)
                    logger.info(
                        "FUNCTION_DEBUG: Function '{}' completed successfully with result: {}",
                        fn.__name__,
                        json.dumps(result) if result else "None",
                    )
                    return result
                except Exception as e:
                    logger.error(
                        "FUNCTION_DEBUG: Error in function '{}': {}",
                        fn.__name__,
                        str(e),
                    )
                    logger.error("FUNCTION_DEBUG: {}", traceback.format_exc())

                    result = {
                        "status": "error",
                        "message": f"Execution error in '{fn.__name__}': {str(e)}",
                    }

                    if isinstance(params, FunctionCallParams):
                        await params.result_callback(result)
                    else:
                        return result

            return wrapper

        # create a closure that provides the rtvi instance and allowed animations to the handler
        async def animation_handler_wrapper(params):
            """Wrapper for the animation handler to include RTVI instance."""
            return await AnimationHandler.handle_animation(
                params, rtvi=rtvi, allowed_animations=allowed_animations
            )

        llm.register_function(
            "trigger_animation", function_call_debug_wrapper(animation_handler_wrapper)
        )

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
        pipeline_builder = PipelineBuilder()
        pipeline = pipeline_builder.build_pipeline(
            config=config,
            pipecat_transport=pipecat_transport,
            transport_params=transport_params,
            rtvi=rtvi,
            stt_mute_processor=stt_mute_processor,
            stt=stt,
            transcript=transcript,
            context_aggregator=context_aggregator,
            llm=llm,
            tts=tts,
            lipsync_processor=lipsync_processor,
            video_buffer=video_buffer,
            audiobuffer=audiobuffer,
            metrics_logger=metrics_logger,
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

        # Create end conversation handler after task is defined
        end_conversation_handler = EndConversationHandler(task)

        async def end_conversation_wrapper(params):
            return await end_conversation_handler.handle_end_conversation(
                params, None  # flow_manager will be available when this is called
            )

        llm.register_function(
            "end_conversation",
            function_call_debug_wrapper(end_conversation_wrapper),
        )

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
            end_conversation_handler=end_conversation_handler,
            summary_prompt=(
                "Summarize the key moments of the session and concepts discussed so far. "
                "Keep it concise and focused on the activity goal and achievements."
            ),
        )
        flow_manager = flow_factory.build()

        # Setup event handlers using event handler manager
        event_manager = EventHandlerManager()
        event_manager.register_event_handlers(
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
            session_dir=session_dir,
        )

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
