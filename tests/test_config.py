from __future__ import annotations

import unittest

from research_agent.config import SCORE_WEIGHTS


class ConfigTest(unittest.TestCase):
    def test_score_weights_sum_to_one(self) -> None:
        self.assertEqual(
            set(SCORE_WEIGHTS),
            {"venue", "article_impact", "methods_quality", "novelty"},
        )
        self.assertAlmostEqual(sum(SCORE_WEIGHTS.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
