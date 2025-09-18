from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport


class TransportConfigurationManager:
    """Manages WebRTC transport configuration and setup."""

    def __init__(self, config: dict):
        """Initialize transport configuration manager.

        Args:
            config: Configuration dictionary containing transport settings
        """
        self.config = config

    def create_transport_params(self) -> TransportParams:
        """Create transport parameters based on configuration.

        Returns:
            TransportParams: Configured transport parameters
        """
        return TransportParams(
            video_in_enabled=self.config.get("video_flag", False),
            video_out_enabled=self.config.get("video_flag", False),
            video_out_is_live=self.config.get("video_flag", False),
            video_out_width=self.config.get("video_out_width", 0),
            video_out_height=self.config.get("video_out_height", 0),
            video_out_framerate=self.config.get("video_out_framerate", 0),
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            turn_analyzer=LocalSmartTurnAnalyzerV3(params=SmartTurnParams()),
            audio_in_passthrough=True,
            audio_out_10ms_chunks=2,
        )

    def setup_transport(self, webrtc_connection) -> SmallWebRTCTransport:
        """Create configured WebRTC transport.

        Args:
            webrtc_connection: WebRTC connection instance

        Returns:
            SmallWebRTCTransport: Configured transport instance
        """
        transport_params = self.create_transport_params()
        return SmallWebRTCTransport(
            webrtc_connection=webrtc_connection, params=transport_params
        )
