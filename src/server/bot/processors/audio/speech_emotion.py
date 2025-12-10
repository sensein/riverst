"""Speech emotion recognition processor using Wav2Vec2-based model."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Tuple
from functools import lru_cache

import numpy as np
import torch
from loguru import logger


@dataclass
class EmotionState:
    """Represents the current detected emotion state."""

    label: str = "neutral"
    confidence: float = 0.0
    timestamp: float = 0.0

    def to_prompt_string(self) -> str:
        """Format emotion state for LLM prompt injection."""
        if self.confidence < 0.4:
            return ""
        return (
            f"[User's current emotional state: {self.label} "
            f"(confidence: {self.confidence:.0%}). "
            "Gently adapt your tone and style to acknowledge this emotion, "
            "but do not change factual content.]"
        )


@dataclass
class SpeechEmotionRecognizer:
    """Lightweight speech emotion recognition using Wav2Vec2.

    Uses ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition model
    which classifies into: angry, calm, disgust, fearful, happy, neutral, sad, surprised.
    """

    model_name: str = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
    device: Optional[str] = None
    _model: Optional[object] = field(default=None, init=False, repr=False)
    _processor: Optional[object] = field(default=None, init=False, repr=False)
    _current_emotion: EmotionState = field(default_factory=EmotionState, init=False)
    _initialized: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            if torch.backends.mps.is_available():
                self.device = "mps"

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_model(model_name: str, device: str):
        """Load and cache the emotion recognition model."""
        from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor

        logger.info(f"Loading SER model: {model_name} on {device}")
        processor = Wav2Vec2Processor.from_pretrained(model_name)
        model = Wav2Vec2ForSequenceClassification.from_pretrained(model_name)
        model = model.to(device)
        model.eval()
        return processor, model

    def initialize(self) -> bool:
        """Initialize the model (lazy loading)."""
        if self._initialized:
            return True
        try:
            self._processor, self._model = self._load_model(self.model_name, self.device)
            self._initialized = True
            logger.info("Speech emotion recognizer initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SER model: {e}")
            return False

    @property
    def current_emotion(self) -> EmotionState:
        """Get the current emotion state."""
        return self._current_emotion

    def _preprocess_audio(
        self, audio_bytes: bytes, sample_rate: int = 16000
    ) -> torch.Tensor:
        """Convert audio bytes to tensor for model input."""
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_array = audio_array / 32768.0  # Normalize to [-1, 1]
        return audio_array

    def predict(
        self, audio_bytes: bytes, sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """Predict emotion from audio bytes.

        Args:
            audio_bytes: Raw audio bytes (int16 PCM)
            sample_rate: Audio sample rate (default 16000)

        Returns:
            Tuple of (emotion_label, confidence)
        """
        if not self._initialized:
            if not self.initialize():
                return ("neutral", 0.0)

        try:
            audio_array = self._preprocess_audio(audio_bytes, sample_rate)

            # Skip very short audio
            if len(audio_array) < sample_rate * 0.5:  # < 0.5 seconds
                return (self._current_emotion.label, self._current_emotion.confidence)

            inputs = self._processor(
                audio_array,
                sampling_rate=sample_rate,
                return_tensors="pt",
                padding=True,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                logits = self._model(**inputs).logits
                probs = torch.softmax(logits, dim=-1)
                predicted_id = torch.argmax(probs, dim=-1).item()
                confidence = probs[0, predicted_id].item()

            label = self._model.config.id2label[predicted_id]

            # Update current emotion state
            import time

            self._current_emotion = EmotionState(
                label=label, confidence=confidence, timestamp=time.time()
            )

            logger.debug(f"Detected emotion: {label} ({confidence:.2%})")
            return (label, confidence)

        except Exception as e:
            logger.warning(f"Emotion prediction failed: {e}")
            return ("neutral", 0.0)

    async def predict_async(
        self, audio_bytes: bytes, sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """Async wrapper for predict."""
        return await asyncio.to_thread(self.predict, audio_bytes, sample_rate)


# Singleton instance for shared state access
_emotion_recognizer: Optional[SpeechEmotionRecognizer] = None


def get_emotion_recognizer(enabled: bool = True) -> Optional[SpeechEmotionRecognizer]:
    """Get or create the singleton emotion recognizer.

    Args:
        enabled: If False, returns None (feature disabled)

    Returns:
        SpeechEmotionRecognizer instance or None
    """
    global _emotion_recognizer
    if not enabled:
        return None
    if _emotion_recognizer is None:
        _emotion_recognizer = SpeechEmotionRecognizer()
    return _emotion_recognizer


def get_current_emotion_state(enabled: bool = True) -> Optional[EmotionState]:
    """Get the current emotion state from the singleton recognizer.

    Args:
        enabled: If False, returns None

    Returns:
        Current EmotionState or None
    """
    recognizer = get_emotion_recognizer(enabled)
    if recognizer is None:
        return None
    return recognizer.current_emotion
