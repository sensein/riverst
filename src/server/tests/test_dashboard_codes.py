import re
import unittest

from dashboard import codes


class DashboardCodesTest(unittest.TestCase):
    def test_generate_code_length_and_alphabet(self):
        for _ in range(200):
            code = codes.generate_code()
            self.assertEqual(len(code), 6)
            self.assertTrue(all(ch in codes.ALPHABET for ch in code))

    def test_alphabet_excludes_lookalikes(self):
        for ch in "0O1IL":
            self.assertNotIn(ch, codes.ALPHABET)

    def test_normalize_code(self):
        self.assertEqual(codes.normalize_code("k7mpq4"), "K7MPQ4")
        self.assertEqual(codes.normalize_code("  K7M PQ4 "), "K7MPQ4")
        self.assertIsNone(codes.normalize_code("K7MPQ"))
        self.assertIsNone(codes.normalize_code("K7MPQ40"))
        self.assertIsNone(codes.normalize_code("K7MPQ0"))
        self.assertIsNone(codes.normalize_code(""))
        self.assertIsNone(codes.normalize_code(None))

    def test_user_key_format_and_uniqueness(self):
        keys = {codes.generate_user_key() for _ in range(1000)}
        self.assertEqual(len(keys), 1000)
        for key in keys:
            self.assertRegex(key, r"^stu_[0-9a-f]{16}$")

    def test_new_id_prefix(self):
        self.assertTrue(re.match(r"^s_[A-Za-z0-9_-]{12}$", codes.new_id("s")))


if __name__ == "__main__":
    unittest.main()
