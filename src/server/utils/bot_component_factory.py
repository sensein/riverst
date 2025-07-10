import os
from typing import Optional, Tuple, Literal, List, Dict, Any
from dataclasses import dataclass

from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai_realtime_beta import (
    InputAudioNoiseReduction, InputAudioTranscription,
    OpenAIRealtimeBetaLLMService, SemanticTurnDetection, SessionProperties
)
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService, GeminiMultimodalModalities

from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
import json
from .animation_handler import AnimationHandler

ModalityType = Literal["classic", "e2e"]
LLMType = Literal["openai", "openai_realtime_beta", "gemini", "llama3.2"]
STTType = Literal["openai", "whisper"]
TTSType = Literal["kokoro", "elevenlabs"]

ALLOWED_LLM = {
    "classic": {"openai", "llama3.2"},
    "e2e": {"openai_realtime_beta", "gemini"},
}

@dataclass
class BotComponentFactory:
    session_dir: str
    user_id: str
    modality: ModalityType
    llm_type: LLMType
    llm_params: Optional[Dict[str, Any]] = None
    stt_type: Optional[STTType] = None
    stt_params: Optional[Dict[str, Any]] = None
    tts_type: Optional[TTSType] = None
    advanced_flows: bool = False
    flow_params: Optional[Dict[str, Any]] = None
    long_term_memory: bool = False

    task_description: str = ""
    user_description: Optional[str] = None
    avatar_personality_description: str = ""
    avatar_system_prompt: str = ""
    body_animations: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    avatar: Dict[str, Any] = None
    animation_instruction: str = ""

    def __post_init__(self):
        if self.llm_type not in ALLOWED_LLM[self.modality]:
            raise ValueError(f"LLM '{self.llm_type}' not allowed for modality '{self.modality}'.")

        if self.modality == "classic" and (not self.stt_type or not self.tts_type):
            raise ValueError("Both 'stt_type' and 'tts_type' are required in 'classic' modality.")

        if self.modality == "e2e" and (self.stt_type):
            print("'stt_type' will be ignored in 'e2e' mode.")
        if self.modality == "e2e" and not self.tts_type:
            raise ValueError("'tts_type' is required in 'e2e' mode.")

        if self.llm_type.startswith("openai") or self.stt_type == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise EnvironmentError("Missing OPENAI_API_KEY in environment.")
        if self.llm_type == "gemini":
            if not os.getenv("GOOGLE_API_KEY"):
                raise EnvironmentError("Missing GOOGLE_API_KEY in environment.")

        if self.tts_type == "elevenlabs":
            if not os.getenv("ELEVENLABS_API_KEY"):
                raise EnvironmentError("Missing ELEVENLABS_API_KEY in environment.")

        if self.body_animations:
            valid_ids = AnimationHandler.get_valid_animation_ids()
            invalid = [a for a in self.body_animations if a not in valid_ids]
            if invalid:
                raise ValueError(f"Invalid animations: {invalid}. Allowed: {sorted(valid_ids)}")

    def build_instruction(self) -> str:
        instruction = f"{self.avatar_system_prompt}\n"
        self.animation_instruction = AnimationHandler.get_animation_instruction(self.body_animations)
        if self.animation_instruction:
            instruction += self.animation_instruction
        if self.languages:
            print(f"Supported languages: {self.languages}")
            instruction += (
                f"You are restricted to understanding and responding in the following languages only: "
                f"{', '.join(self.languages)}. Do NOT respond in any language outside if {', '.join(self.languages)}. "
                f"If that language is among {', '.join(self.languages)}, reply in the same language used by the user in the last interaction.\n"
                f"If the lanugage is NOT among {', '.join(self.languages)}, reply in one and only one of these languages ({', '.join(self.languages)}) with a message indicating "
                f"that you do not understand or speak that language and pretend you do not understand the user.\n"
                f"For instance, if the user speaks in Spanish and you only understand English, "
                f"reply in English with a message indicating that you do not understand or speak that language and pretend you do not understand the user.\n"
            )
            #TODO: we may improve this by adding a language detection tool!!
        instruction += f"Avatar description: {self.avatar_personality_description}\n"
        instruction += f"Task description: {self.task_description}\n"
        if self.user_description:
            instruction += f"User description: {self.user_description}\n"
        return instruction.strip()

    def build_tools(self) -> ToolsSchema:
        animation_schema = AnimationHandler.build_animation_tools_schema(self.body_animations)
        self.used_animations = animation_schema.get("properties", {}).get("animation_id", {}).get("enum", [])
        
        return ToolsSchema(standard_tools=[
            FunctionSchema(
                name=animation_schema["name"],
                description=animation_schema["description"],
                properties=animation_schema["properties"],
                required=animation_schema["required"],
            )
        ])

    async def build(self) -> Tuple[
        Optional[object],  # STT
        object,            # LLM
        ToolsSchema,    # tools
        str,        # instruction
        object,            # context
        object,            # context_aggregator
        object,            # used_animations
        str,        # animation_instruction
        
    ]:
        stt, llm = None, None
        instruction = self.build_instruction()
        tools = self.build_tools()

        if self.modality == "classic":
            if self.stt_type == "openai":
                stt = OpenAISTTService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.stt_params or {}).get("model", "gpt-4o-transcribe"),
                    audio_passthrough=True,
                    prompt=(self.stt_params or {}).get("prompt", None),
                )
            elif self.stt_type == "whisper":
                stt = WhisperSTTService(audio_passthrough=True)

            if self.llm_type == "openai":
                llm = OpenAILLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-4o-mini")
                )
            elif self.llm_type == "llama3.2":
                llm = OLLamaLLMService(model=self.llm_type)

        elif self.modality == "e2e":
            if self.llm_type == "openai_realtime_beta":
                props = SessionProperties(
                    input_audio_transcription=InputAudioTranscription(),
                    turn_detection=SemanticTurnDetection(),
                    input_audio_noise_reduction=InputAudioNoiseReduction(type="near_field"),
                    instructions=instruction,
                    modalities=["text"],
                )
                llm = OpenAIRealtimeBetaLLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model=(self.llm_params or {}).get("model", "gpt-4o-realtime-preview-2024-12-17"),
                    session_properties=props,
                )
            elif self.llm_type == "gemini":
                llm = GeminiMultimodalLiveLLMService(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    transcribe_user_audio=True,
                    system_instruction=instruction,
                    tools=tools,
                    modalities=GeminiMultimodalModalities.TEXT
                )

        messages = []
        messages.append({"role": "system", "content": instruction})
        if self.long_term_memory:
            print("Building long term memory...")
            parent_dir = os.path.dirname(self.session_dir)
            print("Parent directory:", parent_dir)
            current_session_name = os.path.basename(self.session_dir)

            # Get all previous sessions for this user
            user_sessions = sorted([
                d for d in os.listdir(parent_dir)
                if d.startswith(self.user_id) and d != current_session_name and os.path.isdir(os.path.join(parent_dir, d))
            ])

            print("Previous sessions for this user:", user_sessions)

            all_past_messages = []
            for session_id in user_sessions:
                session_path = os.path.join(parent_dir, session_id)
                transcript_path = os.path.join(session_path, "transcript.json")
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            # Add a system message before each session's messages
                            all_past_messages.append({
                                "role": "system",
                                "content": f"--- Start of previous session `{session_id}` ---"
                            })
                            for message in data:
                                if "role" in message and "content" in message:
                                    all_past_messages.append({
                                        "role": message["role"] if message["role"] == "user" else "assistant",
                                        "content": message["content"]
                                    })
                            all_past_messages.append({
                                "role": "system",
                                "content": f"--- End of previous session `{session_id}` ---"
                            })
                    except Exception as e:
                        print(f"Error loading transcript from {session_id}: {e}")
                        continue

            if all_past_messages:
                messages.extend(all_past_messages)

        print("messages before this session:", messages)

        transcript_path = os.path.join(self.session_dir, "transcript.json")
        if os.path.exists(transcript_path):
            print("Loading transcript.json from:", transcript_path)
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)

                    messages.append({"role": "system", "content": "--- Start of the current session ---"})
                    for message in transcript_data:
                        messages.append({
                            "role": message["role"] if message["role"] == "user" else "assistant",
                            "content": message["content"],
                        })
                    messages.append({
                        "role": "system",
                        "content": "Please continue the conversation from where you left. There has been an interruption. Make a summary of the conversation so far before continuing.",
                    })
            except Exception as e:
                print(f"Failed to load transcript.json: {e}")
                raise ValueError("Failed to load transcript.json")
        else:
            print("No transcript.json found. Starting a new conversation.")
            if self.long_term_memory and all_past_messages:
                print("Still, be aware of the previous sessions.")
                messages.append({
                    "role": "system",
                    "content": "Please make a summary of the previous conversations so far (stressing goals and achievements), and then continue the conversation from where you left.",
                })


        print("Messages of this session:", messages)

        context = OpenAILLMContext(messages=messages, tools=tools, tool_choice="auto")
        context_aggregator = llm.create_context_aggregator(context=context)

        return stt, llm, tools, instruction, context, context_aggregator, self.used_animations, self.animation_instruction
