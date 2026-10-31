"""One real test so a pseudo Node entry is the only zero-count failure."""

from __future__ import annotations

import unittest


class RealTests(unittest.TestCase):
    def test_real(self) -> None:
        self.assertEqual(1 + 1, 2)


if __name__ == "__main__":
    unittest.main()
