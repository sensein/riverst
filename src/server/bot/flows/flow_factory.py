import json
from typing import Any, Optional, List

from loguru import logger
from pipecat.pipeline.task import PipelineTask
from pipecat_flows import FlowManager, ContextStrategy, ContextStrategyConfig

from ..flows import load_config
from ..components.llm_tools.animation_handler import AnimationHandler


class FlowComponentFactory:
    """Factory class for creating and initializing flow management components.

    This class encapsulates the creation and configuration of flow-related
    components, ensuring proper initialization and error handling.
    """

    def __init__(
        self,
        llm: Any,
        context_aggregator: Any,
        task: PipelineTask,
        advanced_flows: bool = False,
        flow_config_path: Optional[str] = None,
        activity_variables_path: Optional[str] = None,
        user_activity_variables: Optional[dict[str, Any]] = None,
        user_description: Optional[str] = None,
        enabled_animations: Optional[List[str]] = None,
        end_conversation_handler: Optional[Any] = None,
        context_strategy: ContextStrategy = ContextStrategy.RESET,
        summary_prompt: str = (
            "Summarize the key moments of learning, words, and concepts discussed in the tutoring session so far. "
            "Keep it concise and focused on vocabulary learning."
        ),
    ):
        """Initialize the FlowComponentFactory.

        Args:
            llm: The language model to use with the flow manager
            context_aggregator: The context aggregator component
            task: The pipeline task
            advanced_flows: Whether to use advanced flows (default: False)
            flow_config_path: Path to the flow configuration file
            activity_variables_path: Path to the activity variables file (e.g. book)
            user_activity_variables: User-activity specific variables (e.g. current_chapter)
            user_description: Description of the user for context
            animation_instruction: Instruction for animations of the avatar
            end_conversation_handler: Handler for ending conversations
            context_strategy: Strategy for managing context
            summary_prompt: Prompt for summarizing conversation
        """
        self.llm = llm
        self.context_aggregator = context_aggregator
        self.task = task
        self.advanced_flows = advanced_flows
        self.flow_config_path = flow_config_path
        self.activity_variables_path = activity_variables_path
        self.user_activity_variables = user_activity_variables or {}
        self.user_description = user_description
        self.enabled_animations = enabled_animations or []
        self.context_strategy = context_strategy
        self.summary_prompt = summary_prompt
        self.end_conversation_handler = end_conversation_handler
        self.flow_manager = None

    def build(self) -> Optional[FlowManager]:
        """Build and configure the flow manager.

        Returns:
            FlowManager: The configured flow manager, or None if flows are disabled
        """
        if not self.advanced_flows:
            logger.info("Advanced flows disabled, skipping flow manager initialization")
            return None

        logger.info(f"Initializing flow manager with config path: {self.flow_config_path}")
        if not self.activity_variables_path:
            logger.warning("activity variables path not provided, using default within flow config file")
        else:
            logger.info(f"activity variables path: {self.activity_variables_path}")

        if not self.flow_config_path:
            logger.error("Flow config path not provided but advanced_flows is enabled")
            return None

        try:
            flow_config, state = load_config(
                self.flow_config_path,
                self.activity_variables_path,
                self.user_activity_variables,
                end_conversation_handler=self.end_conversation_handler,
            )

            # Modify system messages in all nodes to include user description and animation instruction, and tools
            for node_id, node_data in flow_config.get("nodes", {}).items():
                self._add_llm_tools_to_node(node_data)
                if "role_messages" in node_data:
                    self._update_system_message(node_data["role_messages"])
                if node_id == "vocab":
                    self._inject_chapter_index_into_node(node_data)
                    self._inject_vocab_override_into_node(node_data, state)

            flow_manager = FlowManager(
                llm=self.llm,
                context_aggregator=self.context_aggregator,
                context_strategy=ContextStrategyConfig(
                    strategy=self.context_strategy,
                    summary_prompt=self.summary_prompt,
                ),
                task=self.task,
                flow_config=flow_config,
            )

            flow_manager.state.update(state)

            self.flow_manager = flow_manager
            logger.info("Flow manager successfully built")
            return flow_manager

        except FileNotFoundError as e:
            logger.error(f"Flow configuration file not found: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in flow configuration file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error initializing flow manager: {e}")
            return None

    async def initialize(self) -> bool:
        """Initialize the flow manager asynchronously.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        logger.info("DEBUG: Starting flow manager initialization")
        if not self.flow_manager:
            logger.warning("Flow manager not built, cannot initialize")
            return False
        try:
            logger.info(
                "DEBUG: Flow manager about to initialize with config: {}",
                {k: v for k, v in self.flow_manager.flow_config.items() if k != "nodes"},
            )
            logger.info(
                "DEBUG: Initial node: {}",
                self.flow_manager.flow_config.get("initial_node"),
            )
            logger.info("DEBUG: Available nodes: {}", list(self.flow_manager.nodes.keys()))

            await self.flow_manager.initialize()

            logger.info(
                "DEBUG: Flow manager state after initialization: {}",
                self.flow_manager.state,
            )
            logger.info(
                "DEBUG: Current node after initialization: {}",
                self.flow_manager.current_node,
            )
            logger.info("Flow manager successfully initialized")
            return True
        except Exception as e:
            logger.error("DEBUG: Error during flow manager initialization: {}", e)
            import traceback

            logger.error("DEBUG: Traceback: {}", traceback.format_exc())
            return False

    def _add_llm_tools_to_node(self, node_data):
        """Add existing LLM tools to node functions"""
        if "functions" not in node_data:
            return

        # Create lookup for tool schemas by function name
        tool_schemas = {
            schema.get("function", {}).get("name"): schema for schema in self.context_aggregator._user.context.tools
        }

        for func_name, tool in self.llm._functions.items():
            if func_name in tool_schemas:
                function = tool_schemas[func_name]["function"]
                parameters = function.get("parameters", {})

                node_data["functions"].append(
                    {
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "description": function.get("description"),
                            "parameters": {
                                "type": "object",
                                "properties": parameters.get("properties", {}),
                                "required": parameters.get("required", []),
                            },
                            "handler": tool.handler,
                        },
                    }
                )

    def _inject_chapter_index_into_node(self, node_data: dict) -> None:
        """Prepend the known chapter index to the vocab node task prompt so it survives context reset."""
        index = self.user_activity_variables.get("index")
        if index is None:
            return
        task_msg = next(
            (m for m in node_data.get("task_messages", []) if m.get("role") == "system"),
            None,
        )
        if task_msg:
            task_msg["content"] = f"Key Information — Chapter Number: {index}\n\n" + task_msg["content"]

    def _inject_vocab_override_into_node(self, node_data: dict, state: dict) -> None:
        """Append teacher override word list to the vocab node task prompt when present.

        For each override word, looks up the curated vocab entry for the current chapter.
        Matched words have their full entry (sentence + context_description) injected so the
        avatar can complete the teaching pipeline without calling lookup_word_in_chapter.
        Unmatched words are injected with the word name only plus a flag instructing the avatar
        to call lookup_word_in_chapter to retrieve the book sentence at teaching time.

        Args:
            node_data: The vocab node data dict from flow_config.
            state: The fully loaded activity state, used to look up curated vocab entries.
        """
        override = self.user_activity_variables.get("vocab_override")
        if not override:
            return
        task_msg = next(
            (m for m in node_data.get("task_messages", []) if m.get("role") == "system"),
            None,
        )
        if not task_msg:
            return

        # Build a flat lookup of word → entry from the curated vocab list for the current chapter
        index = self.user_activity_variables.get("index")
        curated_lookup: dict = {}
        if index is not None:
            vocab_section = state.get("activity", {}).get("vocab", {})
            chapters = vocab_section.get("chapters", [])
            if 1 <= index <= len(chapters):
                chapter_vocab = chapters[index - 1]
                for grade_key in ("grade_4", "grade_5", "grade_6"):
                    for entry in chapter_vocab.get("vocab_words", {}).get(grade_key, []):
                        w = entry.get("word", "").strip().lower()
                        if w:
                            curated_lookup[w] = entry

        # Build per-word lines for the override block
        word_lines = []
        for word in override:
            entry = curated_lookup.get(word.strip().lower())
            if entry:
                sentence = entry.get("sentence", "")
                context = entry.get("context_description", "")
                line = f"- {word}"
                if sentence:
                    line += f"\n  Sentence from book: {sentence}"
                if context:
                    line += f"\n  Context: {context}"
            else:
                line = (
                    f"- {word}\n"
                    f"  No pre-curated sentence available. "
                    f'Call lookup_story_context(context_type="vocab_word", chapter_index=<known chapter>, word="{word}") '
                    f"to retrieve the in-story sentence before proceeding to teaching step 2."
                )
            word_lines.append(line)

        word_block = "\n".join(word_lines)
        task_msg["content"] += (
            f"\n\nTEACHER OVERRIDE ACTIVE:\n"
            f"Teach the following words FIRST, in this exact order, before selecting any words "
            f"from the grade-level list. After all override words have been taught or confirmed "
            f"already known, continue with the normal grade-level word selection to fill remaining "
            f"slots. The global 3-new-words cap applies across override and grade-level words "
            f"combined — stop teaching as soon as 3 new words total have been taught. "
            f"The skip-if-known rule applies: if the student correctly explains an override word, "
            f"it does not count toward the 3-word cap.\n\n"
            f"{word_block}"
        )

    def _update_system_message(self, role_messages):
        """Update first system message with user description and animation instruction"""
        system_msg = next((msg for msg in role_messages if msg.get("role") == "system"), None)

        if system_msg:
            if self.user_description:
                system_msg["content"] += f"\nUser description: {self.user_description}"

            if self.enabled_animations:
                animation_instruction = AnimationHandler.get_animation_instruction(self.enabled_animations)
                if animation_instruction:
                    system_msg["content"] += f"\n{animation_instruction}"

            # Add end conversation instruction
            end_conversation_instruction = self.end_conversation_handler.get_end_conversation_instruction()
            if end_conversation_instruction:
                system_msg["content"] += f"\n{end_conversation_instruction}"
