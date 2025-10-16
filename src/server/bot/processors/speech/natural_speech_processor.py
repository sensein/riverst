"""Natural speech processor for adding realistic speech patterns.

This processor adds interjections, discourse markers, and filled pauses
to make avatar speech sound more natural and human-like.
"""

import random
import re
from typing import Optional
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    LLMFullResponseEndFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class NaturalSpeechProcessor(FrameProcessor):
    """Processor that adds natural speech patterns to text output.
    
    This processor intercepts text frames from the LLM and injects:
    - Interjections (oh, ah, wow, hmm, etc.)
    - Discourse markers (well, you know, I mean, like, etc.)
    - Filled pauses (um, uh, er, etc.)
    - Natural hesitations and thinking sounds
    
    The processor is context-aware and adds patterns based on:
    - Sentence structure and punctuation
    - Question vs statement detection
    - Emotional context from keywords
    - Response length and complexity
    """

    # Natural speech elements categorized by type and usage
    INTERJECTIONS = {
        "surprise": ["oh", "wow", "whoa", "gosh"],
        "understanding": ["ah", "oh I see", "aha", "right"],
        "thinking": ["hmm", "let me think", "let's see"],
        "agreement": ["yeah", "sure", "right", "okay"],
        "uncertainty": ["well", "hmm", "I'm not sure"],
    }

    DISCOURSE_MARKERS = {
        "start": ["well", "so", "you know", "actually", "honestly"],
        "transition": ["and", "but", "also", "plus", "however"],
        "clarification": ["I mean", "that is", "in other words"],
        "emphasis": ["really", "truly", "honestly", "definitely"],
        "hedging": ["kind of", "sort of", "maybe", "perhaps"],
    }

    FILLED_PAUSES = ["um", "uh", "er", "umm", "uhh", "ehh"]

    # Punctuation patterns for natural placement
    SENTENCE_STARTERS = re.compile(r"^([A-Z][^.!?]*)")
    QUESTION_PATTERN = re.compile(r"\?")
    COMPLEX_SENTENCE = re.compile(r",.*,")
    
    def __init__(
        self,
        *,
        enabled: bool = True,
        interjection_probability: float = 0.15,
        discourse_marker_probability: float = 0.20,
        filled_pause_probability: float = 0.12,
        hesitation_probability: float = 0.08,
        vary_intensity: bool = True,
        preserve_formality: bool = False,
        **kwargs,
    ):
        """Initialize the natural speech processor.
        
        Args:
            enabled: Whether to apply natural speech patterns
            interjection_probability: Probability of adding interjections (0.0-1.0)
            discourse_marker_probability: Probability of adding discourse markers (0.0-1.0)
            filled_pause_probability: Probability of adding filled pauses (0.0-1.0)
            hesitation_probability: Probability of adding hesitation patterns (0.0-1.0)
            vary_intensity: Whether to adjust intensity based on context
            preserve_formality: If True, use fewer informal patterns
        """
        super().__init__(**kwargs)
        self.enabled = enabled
        self.interjection_prob = interjection_probability
        self.discourse_marker_prob = discourse_marker_probability
        self.filled_pause_prob = filled_pause_probability
        self.hesitation_prob = hesitation_probability
        self.vary_intensity = vary_intensity
        self.preserve_formality = preserve_formality
        
        # Adjust probabilities if preserving formality
        if self.preserve_formality:
            self.filled_pause_prob *= 0.5
            self.hesitation_prob *= 0.5
        
        logger.info(
            f"NaturalSpeechProcessor initialized: enabled={enabled}, "
            f"interjection_prob={interjection_probability}, "
            f"discourse_marker_prob={discourse_marker_probability}, "
            f"filled_pause_prob={filled_pause_probability}"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process frames and add natural speech patterns to text.
        
        Args:
            frame: The frame to process
            direction: The direction of frame flow
        """
        await super().process_frame(frame, direction)

        # Only process text frames going downstream (from LLM to TTS)
        if not isinstance(frame, TextFrame) or direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if not self.enabled:
            await self.push_frame(frame, direction)
            return

        # Get the original text
        original_text = frame.text.strip()
        
        if not original_text:
            await self.push_frame(frame, direction)
            return

        # Process the text to add natural speech patterns
        enhanced_text = self._enhance_text(original_text)
        
        logger.debug(f"Natural speech: '{original_text}' → '{enhanced_text}'")
        
        # Create a new frame with enhanced text
        enhanced_frame = TextFrame(text=enhanced_text)
        await self.push_frame(enhanced_frame, direction)

    def _enhance_text(self, text: str) -> str:
        """Add natural speech patterns to the text.
        
        Args:
            text: Original text from LLM
            
        Returns:
            Enhanced text with natural speech patterns
        """
        # Split into sentences for more granular control
        sentences = self._split_into_sentences(text)
        enhanced_sentences = []
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Analyze sentence context
            is_question = "?" in sentence
            is_first = i == 0
            is_complex = bool(self.COMPLEX_SENTENCE.search(sentence))
            word_count = len(sentence.split())
            
            # Adjust probabilities based on context
            context_multiplier = 1.0
            if self.vary_intensity:
                if is_complex:
                    context_multiplier *= 1.3  # More patterns in complex sentences
                if word_count > 20:
                    context_multiplier *= 1.2  # Longer sentences get more patterns
                if is_question:
                    context_multiplier *= 0.8  # Fewer patterns in questions
            
            # Start sentence enhancement
            enhanced = sentence
            
            # Add discourse marker at the beginning (especially first sentence)
            if is_first and random.random() < self.discourse_marker_prob * context_multiplier:
                marker = random.choice(self.DISCOURSE_MARKERS["start"])
                enhanced = f"{marker}, {enhanced}"
            
            # Add interjection at the beginning for appropriate contexts
            if random.random() < self.interjection_prob * context_multiplier:
                interjection = self._select_interjection(sentence)
                if interjection:
                    # Insert at beginning or after first word
                    if random.random() < 0.7:
                        enhanced = f"{interjection}, {enhanced}"
                    else:
                        words = enhanced.split(None, 1)
                        if len(words) == 2:
                            enhanced = f"{words[0]}, {interjection}, {words[1]}"
            
            # Add filled pauses in the middle of longer sentences
            if word_count > 8 and random.random() < self.filled_pause_prob * context_multiplier:
                enhanced = self._insert_filled_pause(enhanced)
            
            # Add hesitation for uncertainty or thinking
            if random.random() < self.hesitation_prob * context_multiplier:
                enhanced = self._add_hesitation(enhanced, is_question)
            
            # Add discourse markers for emphasis or clarification
            if word_count > 10 and random.random() < self.discourse_marker_prob * context_multiplier * 0.5:
                enhanced = self._insert_discourse_marker(enhanced)
            
            enhanced_sentences.append(enhanced)
        
        # Join sentences back together
        result = " ".join(enhanced_sentences)
        
        # Post-process: ensure proper spacing and capitalization
        result = self._clean_spacing(result)
        
        return result

    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences while preserving punctuation.
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Simple sentence splitter (could be enhanced with NLTK or spaCy)
        sentences = re.split(r'([.!?]+\s+)', text)
        
        # Recombine sentences with their punctuation
        result = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1].strip())
            else:
                result.append(sentences[i])
        
        return [s for s in result if s.strip()]

    def _select_interjection(self, sentence: str) -> Optional[str]:
        """Select appropriate interjection based on sentence context.
        
        Args:
            sentence: The sentence to analyze
            
        Returns:
            Selected interjection or None
        """
        sentence_lower = sentence.lower()
        
        # Check for surprise words
        if any(word in sentence_lower for word in ["amazing", "incredible", "surprising"]):
            return random.choice(self.INTERJECTIONS["surprise"])
        
        # Check for understanding/clarity
        if any(word in sentence_lower for word in ["understand", "clear", "see", "get it"]):
            return random.choice(self.INTERJECTIONS["understanding"])
        
        # Check for thinking/considering
        if any(word in sentence_lower for word in ["think", "consider", "maybe", "might"]):
            return random.choice(self.INTERJECTIONS["thinking"])
        
        # Check for agreement
        if any(word in sentence_lower for word in ["agree", "correct", "exactly", "yes"]):
            return random.choice(self.INTERJECTIONS["agreement"])
        
        # Check for uncertainty
        if any(word in sentence_lower for word in ["not sure", "uncertain", "don't know"]):
            return random.choice(self.INTERJECTIONS["uncertainty"])
        
        # Default: random interjection from thinking or understanding
        if random.random() < 0.5:
            return random.choice(self.INTERJECTIONS["thinking"])
        return None

    def _insert_filled_pause(self, sentence: str) -> str:
        """Insert a filled pause in the middle of a sentence.
        
        Args:
            sentence: Input sentence
            
        Returns:
            Sentence with filled pause
        """
        words = sentence.split()
        if len(words) < 5:
            return sentence
        
        # Insert pause around 30-60% into the sentence
        insert_position = int(len(words) * random.uniform(0.3, 0.6))
        pause = random.choice(self.FILLED_PAUSES)
        
        # Insert pause with ellipsis for natural timing
        words.insert(insert_position, f"{pause}...")
        
        return " ".join(words)

    def _add_hesitation(self, sentence: str, is_question: bool) -> str:
        """Add hesitation patterns to express uncertainty or thinking.
        
        Args:
            sentence: Input sentence
            is_question: Whether the sentence is a question
            
        Returns:
            Sentence with hesitation
        """
        if is_question:
            # Add thinking interjection before question
            if random.random() < 0.6:
                thinking = random.choice(self.INTERJECTIONS["thinking"])
                return f"{thinking}... {sentence}"
        
        # Add hedging discourse marker
        hedging = random.choice(self.DISCOURSE_MARKERS["hedging"])
        words = sentence.split()
        
        # Insert hedging early in sentence
        if len(words) > 3:
            insert_pos = random.randint(1, min(3, len(words) - 1))
            words.insert(insert_pos, hedging)
        
        return " ".join(words)

    def _insert_discourse_marker(self, sentence: str) -> str:
        """Insert discourse marker for emphasis or clarification.
        
        Args:
            sentence: Input sentence
            
        Returns:
            Sentence with discourse marker
        """
        words = sentence.split()
        if len(words) < 6:
            return sentence
        
        # Choose marker type based on sentence structure
        if "," in sentence:
            marker = random.choice(self.DISCOURSE_MARKERS["clarification"])
        elif random.random() < 0.5:
            marker = random.choice(self.DISCOURSE_MARKERS["emphasis"])
        else:
            marker = random.choice(self.DISCOURSE_MARKERS["transition"])
        
        # Insert around middle of sentence, preferably after a comma
        if "," in sentence:
            parts = sentence.split(",", 1)
            return f"{parts[0]}, {marker}, {parts[1]}"
        else:
            insert_pos = len(words) // 2
            words.insert(insert_pos, f"{marker},")
        
        return " ".join(words)

    def _clean_spacing(self, text: str) -> str:
        """Clean up spacing and ensure proper formatting.
        
        Args:
            text: Input text
            
        Returns:
            Cleaned text
        """
        # Fix multiple spaces
        text = re.sub(r"\s+", " ", text)
        
        # Fix spacing around punctuation
        text = re.sub(r"\s+([.,!?])", r"\1", text)
        text = re.sub(r"([.,!?])([A-Za-z])", r"\1 \2", text)
        
        # Fix ellipsis spacing
        text = re.sub(r"\.\.\.\s+", "... ", text)
        
        # Ensure first letter is capitalized
        if text:
            text = text[0].upper() + text[1:]
        
        return text.strip()

