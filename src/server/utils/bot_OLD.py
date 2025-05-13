from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor, RTVIServerMessageFrame
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.network.small_webrtc import SmallWebRTCTransport
from pipecat.processors.user_idle_processor import UserIdleProcessor
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import EndFrame
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.audio.filters.noisereduce_filter import NoisereduceFilter
import datetime
import aiohttp
# from .passthrough_video_processor import PassthroughVideoProcessor
from .video_processor import VideoProcessor
from .utils import save_audio_file
from .transcript_handler import TranscriptHandler
from .viseme import VisemeProcessor
from .bot_component_factory import BotComponentFactory

load_dotenv(override=True)

async def run_bot(webrtc_connection, 
                  config: dict, 
                  session_dir: str,
                  audio_channels: int = 1,
                  audio_sample_rate: int = 24000,
                  audio_bit_depth: int = 2,
                  ) -> None:
    print("Config:", config)
    print("Session dir:", session_dir)

    async with aiohttp.ClientSession() as session:
        factory = BotComponentFactory(
            modality=config["pipeline_modality"],
            llm_type=config["llm_type"],
            stt_type=config["stt_type"],
            tts_type=config["tts_type"],
            tts_params={"client_session": session} if config["tts_type"] == "piper" else None,
            task_description=config["task_description"],
            user_description=config["user_description"] if "user_description" in config else None,
            avatar_personality_description=config["avatar_personality_description"],
            avatar_system_prompt=config["avatar_system_prompt"],
            body_animations=config["body_animations"],
        )

        stt, llm, tts, tools, instruction, context, context_aggregator = await factory.build()

        transport_params = TransportParams(
            # video params
            video_in_enabled=config.get("video_flag", False),
            video_out_enabled=config.get("video_flag", False),
            video_out_is_live=config.get("video_flag", False),
            video_out_width=config["video_out_width"] if config.get("video_flag", False) and "video_out_width" in config else 0,
            video_out_height=config["video_out_height"] if config.get("video_flag", False) and "video_out_height" in config else 0,
            video_out_framerate=config["video_out_framerate"] if config.get("video_flag", False) and "video_out_framerate" in config else 0,
            # audio params
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_filter=NoisereduceFilter(),
            # vad params
            vad_analyzer=SileroVADAnalyzer(),
            audio_in_passthrough=True,
            audio_out_10ms_chunks=4,
        )

        pipecat_transport = SmallWebRTCTransport(
            webrtc_connection=webrtc_connection, params=transport_params
        )

        audiobuffer = AudioBufferProcessor(enable_turn_audio=True)
        viseme_audiobuffer = AudioBufferProcessor(enable_turn_audio=True,
                                            sample_rate=16000, # this is because the default model works with 16kHz audio
                                            buffer_size=0.5* audio_channels * audio_sample_rate * audio_bit_depth 
                                            # sec (0.5 sec was heurically chosen) * channels * sampling_rate * bit_depth
                                            )

        # RTVI events for Pipecat client UI
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
        viseme_processor = VisemeProcessor()

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
            animation_id = args.get("animation_id", None)
            if animation_id is not None:
                frame = RTVIServerMessageFrame(
                    data={
                        "type": "animation-event",
                        "payload": {"animation_id": animation_id},
                    }
                )
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
                message = "The user has been quiet. Politely follow up on the same topic."
            elif retry_count < 4:
                message = "The user is still inactive. Ask if they'd like to continue our conversation."
            elif retry_count < 6:
                message = "Still no response from the user. Wait patiently and let them know you're available if needed."
            elif retry_count < 10:
                message = "No user input detected for a while. Consider ending the session politely if it continues."
            else:
                # Final attempt: End the session
                print("User has been idle for a while. Actually ending the conversation.")
                await task.queue_frame(EndFrame())
                # TODO: handle the end of the conversation on the client side
                return False  # Stop monitoring

            context.add_message({
                "role": "system",
                "content": message
            })
            await task.queue_frame(context_aggregator.assistant().get_context_frame())
            return True

        IDLE_TIMEOUT = 15 # seconds
        user_idle = UserIdleProcessor(
            callback=handle_user_idle,
            timeout=IDLE_TIMEOUT
        )

        # Create a single transcript processor instance
        transcript = TranscriptProcessor()
        transcript_handler = TranscriptHandler(output_file=f"{session_dir}/transcript.json")

        if config["advanced_flows"]:
            raise NotImplementedError("Advanced flows are not implemented yet. It's on Bruce's TODO list.")
        else:
            if stt is not None and tts is not None:
                pipeline = Pipeline(
                    [
                        pipecat_transport.input(),
                        rtvi,
                        stt,
                        transcript.user(),
                        context_aggregator.user(),
                        llm,
                        tts,
                        viseme_audiobuffer,
                        VideoProcessor(
                            transport_params.video_out_width, transport_params.video_out_height,
                            context, context_aggregator
                        ),  # Sending the video back to the user
                        pipecat_transport.output(),
                        audiobuffer,
                        transcript.assistant(),
                        user_idle,
                        context_aggregator.assistant(),
                    ]
                )
            else:
                pipeline = Pipeline(
                    [
                        pipecat_transport.input(),
                        rtvi,
                        context_aggregator.user(),
                        VideoProcessor(
                            transport_params.video_out_width, transport_params.video_out_height, 
                            context, context_aggregator
                        ),  # Sending the video back to the user
                        llm,  # LLM
                        transcript.user(),
                        viseme_audiobuffer,
                        pipecat_transport.output(),
                        audiobuffer,
                        transcript.assistant(),
                        user_idle,
                        context_aggregator.assistant(),
                    ]
                )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                observers=[RTVIObserver(rtvi)],
            ),
        )

        # Register event handler for transcript updates
        @transcript.event_handler("on_transcript_update")
        async def on_transcript_update(processor, frame):
            """Handle new transcript messages."""
            # Each message contains role (user/assistant), content, and timestamp
            await transcript_handler.on_transcript_update(processor, frame)
            # TODO: fix the transcript!!

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_USER.wav"
            path = f"{session_dir}/{name}"
            await save_audio_file(audio, path, sr, ch)
            # TODO: fix the transcript!!
            # await transcript_handler.attach_audio_to_last_message("user", path) # TODO: not always working!!!

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_AGENT.wav"
            path = f"{session_dir}/{name}"
            await save_audio_file(audio, path, sr, ch)
            # TODO: fix the transcript!!
            # await transcript_handler.attach_audio_to_last_message("assistant", path) # TODO: not always working!!!

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            """Handle session audio data from the audio buffer."""
            await save_audio_file(audio, f"{session_dir}/session.wav", sr, ch)

        @viseme_audiobuffer.event_handler("on_track_audio_data")
        async def on_track_audio_data(buffer, user_audio: bytes, bot_audio: bytes, sample_rate: int, num_channels: int):
            """Process audio data to extract viseme information."""
            visemes_durations = await viseme_processor.process_async(bot_audio, sample_rate, num_channels)

            if visemes_durations and isinstance(visemes_durations, list) and len(visemes_durations) == 1 and visemes_durations[0]["visemes"] == [0]:
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
            """Handle the event when the Pipecat client is ready."""
            # logger.info("Pipecat client ready.")
            await rtvi.set_bot_ready()
            # Kick off the conversation.
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        @pipecat_transport.event_handler("on_client_connected")
        async def on_client_connected(_transport, _client):
            """Handle the event when the Pipecat client is connected."""
            # logger.info("Pipecat Client connected")
            await viseme_audiobuffer.start_recording()
            await audiobuffer.start_recording()

        @pipecat_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(_transport, _client):
            """Handle the event when the Pipecat client is disconnected."""
            # logger.info("Pipecat Client disconnected")
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()

        @pipecat_transport.event_handler("on_client_closed")
        async def on_client_closed(_transport, _client):
            """Handle the event when the Pipecat client is closed."""
            # logger.info("Pipecat Client closed")
            await viseme_audiobuffer.stop_recording()
            await audiobuffer.stop_recording()
            await task.cancel()

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)
