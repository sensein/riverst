import os
import datetime
import asyncio
from loguru import logger
from ..utils.audio_utils import save_audio_file
from ..processors.audio.analyzer import AudioAnalyzer


class EventHandlerManager:
    """Manages event handler registration and audio processing callbacks."""

    def __init__(self, session_dir: str):
        """Initialize event handler manager.

        Args:
            session_dir: Directory for session artifacts
        """
        self.session_dir = session_dir

    def register_transcript_handlers(self, transcript, transcript_handler):
        """Register transcript-related event handlers.

        Args:
            transcript: Transcript processor instance
            transcript_handler: Transcript handler instance
        """

        @transcript.event_handler("on_transcript_update")
        async def on_transcript_update(processor, frame):
            await transcript_handler.on_transcript_update(processor, frame)

    def register_audio_handlers(self, audiobuffer):
        """Register audio-related event handlers.

        Args:
            audiobuffer: Audio buffer processor instance
        """

        @audiobuffer.event_handler("on_user_turn_audio_data")
        async def on_user_audio(_, audio, sr, ch):
            audios_dir = os.path.join(self.session_dir, "audios")
            os.makedirs(audios_dir, exist_ok=True)
            path = f"{audios_dir}/{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_USER.wav"
            await save_audio_file(audio, path, sr, ch)

        @audiobuffer.event_handler("on_bot_turn_audio_data")
        async def on_bot_audio(_, audio, sr, ch):
            audios_dir = os.path.join(self.session_dir, "audios")
            os.makedirs(audios_dir, exist_ok=True)
            path = f"{audios_dir}/{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_AGENT.wav"
            await save_audio_file(audio, path, sr, ch)

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_, audio, sr, ch):
            # Note: this audio seems to be not very reliable (voices get overlapped)
            i = 0
            while os.path.exists(os.path.join(self.session_dir, f"session_{i}.wav")):
                i += 1
            session_wav = os.path.join(self.session_dir, f"session_{i}.wav")
            await save_audio_file(audio, session_wav, sr, ch)

    def register_rtvi_handlers(self, rtvi, task, context_aggregator, flow_manager):
        """Register RTVI-related event handlers.

        Args:
            rtvi: RTVI processor instance
            task: Pipeline task instance
            context_aggregator: Context aggregator instance
            flow_manager: Flow manager instance (can be None)
        """

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi_instance):
            await rtvi_instance.set_bot_ready()
            if flow_manager:
                await flow_manager.initialize()
            else:
                await task.queue_frames([context_aggregator.user().get_context_frame()])

    def register_transport_handlers(
        self, pipecat_transport, audiobuffer, task, metrics_logger, video_buffer
    ):
        """Register WebRTC transport event handlers.

        Args:
            pipecat_transport: WebRTC transport instance
            audiobuffer: Audio buffer processor instance
            task: Pipeline task instance
            metrics_logger: Metrics logger instance
            video_buffer: Video buffer processor instance
        """

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
                            await AudioAnalyzer.analyze_audio(filepath)
                except Exception as e:
                    logger.error(f"Error triggering analysis on audios: {e}")

            audios_dir = f"{self.session_dir}/audios"
            asyncio.create_task(trigger_analysis_on_audios(audios_dir))
            video_buffer.save_video()

    def register_all_handlers(
        self,
        transcript,
        transcript_handler,
        audiobuffer,
        rtvi,
        task,
        context_aggregator,
        flow_manager,
        pipecat_transport,
        metrics_logger,
        video_buffer,
    ):
        """Register all event handlers at once.

        Args:
            transcript: Transcript processor instance
            transcript_handler: Transcript handler instance
            audiobuffer: Audio buffer processor instance
            rtvi: RTVI processor instance
            task: Pipeline task instance
            context_aggregator: Context aggregator instance
            flow_manager: Flow manager instance (can be None)
            pipecat_transport: WebRTC transport instance
            metrics_logger: Metrics logger instance
            video_buffer: Video buffer processor instance
        """
        self.register_transcript_handlers(transcript, transcript_handler)
        self.register_audio_handlers(audiobuffer)
        self.register_rtvi_handlers(rtvi, task, context_aggregator, flow_manager)
        self.register_transport_handlers(
            pipecat_transport, audiobuffer, task, metrics_logger, video_buffer
        )
