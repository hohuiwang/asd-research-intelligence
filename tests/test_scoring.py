from __future__ import annotations

import unittest

from research_agent.models import Paper
from research_agent.scoring import score_paper


class ScoringTest(unittest.TestCase):
    def test_young_adult_range_does_not_become_adult_25_plus(self) -> None:
        paper = Paper(
            pmid="1",
            title="Population-based longitudinal outcomes among autistic youth",
            abstract=(
                "This cohort included 12,450 autistic participants ages 13 to 24 "
                "and studied transition-age healthcare outcomes."
            ),
            journal="Journal of Child Psychology and Psychiatry",
            publication_date="2026-05-01",
            publication_types=("Journal Article",),
        )

        score = score_paper(paper)

        self.assertIn("adolescent_13_17", score.age_tags)
        self.assertIn("young_adult_18_24", score.age_tags)
        self.assertNotIn("adult_25_plus", score.age_tags)
        self.assertNotIn("mixed_lifespan", score.age_tags)

    def test_adult_only_paper_is_companion_interest(self) -> None:
        paper = Paper(
            pmid="2",
            title="Employment outcomes among autistic adults",
            abstract="A national registry cohort studied employment and independent living in adults with autism.",
            journal="Autism in Adulthood",
            publication_date="2026-05-01",
            publication_types=("Journal Article",),
        )

        score = score_paper(paper)

        self.assertIn("adult_25_plus", score.age_tags)
        self.assertEqual(score.age_relevance_score, 0.70)

    def test_low_value_publication_is_excluded_even_in_high_impact_journal(self) -> None:
        paper = Paper(
            pmid="3",
            title="Commentary on autism awareness",
            abstract="An opinion piece without original data or systematic review methods.",
            journal="JAMA Pediatrics",
            publication_date="2026-05-01",
            publication_types=("Comment",),
        )

        score = score_paper(paper)

        self.assertEqual(score.bucket, "excluded")
        self.assertFalse(score.included)

    def test_title_level_commentary_signal_is_excluded(self) -> None:
        paper = Paper(
            pmid="4",
            title="Population-based cohort study of autism risk: A commentary",
            abstract="This commentary discusses a large population-based cohort of children.",
            journal="Journal of Child Psychology and Psychiatry",
            publication_date="2026-05-01",
            publication_types=("Journal Article",),
        )

        score = score_paper(paper)

        self.assertEqual(score.bucket, "excluded")
        self.assertFalse(score.included)

    def test_synthesis_without_meta_analysis_scores_as_systematic_review(self) -> None:
        paper = Paper(
            pmid="5",
            title="Auditory Sensitivity in Autism: A Systematic Review",
            abstract="The review used Synthesis Without Meta-analysis to compare children and adolescents.",
            journal="Autism Research",
            publication_date="2026-05-01",
            publication_types=("Journal Article",),
        )

        score = score_paper(paper)

        self.assertEqual(score.article_impact_score, 0.80)


if __name__ == "__main__":
    unittest.main()
