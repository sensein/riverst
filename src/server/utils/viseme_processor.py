import asyncio
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TTSTextFrame
from ultralytics.utils import LOGGER
from pipecat.processors.frameworks.rtvi import (
    RTVIConfig,
    RTVIObserver,
    RTVIProcessor,
    RTVIServerMessageFrame,
)
import logging
LOGGER.setLevel(logging.WARNING)

class VisemeProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSTextFrame):
            print("TTSAudioRawFrames received, processing...: ", frame)
            word_frame = RTVIServerMessageFrame(data={"type": "tts-event", "payload": {
                "text": frame.text,
                "timestamp": frame.pts,
            }})
            await self.push_frame(word_frame, direction)
            await self.push_frame(frame, direction)
        else:
            await self.push_frame(frame, direction)
