"""Custom OLLama LLM Service"""

from pipecat.services.ollama.llm import OLLamaLLMService


class CustomOLLamaLLMService(OLLamaLLMService):
    def __init__(self, **kwargs):
        # Force think=False regardless of what the caller provides
        # See https://ollama.com/blog/thinking
        # This hasn't been tested yet, but it shouldn't break anything
        kwargs["think"] = False
        super().__init__(**kwargs)
