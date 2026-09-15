"""Which model backends a deployment should offer.

Some backends run as local models on the box (ollama for the LLM, Whisper for
STT, Kokoro for TTS) and some are hosted APIs. The hosted deployment runs on a
deliberately GPU-less EC2 instance to keep costs down. Those models *would* run
there on CPU -- this is a policy about what is worth offering, not a claim that
the machine is incapable -- but inference is slow enough that exposing the
option to users is worse than not having it. (ollama additionally needs a
separate server that the CPU runbook never installs, so that one fails
outright.)

That asymmetry used to be handled by maintaining a separate `cpu_aws` branch
with those options stripped out of the activity configs by hand. It drifted
behind main, conflicted on every change to a session config, and was defeated
anyway by the client overriding the server's option list. Filtering here
instead lets both deployments run the same branch.

Driven by RIVERST_COMPUTE_DEVICE, which the hosted deployment already sets.
Note what that overloads: the variable used to mean only "place torch execution
on CPU", so a self-hosted GPU-less operator who set it for that reason will now
also lose the local options from their dropdowns. That is a behaviour change for
them, not just for the hosted site. RIVERST_LOCAL_MODELS=true is the escape
hatch -- it keeps the options while still forcing CPU execution -- and
env.example documents it on the RIVERST_COMPUTE_DEVICE line where such an
operator would be looking.

Deployments that leave RIVERST_COMPUTE_DEVICE at "auto" (its default, and what
docker-compose.yaml sets) are unaffected and keep every option.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from loguru import logger

COMPUTE_DEVICE_ENV_VAR = "RIVERST_COMPUTE_DEVICE"
VALID_COMPUTE_DEVICE_POLICIES = ("auto", "cpu")
LOCAL_MODELS_ENV_VAR = "RIVERST_LOCAL_MODELS"

# Session-config keys whose values name a model backend.
SERVICE_OPTION_KEYS = ("llm_type", "stt_type", "tts_type")


@dataclass(frozen=True)
class Backend:
    """One selectable model backend.

    Attributes:
        slot: The session-config key this value appears under.
        value: The value as written in a config enum.
        kind: What the backend actually is. This is *not* the same as `slot`:
            `openai_gpt-realtime` fills the `llm_type` slot but is a
            speech-to-speech model ("s2s"), not an LLM -- in e2e modality it
            replaces the whole stt -> llm -> tts chain rather than sitting in
            the middle of it. `llm_type` is an overloaded key, and conflating
            the two is what makes ALLOWED_LLM read as arbitrary.
        runtime: "hosted" (needs a credential) or "local" (runs on the box).
        credential: Env var the backend needs, or None.
        modalities: Pipeline modalities this backend can be used in.
        match: How `value` matches a config value. "exact" for a fixed name;
            "prefix" when the builder accepts a whole family, as
            `_build_llm_service` does for any value starting `ollama/`. A
            family must be registered as a prefix, or the registry would
            withhold every member the enum happens not to name.
    """

    slot: str
    value: str
    kind: str
    runtime: str
    credential: Optional[str]
    modalities: FrozenSet[str]
    match: str = "exact"

    @property
    def is_local(self) -> bool:
        """Whether this backend runs as a local model on the machine."""
        return self.runtime == "local"


# The single declaration of every selectable backend. Everything else in this
# module, and ALLOWED_LLM in bot/core/component_factory.py, derives from it --
# so adding a backend is one entry here rather than an edit in four places.
#
# Keyed on (slot, value): "openai" appears under all three slots.
BACKENDS: Tuple[Backend, ...] = (
    Backend(
        "llm_type",
        "openai",
        "llm",
        "hosted",
        "OPENAI_API_KEY",
        frozenset({"classic"}),
    ),
    Backend(
        "llm_type",
        "openai_gpt-realtime",
        "s2s",
        "hosted",
        "OPENAI_API_KEY",
        frozenset({"e2e"}),
    ),
    # A prefix, not one model: component_factory's `_build_llm_service` takes
    # any `ollama/<model>` and passes the suffix straight through, so pinning
    # the single model today's configs happen to name would silently strip a
    # second one a self-hoster added -- a working capability on main, and the
    # population this filtering is meant to leave alone.
    Backend(
        "llm_type",
        "ollama/",
        "llm",
        "local",
        None,
        frozenset({"classic"}),
        match="prefix",
    ),
    Backend(
        "stt_type",
        "openai",
        "stt",
        "hosted",
        "OPENAI_API_KEY",
        frozenset({"classic"}),
    ),
    # No credential: component_factory loads the `tiny` model, which is public
    # on Hugging Face. env.example notes HF_TOKEN is needed for "many models",
    # but requiring it here would hide Whisper from any GPU box that has not
    # set one, for a model that does not need it.
    Backend(
        "stt_type",
        "whisper",
        "stt",
        "local",
        None,
        frozenset({"classic"}),
    ),
    Backend(
        "tts_type",
        "openai",
        "tts",
        "hosted",
        "OPENAI_API_KEY",
        frozenset({"classic"}),
    ),
    Backend(
        "tts_type",
        "kokoro",
        "tts",
        "local",
        None,
        frozenset({"classic"}),
    ),
    # Implemented in component_factory (ElevenLabsTTSService, its credential
    # check and _get_voice_id_for_elevenlabs) but offered by no activity today.
    # Registered anyway: this is an allow-list, so omitting an implemented
    # backend would hard-reject a config that names it.
    Backend(
        "tts_type",
        "elevenlabs",
        "tts",
        "hosted",
        "ELEVENLABS_API_KEY",
        frozenset({"classic"}),
    ),
)

# NOT registered, deliberately: `gemini` (GeminiMultimodalLiveLLMService in
# component_factory) is implemented but offered by no activity, and registering
# it would arm a latent bug. SettingsForm.tsx decides classic-vs-e2e with
# `value.startsWith('openai_gpt-realtime')`, so an e2e backend under any other
# name renders in the *classic* dropdown and then fails ALLOWED_LLM at session
# start. Registering it means first teaching the client to read modality
# eligibility from here instead of inferring it from the name;
# ClientCouplingTest fails if that is forgotten.

# Exact rows only. A prefix row's `value` ("ollama/") is a family marker, not
# a selectable value, so indexing it here would make the bare prefix resolve as
# a backend in its own right.
_BY_SLOT_VALUE: Dict[Tuple[str, str], Backend] = {
    (b.slot, b.value): b for b in BACKENDS if b.match == "exact"
}


def lookup(slot: str, value: str) -> Optional[Backend]:
    """Find the registered backend for a config slot and value.

    Args:
        slot: A key from SERVICE_OPTION_KEYS.
        value: The value as written in the config enum.

    Returns:
        The Backend, or None if nothing is registered for that pair.
    """
    exact = _BY_SLOT_VALUE.get((slot, value))
    if exact is not None:
        return exact
    for backend in BACKENDS:
        if (
            backend.match == "prefix"
            and backend.slot == slot
            and value.startswith(backend.value)
            and value != backend.value
        ):
            return backend
    return None


def llm_allowed_for_modality(modality: str, value: str) -> bool:
    """Whether a pipeline modality accepts this `llm_type` value.

    A predicate rather than a modality-to-values mapping, because a registered
    family (`ollama/<model>`) has no finite value set to enumerate. Derived so
    the modality/backend pairing is stated once, in BACKENDS.

    Args:
        modality: "classic" or "e2e".
        value: The `llm_type` value from the session config.

    Returns:
        True if some registered llm_type backend matches `value` and declares
        `modality`.
    """
    backend = lookup("llm_type", value)
    return backend is not None and modality in backend.modalities


def _env_flag(name: str) -> Optional[bool]:
    """Read a tri-state boolean env var: true, false, or unset."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"Invalid {name}={raw!r}. Expected a boolean such as true/false.")


def compute_device_policy() -> str:
    """The configured compute device policy, validated.

    Read here rather than imported from device_utils, which imports torch at
    module scope -- this module is pure dict manipulation and its tests should
    not need the model stack to run.

    An exported-but-empty value is an error rather than a default: this value
    now also decides which backends are offered, so silently treating a blank
    unit-file entry as "auto" would re-enable local models on the one
    deployment that must not have them.
    """
    policy = os.getenv(COMPUTE_DEVICE_ENV_VAR, "auto").strip().lower()
    if policy not in VALID_COMPUTE_DEVICE_POLICIES:
        raise ValueError(
            f"Invalid {COMPUTE_DEVICE_ENV_VAR}={policy!r}. "
            f"Expected one of {sorted(VALID_COMPUTE_DEVICE_POLICIES)}."
        )
    return policy


def validate_deployment_env() -> None:
    """Raise if either deployment knob is malformed.

    Called once at startup. Otherwise a typo surfaces as a generic 500 on every
    activity-settings request, because that handler wraps everything in a broad
    `except Exception` and the real reason only reaches the log.
    """
    compute_device_policy()
    _env_flag(LOCAL_MODELS_ENV_VAR)


def local_models_enabled() -> bool:
    """Whether this deployment should offer locally-run models.

    RIVERST_LOCAL_MODELS wins if set. Otherwise local models are offered unless
    the compute device policy is "cpu".
    """
    override = _env_flag(LOCAL_MODELS_ENV_VAR)
    if override is not None:
        return override
    return compute_device_policy() != "cpu"


def option_unavailable_reason(
    slot: str, value: str, allow_local: bool
) -> Optional[str]:
    """Why an option cannot be offered, or None if it can.

    Args:
        slot: A key from SERVICE_OPTION_KEYS.
        value: The value as written in the config enum.
        allow_local: Whether locally-run models are offered here.

    Returns:
        A short human-readable reason, or None when the option is available.
    """
    backend = lookup(slot, value)
    if backend is None:
        # Not in BACKENDS, so nothing here knows what it needs. Refused rather
        # than offered, so a config naming an unregistered backend fails
        # visibly instead of at connect time.
        return f"not registered as a {slot} backend (see capabilities.py)"
    if backend.is_local and not allow_local:
        return "runs locally; not offered on this deployment (too slow without a GPU)"
    if backend.credential and not os.getenv(backend.credential):
        return f"needs {backend.credential}"
    return None


def filter_service_options(
    options_props: Dict[str, Any],
    allow_local: Optional[bool] = None,
) -> Dict[str, List[Tuple[str, str]]]:
    """Remove unofferable backends from a session config, in place.

    Repairs `default` when the configured default was removed, and drops the key
    entirely when nothing usable is left -- an empty enum would render as a
    Select the user cannot fill.

    Args:
        options_props: The `properties.options.properties` object of a session
            config. Mutated in place.
        allow_local: Override for whether local models are offered. Defaults to
            `local_models_enabled()`.

    Returns:
        Mapping of option key to the (value, reason) pairs that were removed.
    """
    if allow_local is None:
        allow_local = local_models_enabled()

    removed: Dict[str, List[Tuple[str, str]]] = {}

    for key in SERVICE_OPTION_KEYS:
        prop = options_props.get(key)
        if not isinstance(prop, dict):
            continue

        # A prop may pin its value with `const` and carry no `enum`. Treating
        # that as nothing to filter would let an unofferable backend through.
        candidates = prop.get("enum")
        pinned = prop.get("const")
        if candidates is None:
            if pinned is None:
                continue
            candidates = [pinned]

        kept: List[str] = []
        for value in candidates:
            reason = option_unavailable_reason(key, value, allow_local)
            if reason is None:
                kept.append(value)
            else:
                removed.setdefault(key, []).append((value, reason))

        # Both decided before any rewriting below, so neither depends on what
        # has already been stripped.
        if not kept:
            logger.warning(f"No offerable backend left for '{key}' after filtering.")
            del options_props[key]
            continue
        if pinned is not None and pinned not in kept:
            # The author pinned one value and it is not offerable here, so this
            # activity cannot run on this deployment. Left exactly as shipped:
            # un-pinning would widen the field to alternatives they excluded,
            # and deleting the key would let the form submit a config with the
            # key missing and fail server-side. As-is the prop stays
            # unsatisfiable, so validation fails and Confirm stays disabled --
            # visibly broken rather than silently broken.
            logger.warning(
                f"Pinned '{key}' value {pinned!r} is not offerable here; "
                f"leaving the option unsatisfiable rather than rewriting it."
            )
            # Replaces the per-value entries recorded above rather than adding
            # to them: this path leaves the prop exactly as shipped, so
            # reporting those would tell the caller options were hidden from a
            # prop nothing touched, and would name the pinned value twice.
            removed[key] = [
                (pinned, "pinned value is not offerable on this deployment")
            ]
            continue

        if "enum" in prop:
            prop["enum"] = kept
        if "default" in prop and prop["default"] not in kept:
            prop["default"] = kept[0]

    return removed


def _modality_is_servable(options_props: Dict[str, Any], modality: str) -> bool:
    """Whether a modality has every backend it needs still on offer.

    Args:
        options_props: A filtered `properties.options.properties` object.
        modality: The pipeline modality to check.

    Returns:
        True if the modality can actually run here.
    """

    def offered(slot: str) -> List[str]:
        prop = options_props.get(slot, {})
        if "enum" in prop:
            return list(prop["enum"])
        # filter_service_options supports a prop pinned with `const` and no
        # `enum`; ignoring that would make this silently report "nothing
        # offered" and prune a modality that works.
        return [prop["const"]] if "const" in prop else []

    has_llm = any(
        modality in backend.modalities
        for value in offered("llm_type")
        for backend in (lookup("llm_type", value),)
        if backend is not None
    )
    if not has_llm:
        return False
    if modality == "classic":
        # component_factory requires both in classic modality, so a modality
        # whose stt or tts was filtered away cannot run even with an LLM left.
        return bool(offered("stt_type")) and bool(offered("tts_type"))
    return True


def apply_deployment_policy(options_props: Dict[str, Any]) -> Dict[str, Any]:
    """Apply every deployment-dependent adjustment, in the required order.

    A single entry point on purpose: the steps are order-dependent (options
    must be filtered before servability can be judged, and servability must be
    known before a default is chosen), and exposing them separately invited
    getting that wrong.

    Args:
        options_props: The `properties.options.properties` object of a session
            config. Mutated in place.

    Returns:
        {"removed_options": {key: [(value, reason)]},
         "pruned_modalities": [str],
         "modality_default": str | None} for logging.
    """
    removed = filter_service_options(options_props)
    pruned = _prune_unservable_modalities(options_props)
    default = _prefer_low_latency_modality(options_props)
    return {
        "removed_options": removed,
        "pruned_modalities": pruned,
        "modality_default": default,
    }


def _prune_unservable_modalities(options_props: Dict[str, Any]) -> List[str]:
    """Drop pipeline modalities that cannot run here, in place.

    Never empties the enum, and never touches a pinned `pipeline_modality`:
    rewriting a pin would either relax the author's choice or leave it
    unsatisfiable and unfixable, since a pinned field renders no control.
    """
    prop = options_props.get("pipeline_modality")
    if not isinstance(prop, dict) or "enum" not in prop:
        return []
    if "const" in prop:
        return []

    servable = [m for m in prop["enum"] if _modality_is_servable(options_props, m)]
    dropped = [m for m in prop["enum"] if m not in servable]
    if not dropped:
        return []
    if not servable:
        # Nothing runs here. Leaving the config alone keeps it visibly broken
        # rather than manufacturing an empty enum on top.
        logger.warning("No pipeline modality is servable; leaving the config alone.")
        return []

    prop["enum"] = servable
    if prop.get("default") not in servable:
        prop["default"] = servable[0]
    return dropped


def _prefer_low_latency_modality(options_props: Dict[str, Any]) -> Optional[str]:
    """Default to `e2e` on the hosted deployment where it is servable.

    The speech-to-speech path has noticeably lower latency on the hosted CPU
    box than running stt -> llm -> tts as three separate hosted calls.

    Gated on the compute-device policy rather than `local_models_enabled()`:
    RIVERST_LOCAL_MODELS is an independent override for local models and should
    not silently rewrite an activity's modality.

    Also repairs `llm_type.default`, so the served schema's defaults are a pair
    `BotComponentFactory` accepts rather than one it rejects.
    """
    if compute_device_policy() != "cpu":
        return None
    prop = options_props.get("pipeline_modality")
    if not isinstance(prop, dict) or "const" in prop:
        return None
    if "e2e" not in prop.get("enum", []):
        return None
    # Servability is re-checked rather than assumed: the pruner leaves the
    # config alone when nothing is servable, which is exactly the case where
    # e2e must not become the default.
    if not _modality_is_servable(options_props, "e2e"):
        return None
    if prop.get("default") == "e2e":
        return None

    prop["default"] = "e2e"

    # Keep the default pair self-consistent: llm_type's shipped default is a
    # classic backend, which is invalid in e2e.
    llm_prop = options_props.get("llm_type", {})
    for value in llm_prop.get("enum", []):
        backend = lookup("llm_type", value)
        if backend and "e2e" in backend.modalities:
            llm_prop["default"] = value
            break
    return "e2e"
