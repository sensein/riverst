from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, InputImageRawFrame, OutputImageRawFrame
import cv2
import numpy as np

class PassthroughVideoProcessor(FrameProcessor):
    def __init__(self, camera_out_width: int, camera_out_height: int):
        super().__init__()
        self._camera_out_width = camera_out_width
        self._camera_out_height = camera_out_height

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InputImageRawFrame):
            img = np.frombuffer(frame.image, dtype=np.uint8).reshape(
                (frame.size[1], frame.size[0], 3)
            )

            desired_size = (self._camera_out_width, self._camera_out_height)
            if frame.size != desired_size:
                resized_image = cv2.resize(img, desired_size)
                output_frame = OutputImageRawFrame(resized_image.tobytes(), desired_size, frame.format)
            else:
                output_frame = OutputImageRawFrame(image=img.tobytes(), size=frame.size, format=frame.format)

            await self.push_frame(output_frame)
        else:
            await self.push_frame(frame, direction)
