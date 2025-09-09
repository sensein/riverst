from typing import Optional, Any
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.filters.stt_mute_filter import (
    STTMuteConfig,
    STTMuteFilter,
    STTMuteStrategy,
)
from ..processors.video.processor import VideoProcessor
from ..processors.video.buffer_processor import VideoBufferProcessor


class PipelineBuilder:
    """Builds pipeline configurations based on available components and settings."""

    def __init__(self, config: dict, session_dir: str):
        """Initialize pipeline builder.

        Args:
            config: Configuration dictionary
            session_dir: Directory for session artifacts
        """
        self.config = config
        self.session_dir = session_dir

    def _create_stt_mute_processor(self) -> STTMuteFilter:
        """Create STT mute processor with appropriate configuration.

        Returns:
            STTMuteFilter: Configured STT mute processor
        """
        return STTMuteFilter(
            config=STTMuteConfig(
                strategies={
                    STTMuteStrategy.FIRST_SPEECH,
                    # Mute only during the bot's first speech utterance.
                    # Useful for introductions when you want the bot to complete its greeting before the user can speak.
                }
            ),
        )

    def _create_video_buffer(self) -> Optional[VideoBufferProcessor]:
        """Create video buffer processor if video is enabled.

        Returns:
            VideoBufferProcessor or None: Video buffer processor if enabled
        """
        if not self.config.get("video_flag", False):
            return None

        return VideoBufferProcessor(
            session_dir=self.session_dir,
            camera_out_width=self.config.get("video_out_width", 0),
            camera_out_height=self.config.get("video_out_height", 0),
        )

    def _create_video_processor(self, transport_params) -> Optional[VideoProcessor]:
        """Create video processor if video is enabled.

        Args:
            transport_params: Transport parameters containing video dimensions

        Returns:
            VideoProcessor or None: Video processor if enabled
        """
        if not self.config.get("video_flag", False):
            return None

        return VideoProcessor(
            transport_params.video_out_width,
            transport_params.video_out_height,
        )

    def _should_include_lipsync(self, lipsync_processor) -> Optional[Any]:
        """Determine if lipsync processor should be included.

        Args:
            lipsync_processor: The lipsync processor instance

        Returns:
            Lipsync processor or None based on embodiment type
        """
        if self.config.get("embodiment", "humanoid_avatar") == "humanoid_avatar":
            return lipsync_processor
        return None

    def build_full_pipeline(
        self,
        pipecat_transport,
        rtvi,
        stt,
        llm,
        tts,
        transcript,
        context_aggregator,
        lipsync_processor,
        audiobuffer,
        metrics_logger,
        transport_params,
    ) -> Pipeline:
        """Build complete pipeline with STT and TTS.

        Args:
            pipecat_transport: WebRTC transport
            rtvi: RTVI processor
            stt: Speech-to-text processor
            llm: Language model processor
            tts: Text-to-speech processor
            transcript: Transcript processor
            context_aggregator: Context aggregation processor
            lipsync_processor: Lip sync processor
            audiobuffer: Audio buffer processor
            metrics_logger: Metrics logging processor
            transport_params: Transport parameters

        Returns:
            Pipeline: Configured pipeline instance
        """
        stt_mute_processor = self._create_stt_mute_processor()
        video_buffer = self._create_video_buffer()
        video_processor = self._create_video_processor(transport_params)
        lipsync = self._should_include_lipsync(lipsync_processor)

        steps = [
            pipecat_transport.input(),
            rtvi,
            stt_mute_processor,  # Add the mute processor before STT
            stt,
            transcript.user(),
            context_aggregator.user(),
            llm,
            tts,
            lipsync,
            video_buffer,
            video_processor,
            pipecat_transport.output(),
            audiobuffer,
            transcript.assistant(),
            context_aggregator.assistant(),
            metrics_logger,
        ]

        return Pipeline([p for p in steps if p is not None])

    def build_llm_only_pipeline(
        self,
        pipecat_transport,
        rtvi,
        llm,
        transcript,
        context_aggregator,
        lipsync_processor,
        audiobuffer,
        metrics_logger,
        transport_params,
    ) -> Pipeline:
        """Build LLM-only pipeline without STT/TTS.

        Args:
            pipecat_transport: WebRTC transport
            rtvi: RTVI processor
            llm: Language model processor
            transcript: Transcript processor
            context_aggregator: Context aggregation processor
            lipsync_processor: Lip sync processor
            audiobuffer: Audio buffer processor
            metrics_logger: Metrics logging processor
            transport_params: Transport parameters

        Returns:
            Pipeline: Configured pipeline instance
        """
        stt_mute_processor = self._create_stt_mute_processor()
        video_buffer = self._create_video_buffer()
        video_processor = self._create_video_processor(transport_params)
        lipsync = self._should_include_lipsync(lipsync_processor)

        steps = [
            pipecat_transport.input(),
            context_aggregator.user(),
            rtvi,
            video_buffer,
            video_processor,
            stt_mute_processor,  # Add the mute processor before LLM
            llm,
            lipsync,
            transcript.user(),
            pipecat_transport.output(),
            audiobuffer,
            transcript.assistant(),
            context_aggregator.assistant(),
            metrics_logger,
        ]

        return Pipeline([p for p in steps if p is not None])

    def build_pipeline(
        self,
        pipecat_transport,
        rtvi,
        stt,
        llm,
        tts,
        transcript,
        context_aggregator,
        lipsync_processor,
        audiobuffer,
        metrics_logger,
        transport_params,
    ) -> Pipeline:
        """Build appropriate pipeline based on available components.

        Args:
            pipecat_transport: WebRTC transport
            rtvi: RTVI processor
            stt: Speech-to-text processor (can be None)
            llm: Language model processor
            tts: Text-to-speech processor (can be None)
            transcript: Transcript processor
            context_aggregator: Context aggregation processor
            lipsync_processor: Lip sync processor
            audiobuffer: Audio buffer processor
            metrics_logger: Metrics logging processor
            transport_params: Transport parameters

        Returns:
            Pipeline: Configured pipeline instance
        """
        if stt is not None and tts is not None:
            return self.build_full_pipeline(
                pipecat_transport,
                rtvi,
                stt,
                llm,
                tts,
                transcript,
                context_aggregator,
                lipsync_processor,
                audiobuffer,
                metrics_logger,
                transport_params,
            )
        else:
            return self.build_llm_only_pipeline(
                pipecat_transport,
                rtvi,
                llm,
                transcript,
                context_aggregator,
                lipsync_processor,
                audiobuffer,
                metrics_logger,
                transport_params,
            )
