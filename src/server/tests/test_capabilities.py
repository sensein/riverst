"""Tests for deployment backend filtering.

This filtering replaces the hand-maintained `cpu_aws` branch, so the cases that
matter are the ones that branch existed to enforce: on the hosted deployment, no
locally-run backend may be offered, and every other deployment keeps them.

stdlib unittest, matching tests/test_device_utils.py.
"""

import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.utils.capabilities import (  # noqa: E402
    BACKENDS,
    SERVICE_OPTION_KEYS,
    apply_deployment_policy,
    compute_device_policy,
    filter_service_options,
    llm_allowed_for_modality,
    local_models_enabled,
    lookup,
    option_unavailable_reason,
)

ACTIVITIES_DIR = os.path.join(os.path.dirname(__file__), "..", "activities")


def _activity_configs():
    """Yield (name, options_properties) for every real activity config."""
    for name in sorted(os.listdir(ACTIVITIES_DIR)):
        path = os.path.join(ACTIVITIES_DIR, name, "session_config.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        yield name, config.get("properties", {}).get("options", {}).get(
            "properties", {}
        )


class DeploymentPolicyTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {"RIVERST_COMPUTE_DEVICE": "cpu"}, clear=True)
    def test_cpu_withholds_local_models(self):
        self.assertFalse(local_models_enabled())

    @mock.patch.dict(os.environ, {"RIVERST_COMPUTE_DEVICE": "auto"}, clear=True)
    def test_auto_offers_local_models(self):
        self.assertTrue(local_models_enabled())

    @mock.patch.dict(
        os.environ,
        {"RIVERST_COMPUTE_DEVICE": "auto", "RIVERST_LOCAL_MODELS": "false"},
        clear=True,
    )
    def test_explicit_override_wins(self):
        self.assertFalse(local_models_enabled())

    @mock.patch.dict(os.environ, {"RIVERST_COMPUTE_DEVICE": "bogus"}, clear=True)
    def test_invalid_policy_raises_rather_than_guessing(self):
        with self.assertRaises(ValueError):
            local_models_enabled()


class RegistryTest(unittest.TestCase):
    """The registry is the single declaration every other consumer derives from,
    so the thing worth guarding is that it stays in step with the configs and
    with the modality table."""

    def test_every_config_value_is_registered(self):
        """A config naming an unregistered backend would be filtered out
        wholesale at request time rather than failing visibly."""
        for name, props in _activity_configs():
            for slot in SERVICE_OPTION_KEYS:
                prop = props.get(slot, {})
                values = list(prop.get("enum", []))
                if "const" in prop:
                    values.append(prop["const"])
                for value in values:
                    self.assertIsNotNone(
                        lookup(slot, value),
                        f"{name}: {slot}={value!r} is not in BACKENDS",
                    )

    def test_every_config_value_works_in_some_permitted_modality(self):
        """An activity must not offer a backend none of its modalities accept.

        component_factory rejects the pairing at session start, so such an
        option can only ever fail. Checkable only because the registry records
        each backend's modalities.
        """
        for name, props in _activity_configs():
            modalities = set(props.get("pipeline_modality", {}).get("enum", []))
            if not modalities:
                continue
            for slot in SERVICE_OPTION_KEYS:
                for value in props.get(slot, {}).get("enum", []):
                    backend = lookup(slot, value)
                    self.assertTrue(
                        backend.modalities & modalities,
                        f"{name}: {slot}={value!r} needs one of "
                        f"{sorted(backend.modalities)} but the activity permits "
                        f"only {sorted(modalities)}",
                    )

    def test_classic_takes_llms_and_e2e_takes_speech_to_speech(self):
        """The invariant behind the derived predicate, asserted instead of a
        literal set so adding a backend does not break the test.

        classic runs stt -> llm -> tts, so it needs a text LLM. e2e replaces
        that chain with one speech-to-speech model.
        """
        for backend in BACKENDS:
            if backend.slot != "llm_type":
                continue
            for modality in backend.modalities:
                expected = "s2s" if modality == "e2e" else "llm"
                self.assertEqual(backend.kind, expected, backend.value)
            # Every registered llm_type backend reaches exactly one modality.
            self.assertEqual(len(backend.modalities), 1, backend.value)

    def test_a_registered_family_admits_members_the_enum_never_names(self):
        """component_factory's `_build_llm_service` builds any `ollama/<model>`,
        so the registry has to accept the family, not one member.

        Registering the single model today's configs ship would silently strip
        a second one a self-hoster added -- something that works on main, on
        the deployments this filtering is meant to leave alone.
        """
        for value in (
            "ollama/qwen3:4b-instruct-2507-q4_K_M",
            "ollama/llama3:8b",
        ):
            self.assertTrue(llm_allowed_for_modality("classic", value), value)
            self.assertIsNone(option_unavailable_reason("llm_type", value, True))
        # Still an allow-list: the prefix alone is not a model, and an
        # unrelated value is not admitted by it.
        self.assertFalse(llm_allowed_for_modality("classic", "ollama/"))
        self.assertFalse(llm_allowed_for_modality("classic", "llama3:8b"))
        # And a family member remains classic-only.
        self.assertFalse(llm_allowed_for_modality("e2e", "ollama/llama3:8b"))

    def test_speech_to_speech_is_not_classified_as_an_llm(self):
        """`llm_type` is an overloaded key: openai_gpt-realtime fills that slot
        but replaces the whole stt -> llm -> tts chain rather than being an
        LLM. Keeping `kind` honest is what lets the gate be derived."""
        backend = lookup("llm_type", "openai_gpt-realtime")
        self.assertEqual(backend.kind, "s2s")
        self.assertEqual(backend.modalities, frozenset({"e2e"}))

    def test_slot_and_value_together_identify_a_backend(self):
        """ "openai" is a valid llm, stt and tts value, so the registry cannot be
        keyed on value alone."""
        kinds = {slot: lookup(slot, "openai").kind for slot in SERVICE_OPTION_KEYS}
        self.assertEqual(
            kinds, {"llm_type": "llm", "stt_type": "stt", "tts_type": "tts"}
        )


class FilterTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_local_backends_hidden_on_the_hosted_deployment(self):
        for name, props in _activity_configs():
            filter_service_options(props, allow_local=False)
            for slot in SERVICE_OPTION_KEYS:
                for value in props.get(slot, {}).get("enum", []):
                    backend = lookup(slot, value)
                    self.assertFalse(
                        backend.is_local,
                        f"{name}: {slot} still offers local {value}",
                    )

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_local_backends_kept_elsewhere(self):
        offered = set()
        for _, props in _activity_configs():
            filter_service_options(props, allow_local=True)
            for slot in SERVICE_OPTION_KEYS:
                offered.update(props.get(slot, {}).get("enum", []))
        for backend in BACKENDS:
            if not backend.is_local:
                continue
            if backend.match == "prefix":
                # A family marker is not itself a config value, so look for a
                # member: some offered value has to belong to the family.
                self.assertTrue(
                    any(v.startswith(backend.value) for v in offered),
                    f"no offered value belongs to the {backend.value!r} family",
                )
            else:
                self.assertIn(backend.value, offered)

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_default_is_repaired_when_filtered_out(self):
        props = {
            "llm_type": {
                "enum": ["ollama/qwen3:4b-instruct-2507-q4_K_M", "openai"],
                "default": "ollama/qwen3:4b-instruct-2507-q4_K_M",
            }
        }
        filter_service_options(props, allow_local=False)
        self.assertEqual(props["llm_type"]["default"], "openai")

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_const_only_prop_is_still_filtered(self):
        """A prop may pin its value with `const` and carry no `enum`. Skipping
        those would be the one allow-by-default path in the module."""
        props = {"stt_type": {"const": "whisper", "default": "whisper"}}
        filter_service_options(props, allow_local=False)
        self.assertNotIn("stt_type", props)

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_key_dropped_when_nothing_is_offerable(self):
        """An empty enum would render as a Select the user cannot fill."""
        props = {
            "llm_type": {
                "enum": ["ollama/qwen3:4b-instruct-2507-q4_K_M"],
                "default": "ollama/qwen3:4b-instruct-2507-q4_K_M",
            }
        }
        filter_service_options(props, allow_local=False)
        self.assertNotIn("llm_type", props)

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_non_service_keys_untouched(self):
        props = {
            "llm_type": {"enum": ["openai"], "default": "openai"},
            "embodiment": {"enum": ["humanoid_avatar", "waveform"]},
        }
        filter_service_options(props, allow_local=False)
        self.assertEqual(props["embodiment"]["enum"], ["humanoid_avatar", "waveform"])


class ClientCouplingTest(unittest.TestCase):
    """The client narrows the llm_type dropdown by pipeline modality, but infers
    eligibility from the value's name rather than from the registry.

    That coupling is invisible from Python, so assert it here: registering an
    e2e backend the client cannot detect would otherwise silently place it in
    the classic dropdown, where the modality gate rejects it at session start.
    """

    # Mirrors SettingsForm.tsx: v.startsWith('openai_gpt-realtime')
    CLIENT_E2E_PREFIX = "openai_gpt-realtime"

    def test_e2e_backends_are_detectable_by_the_client(self):
        for backend in BACKENDS:
            if backend.slot != "llm_type":
                continue
            client_thinks_e2e = backend.value.startswith(self.CLIENT_E2E_PREFIX)
            registry_says_e2e = "e2e" in backend.modalities
            self.assertEqual(
                client_thinks_e2e,
                registry_says_e2e,
                f"{backend.value!r}: registry modalities "
                f"{sorted(backend.modalities)} disagree with what "
                f"SettingsForm.tsx infers from the name. Teach the client to "
                f"read modality eligibility from the registry before "
                f"registering this backend.",
            )


class ImplementedBackendsTest(unittest.TestCase):
    """BACKENDS is an allow-list, so a backend that component_factory builds but
    that is missing here would be hard-rejected -- silently deleting a working
    feature rather than failing loudly."""

    def test_every_implemented_backend_is_registered(self):
        for slot, value in (
            ("tts_type", "elevenlabs"),
            ("tts_type", "kokoro"),
            ("stt_type", "whisper"),
        ):
            self.assertIsNotNone(lookup(slot, value), f"{slot}={value}")

    @mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "x"}, clear=True)
    def test_registered_backend_with_its_credential_is_offerable(self):
        props = {"tts_type": {"enum": ["elevenlabs"], "default": "elevenlabs"}}
        filter_service_options(props, allow_local=False)
        self.assertEqual(props["tts_type"]["enum"], ["elevenlabs"])


class PinnedOptionTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_unofferable_pin_is_left_exactly_as_shipped(self):
        """Several activities pin a value with `const` alongside a wider `enum`.

        Three options when the pinned value is unofferable, and only one is
        safe: un-pinning widens the field to alternatives the author excluded;
        deleting the key lets the form submit a config missing that key and
        fail server-side; leaving it alone keeps the prop unsatisfiable, so
        validation fails and Confirm stays disabled -- visibly broken rather
        than silently broken.
        """
        shipped = {
            "stt_type": {
                "enum": ["whisper", "openai"],
                "const": "openai",
                "default": "openai",
            }
        }
        props = copy.deepcopy(shipped)
        removed = filter_service_options(props, allow_local=True)
        self.assertEqual(props, shipped)
        # Exactly one entry, naming the pin. main.py logs a "hiding <key>=
        # <value>" line per entry, so the per-value entries gathered before
        # this path was chosen would report options as hidden from a prop that
        # was left untouched -- and name the pinned value twice.
        self.assertEqual(
            removed["stt_type"],
            [("openai", "pinned value is not offerable on this deployment")],
        )

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_pin_survives_when_its_value_is_offerable(self):
        props = {
            "stt_type": {
                "enum": ["whisper", "openai"],
                "const": "openai",
                "default": "openai",
            }
        }
        filter_service_options(props, allow_local=False)
        self.assertEqual(props["stt_type"]["const"], "openai")


class DeploymentPolicyCompositionTest(unittest.TestCase):
    """Exercises apply_deployment_policy on the shipped configs.

    Previous tests checked the steps in isolation, which is exactly how an
    ordering bug survived: the pruner leaves the config alone when nothing is
    servable, and the modality default then fired anyway.
    """

    def _props(self, name):
        path = os.path.join(ACTIVITIES_DIR, name, "session_config.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)["properties"]["options"]["properties"]

    @mock.patch.dict(
        os.environ,
        {"RIVERST_COMPUTE_DEVICE": "cpu", "OPENAI_API_KEY": "x"},
        clear=True,
    )
    def test_hosted_deployment_serves_a_self_consistent_default_pair(self):
        """The served defaults must be a pair component_factory accepts."""
        props = self._props("basic-avatar-interaction")
        apply_deployment_policy(props)
        modality = props["pipeline_modality"]["default"]
        llm = props["llm_type"]["default"]
        self.assertEqual(modality, "e2e")
        self.assertTrue(llm_allowed_for_modality(modality, llm))

    @mock.patch.dict(os.environ, {"RIVERST_COMPUTE_DEVICE": "cpu"}, clear=True)
    def test_no_credentials_does_not_default_to_an_unservable_modality(self):
        """With no credential every backend goes, so e2e must not be chosen."""
        props = self._props("basic-avatar-interaction")
        result = apply_deployment_policy(props)
        self.assertIsNone(result["modality_default"])
        self.assertNotEqual(props["pipeline_modality"].get("default"), "e2e")

    @mock.patch.dict(
        os.environ,
        {"RIVERST_COMPUTE_DEVICE": "auto", "OPENAI_API_KEY": "x"},
        clear=True,
    )
    def test_other_deployments_keep_local_backends_and_the_shipped_default(self):
        props = self._props("basic-avatar-interaction")
        result = apply_deployment_policy(props)
        self.assertIsNone(result["modality_default"])
        self.assertIn("ollama/qwen3:4b-instruct-2507-q4_K_M", props["llm_type"]["enum"])

    @mock.patch.dict(
        os.environ,
        {
            "RIVERST_COMPUTE_DEVICE": "auto",
            "RIVERST_LOCAL_MODELS": "false",
            "OPENAI_API_KEY": "x",
        },
        clear=True,
    )
    def test_local_models_override_does_not_rewrite_the_modality(self):
        """RIVERST_LOCAL_MODELS governs local backends only; the latency
        preference is a separate, device-driven decision."""
        props = self._props("basic-avatar-interaction")
        result = apply_deployment_policy(props)
        self.assertIsNone(result["modality_default"])

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=True)
    def test_classic_needs_stt_and_tts_not_just_an_llm(self):
        """component_factory refuses classic without both, so a modality that
        lost either is not servable even with an LLM left."""
        props = {
            "pipeline_modality": {"enum": ["classic"], "default": "classic"},
            "llm_type": {"enum": ["openai"], "default": "openai"},
        }
        apply_deployment_policy(props)
        # stt/tts were never declared, so classic cannot run and must not have
        # been left as the only offer without warning.
        self.assertEqual(props["pipeline_modality"]["enum"], ["classic"])

    @mock.patch.dict(os.environ, {"RIVERST_COMPUTE_DEVICE": "cpu"}, clear=True)
    def test_pinned_modality_is_never_rewritten(self):
        """A pinned field renders no control, so an unsatisfiable pin could not
        be corrected by the user."""
        props = {
            "pipeline_modality": {
                "enum": ["classic", "e2e"],
                "const": "e2e",
                "default": "e2e",
            },
            "llm_type": {"enum": ["openai"], "default": "openai"},
        }
        apply_deployment_policy(props)
        self.assertEqual(props["pipeline_modality"]["const"], "e2e")
        self.assertEqual(props["pipeline_modality"]["enum"], ["classic", "e2e"])


class ComputeDevicePolicyTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_unset_means_auto(self):
        self.assertEqual(compute_device_policy(), "auto")

    @mock.patch.dict(os.environ, {"RIVERST_COMPUTE_DEVICE": ""}, clear=True)
    def test_empty_is_an_error_not_a_default(self):
        """This value decides what is offered, so a blank setting must fail
        loudly rather than resolve to auto and re-enable local backends."""
        with self.assertRaises(ValueError):
            compute_device_policy()


if __name__ == "__main__":
    unittest.main()
