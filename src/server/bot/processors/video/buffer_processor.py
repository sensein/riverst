from __future__ import annotations  # keep the cv2.VideoWriter annotation lazy (string)

import os
import numpy as np
from typing import Optional
from loguru import logger
# cv2 (OpenCV, ~80 MB) imported lazily inside the methods that use it — this module is on the
# always-on backend's startup path (via the processors package), but video recording only runs
# during a session, so cv2 should not load at process startup.

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, InputImageRawFrame


class VideoBufferProcessor(FrameProcessor):
    """Buffers incoming video frames and saves them to a .mp4 file at the end.

    # TODO: sync with audio
    """

    def __init__(
        self,
        session_dir: str,
        camera_out_width: int,
        camera_out_height: int,
        fps: int = 30,
    ):
        super().__init__()
        self.session_dir = session_dir
        self.camera_out_width = camera_out_width
        self.camera_out_height = camera_out_height
        self.fps = fps
        self.frames = []
        self.video_writer: Optional[cv2.VideoWriter] = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            import cv2
            try:
                img = np.frombuffer(frame.image, dtype=np.uint8).reshape(
                    (frame.size[1], frame.size[0], 3)
                )

                if frame.size != (self.camera_out_width, self.camera_out_height):
                    img = cv2.resize(
                        img, (self.camera_out_width, self.camera_out_height)
                    )

                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                self.frames.append(img_bgr)

            except Exception as e:
                logger.warning(f"Error processing input frame: {e}")
        await self.push_frame(frame, direction)

    def save_video(self):
        """Call this method at the end of the session to save the video file."""
        if not self.frames:
            logger.warning("No frames to write.")
            return
        import cv2

        i = 0
        while os.path.exists(os.path.join(self.session_dir, f"session_{i}.mp4")):
            i += 1
        session_path = os.path.join(self.session_dir, f"session_{i}.mp4")

        logger.info(f"Saving video to {session_path}...")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.video_writer = cv2.VideoWriter(
            session_path,
            fourcc,
            self.fps,
            (self.camera_out_width, self.camera_out_height),
        )

        for frame in self.frames:
            self.video_writer.write(frame)

        self.video_writer.release()
        self.video_writer = None
        logger.info("Video saved successfully.")
