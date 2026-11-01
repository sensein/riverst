import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SECRET_KEY", "test-secret")

from authorization import auth  # noqa: E402


class RolesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.users_file = Path(self.tmp.name) / "authorized_users.json"
        self.users_file.write_text(
            json.dumps(
                {
                    "authorized_emails": ["res@example.org", "both@example.org"],
                    "teacher_emails": ["teach@example.org", "both@example.org"],
                }
            )
        )
        self.patch = mock.patch.object(auth, "USERS_FILE", self.users_file)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_roles_per_list(self):
        self.assertEqual(auth.get_roles("res@example.org"), ["researcher"])
        self.assertEqual(auth.get_roles("teach@example.org"), ["teacher"])
        self.assertEqual(auth.get_roles("both@example.org"), ["researcher", "teacher"])
        self.assertEqual(auth.get_roles("nobody@example.org"), [])

    def test_teachers_may_sign_in(self):
        allowed = auth.load_authorized_users()
        self.assertIn("teach@example.org", allowed)
        self.assertIn("res@example.org", allowed)
        self.assertNotIn("nobody@example.org", allowed)

    def test_role_dependencies(self):
        self.assertEqual(
            auth.require_teacher({"sub": "t", "roles": ["teacher"]})["sub"], "t"
        )
        with self.assertRaises(auth.HTTPException) as ctx:
            auth.require_researcher({"sub": "t", "roles": ["teacher"]})
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(auth.HTTPException):
            auth.require_teacher({"sub": "legacy"})

    def test_bypass_token_has_both_roles(self):
        _, user = auth.create_bypass_token()
        self.assertEqual(user["roles"], ["researcher", "teacher"])


if __name__ == "__main__":
    unittest.main()
