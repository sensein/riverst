import numpy as np
import cv2
import asyncio
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, InputImageRawFrame, OutputImageRawFrame
from deepface import DeepFace
from ultralytics import YOLO
import torch
from loguru import logger
from ultralytics.utils import LOGGER
import logging
LOGGER.setLevel(logging.WARNING)
from .utils import get_best_device

class VideoProcessor(FrameProcessor):
    def __init__(self, camera_out_width: int, camera_out_height: int,
                 every_n_frames: int = 5, 
                 enable_pose=True, enable_face=False):
        super().__init__()
        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height
        self.every_n_frames = every_n_frames
        self.enable_pose = enable_pose
        self.enable_face = enable_face
        self.frame_count = 0

        self.device = get_best_device()

        if self.enable_pose:
            print("Initializing yolo...")
            yolo_model = YOLO("yolo11n-pose.pt")

            # Export the model to ONNX format
            yolo_model.export(format="onnx")  # creates 'yolo11n.onnx'

            # Load the exported ONNX model
            self.pose_inferencer = YOLO("yolo11n-pose.onnx")

            dummy_img = np.random.randint(0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8)
            _ = self.pose_inferencer(dummy_img)
            print("yolo warmed up!: ")

        if self.enable_face:
            print("Warming up DeepFace...")
            dummy_img = np.random.randint(0, 255, (camera_out_height, camera_out_width, 3), dtype=np.uint8)
            _ = DeepFace.analyze(img_path=dummy_img, actions=['emotion'], enforce_detection=False)
            print("DeepFace warmed up!")

        self._pose_lock = asyncio.Lock()
        self._deepface_lock = asyncio.Lock()

        self.last_pose_results = None
        self.last_face_results = None

        self.previous_emotion = None

    async def _run_pose_in_background(self, img):
        if self._pose_lock.locked():
            return
        async with self._pose_lock:
            loop = asyncio.get_running_loop()
            try:
                results = await loop.run_in_executor(None, lambda: self.pose_inferencer(img))
                if results:
                    img_with_pose = results[0].plot()
                    self.last_pose_results = cv2.cvtColor(img_with_pose, cv2.COLOR_BGR2RGB)
                else:
                    self.last_pose_results = None
            except Exception as e:
                logger.warning(f"[yolo Error] {e}")
                self.last_pose_results = None

    async def _run_deepface_in_background(self, img):
        if self._deepface_lock.locked():
            return
        async with self._deepface_lock:
            loop = asyncio.get_running_loop()
            try:
                results = await loop.run_in_executor(None, lambda: DeepFace.analyze(
                    img_path=img,
                    actions=['emotion'], # ['age', 'gender', 'race', 'emotion'],
                    enforce_detection=False
                ))
                if isinstance(results, list):
                    # Get the first result if it's a list (TODO: manage multiple faces)
                    self.last_face_results = results[0]
            except Exception as e:
                logger.warning(f"[DeepFace Error] {e}")
                self.last_face_results = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            if not self.enable_pose and not self.enable_face:
                await self.push_frame(frame, direction)
                # This is a pass-through processor, so we need to push the frame
                output_frame = OutputImageRawFrame(frame.image, frame.size, frame.format)
                await self.push_frame(output_frame)
                return
            
            self.frame_count += 1
            try:
                img = np.frombuffer(frame.image, dtype=np.uint8).reshape((frame.size[1], frame.size[0], 3))
            except Exception as e:
                logger.warning(f"Error decoding input image: {e}")
                return

            # If it's time to update the predictions, run them asynchronously
            if self.frame_count % self.every_n_frames == 0:
                if self.enable_pose:
                    asyncio.create_task(self._run_pose_in_background(img))
                if self.enable_face:
                    asyncio.create_task(self._run_deepface_in_background(img))

            if self.enable_pose and self.last_pose_results is not None:
                output_img = self.last_pose_results.copy()

                desired_size = (self._camera_out_width, self._camera_out_height)
                if isinstance(output_img, np.ndarray):
                    if frame.size != desired_size:
                        output_img = cv2.resize(output_img, desired_size)
                else:
                    logger.warning("[Warning] output_img is not a valid numpy array after overlay. Skipping resize.")
                    return

                output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2RGB)
                output_frame = OutputImageRawFrame(output_img.tobytes(), desired_size, frame.format)
                await self.push_frame(output_frame)
        else:
            await self.push_frame(frame, direction)

