"""This module provides the VideoProcessor class for processing video frames with pose and facial emotion detection."""

# import os
import cv2
import numpy as np
import asyncio
import logging

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, InputImageRawFrame, OutputImageRawFrame

import torch
from ultralytics import YOLO
from ultralytics.utils import LOGGER
from loguru import logger

from ...utils.device_utils import get_best_device

LOGGER.setLevel(logging.WARNING)


class VideoProcessor(FrameProcessor):
    """Processes video frames to optionally detect pose and facial emotion."""

    def __init__(
        self,
        camera_out_width: int,
        camera_out_height: int,
        every_n_frames: int = 5,
        enable_pose: bool = True,
        enable_face: bool = False,
    ):
        super().__init__()
        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height
        self.every_n_frames = every_n_frames
        self.enable_pose = enable_pose
        self.enable_face = enable_face
        self.frame_count = 0
        self.device = get_best_device()

        self._pose_lock = asyncio.Lock()
        self._deepface_lock = asyncio.Lock()

        self.last_pose_results = None
        self.last_face_results = None
        self.previous_emotion = None

        if self.enable_pose:
            logger.info("Initializing YOLO pose model...")

            # force PyTorch to grab the GPU before TensorFlow does
            # this is because otherwise yolo cannot find any gpu device and fails
            if torch.cuda.is_available():
                torch.cuda.is_available()
                _ = torch.cuda.current_device()
                _ = torch.cuda.get_device_properties(0)

            yolo_model = YOLO("yolo11n-pose.pt")
            yolo_model.export(format="onnx")  # Creates 'yolo11n-pose.onnx'
            self.pose_inferencer = YOLO("yolo11n-pose.onnx")

            dummy_img = np.random.randint(
                0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8
            )
            _ = self.pose_inferencer(dummy_img)
            logger.info("YOLO warmed up.")

        if self.enable_face:
            logger.info("Warming up DeepFace...")
            dummy_img = np.random.randint(
                0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8
            )
            from deepface import DeepFace

            _ = DeepFace.analyze(
                img_path=dummy_img, actions=["emotion"], enforce_detection=False
            )
            logger.info("DeepFace warmed up.")

    async def _run_pose_in_background(self, img: np.ndarray) -> None:
        if self._pose_lock.locked():
            return
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

    async def _run_deepface_in_background(self, img: np.ndarray) -> None:
        if self._deepface_lock.locked():
            return
        async with self._deepface_lock:
            try:
                from deepface import DeepFace

                results = await asyncio.to_thread(
                    DeepFace.analyze,
                    img_path=img,
                    actions=["emotion"],
                    enforce_detection=False,
                )
                if isinstance(results, list):
                    self.last_face_results = results[0]  # TODO: handle multiple faces
            except Exception as e:
                logger.warning(f"[DeepFace Error] {e}")
                self.last_face_results = None

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
                if self.enable_face:
                    asyncio.create_task(self._run_deepface_in_background(img))

            if self.enable_pose and self.last_pose_results is not None:
                output_img = self.last_pose_results.copy()

                if isinstance(output_img, np.ndarray):
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
