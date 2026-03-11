import os
import sys
import unittest
import types
import importlib
from unittest import mock


def make_fake_torch(cuda_available=False, mps_available=False):
    torch_module = types.ModuleType("torch")
    torch_module.device = lambda name: name
    torch_module.cuda = types.SimpleNamespace(is_available=lambda: cuda_available)
    torch_module.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: mps_available)
    )
    return torch_module


class DeviceUtilsTest(unittest.TestCase):
    def setUp(self):
        self.modules_backup = {
            "torch": sys.modules.get("torch"),
            "bot.utils.device_utils": sys.modules.get("bot.utils.device_utils"),
            "bot.utils": sys.modules.get("bot.utils"),
            "bot": sys.modules.get("bot"),
        }
        sys.modules["torch"] = make_fake_torch()
        if "bot.utils.device_utils" in sys.modules:
            self.device_utils = importlib.reload(sys.modules["bot.utils.device_utils"])
        else:
            self.device_utils = importlib.import_module("bot.utils.device_utils")

    def tearDown(self):
        for module_name, module in self.modules_backup.items():
            if module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = module

    def test_default_policy_is_auto(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(self.device_utils.COMPUTE_DEVICE_ENV_VAR, None)
            self.assertEqual(self.device_utils.get_compute_device_policy(), "auto")

    def test_cpu_policy_forces_cpu(self):
        with mock.patch.dict(
            os.environ,
            {self.device_utils.COMPUTE_DEVICE_ENV_VAR: "cpu"},
            clear=False,
        ):
            device = self.device_utils.get_best_device(options=["cuda", "mps", "cpu"])
            self.assertEqual(str(device), "cpu")

    def test_invalid_policy_raises(self):
        with mock.patch.dict(
            os.environ,
            {self.device_utils.COMPUTE_DEVICE_ENV_VAR: "invalid"},
            clear=False,
        ):
            with self.assertRaises(ValueError):
                self.device_utils.get_compute_device_policy()

    def test_cpu_policy_requires_cpu_option(self):
        with mock.patch.dict(
            os.environ,
            {self.device_utils.COMPUTE_DEVICE_ENV_VAR: "cpu"},
            clear=False,
        ):
            with self.assertRaises(ValueError):
                self.device_utils.get_best_device(options=["cuda"])


if __name__ == "__main__":
    unittest.main()
