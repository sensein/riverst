"""This module provides the VideoProcessor class for processing video frames with pose detection."""

# import os
import numpy as np
import asyncio
import logging
# cv2 (OpenCV, ~80 MB) is imported lazily inside the frame-processing methods — it's only used
# when video frames actually flow (video is off for the language tutor), so this keeps the
# always-on backend light at startup.

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, InputImageRawFrame, OutputImageRawFrame

from loguru import logger

from ...utils.device_utils import get_best_device

# ultralytics/YOLO (pulls torch) is imported LAZILY inside _load_pose_inferencer — it's only
# needed for pose detection, which is off for the language tutor. Keeping it out of module
# scope keeps the always-on backend light at startup.


class VideoProcessor(FrameProcessor):
    """Processes video frames to optionally detect pose."""

    def __init__(
        self,
        camera_out_width: int,
        camera_out_height: int,
        every_n_frames: int = 5,
        enable_pose: bool = True,
    ):
        super().__init__()
        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height
        self.every_n_frames = every_n_frames
        self.enable_pose = enable_pose
        self.frame_count = 0
        self.device = get_best_device()

        self._pose_lock = asyncio.Lock()
        self.last_pose_results = None

        if self.enable_pose:
            logger.info("Initializing YOLO pose model...")
            self.pose_inferencer = self._load_pose_inferencer()

            dummy_img = np.random.randint(
                0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8
            )
            _ = self.pose_inferencer(dummy_img)
            logger.info("YOLO warmed up.")

    def _load_pose_inferencer(self):
        """Prefer ONNX when available, but keep CPU deployments functional without it."""
        from ultralytics import YOLO
        from ultralytics.utils import LOGGER
        LOGGER.setLevel(logging.WARNING)

        yolo_model = YOLO("yolo11n-pose.pt")
        try:
            yolo_model.export(format="onnx")  # Creates 'yolo11n-pose.onnx'
            logger.info("Using ONNX-backed YOLO pose inferencer.")
            return YOLO("yolo11n-pose.onnx")
        except Exception as exc:
            logger.warning(
                "ONNX pose export unavailable, falling back to PyTorch YOLO pose model: "
                f"{exc}"
            )
            return yolo_model

    async def _run_pose_in_background(self, img: np.ndarray) -> None:
        if self._pose_lock.locked():
            return
        import cv2
        async with self._pose_lock:
            try:
                results = await asyncio.to_thread(self.pose_inferencer, img)
                if results:
                    plotted = results[0].plot()
                    self.last_pose_results = cv2.cvtColor(plotted, cv2.COLOR_BGR2RGB)
                else:
                    self.last_pose_results = None
            except Exception as e:
                logger.warning(f"[YOLO Error] {e}")
                self.last_pose_results = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            if not self.enable_pose and not self.enable_face:
                await self.push_frame(frame, direction)
                await self.push_frame(
                    OutputImageRawFrame(frame.image, frame.size, frame.format)
                )
                return

            self.frame_count += 1

            try:
                img = np.frombuffer(frame.image, dtype=np.uint8).reshape(
                    (frame.size[1], frame.size[0], 3)
                )
            except Exception as e:
                logger.warning(f"Error decoding input image: {e}")
                return

            if self.frame_count % self.every_n_frames == 0:
                if self.enable_pose:
                    asyncio.create_task(self._run_pose_in_background(img))

            if self.enable_pose and self.last_pose_results is not None:
                output_img = self.last_pose_results.copy()

                if isinstance(output_img, np.ndarray):
                    import cv2
                    if frame.size != (self._camera_out_width, self._camera_out_height):
                        output_img = cv2.resize(
                            output_img,
                            (self._camera_out_width, self._camera_out_height),
                        )
                    output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2RGB)
                    output_frame = OutputImageRawFrame(
                        output_img.tobytes(),
                        (self._camera_out_width, self._camera_out_height),
                        frame.format,
                    )
                    await self.push_frame(output_frame)
                else:
                    logger.warning(
                        "[Warning] Invalid pose result array. Skipping overlay."
                    )
        else:
            await self.push_frame(frame, direction)
