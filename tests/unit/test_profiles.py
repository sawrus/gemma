from __future__ import annotations

import unittest

from gemma_local_agent.profiles import memory_guard, select_profile


class ProfileTests(unittest.TestCase):
    def test_default_profile_is_26b_2bit(self) -> None:
        profile = select_profile()
        self.assertEqual(profile.name, "26b-a4b-tq-2bit")
        self.assertIn("26B", profile.description)

    def test_4bit_profile_requires_more_than_16gb_without_force(self) -> None:
        profile = select_profile("26b-a4b-tq-4bit")
        result = memory_guard(profile, memory_gb=16.0, force=False)
        self.assertFalse(result.allowed)

    def test_force_allows_risky_profile_with_warning(self) -> None:
        profile = select_profile("26b-a4b-tq-4bit")
        result = memory_guard(profile, memory_gb=16.0, force=True)
        self.assertTrue(result.allowed)
        self.assertIn("warning", result.messages[0])


if __name__ == "__main__":
    unittest.main()

