from __future__ import annotations

import unittest

from research_agent.models import Paper
from research_agent.topics import classify_study_type


class TopicsTest(unittest.TestCase):
    def test_medication_is_non_therapy(self) -> None:
        paper = Paper(
            pmid="med",
            title="Pimavanserin for irritability in autism",
            abstract="A randomized placebo-controlled dose study used 20 mg/day medication.",
            journal="JAMA Psychiatry",
            publication_date="2026-05-01",
        )

        study_type = classify_study_type(paper)

        self.assertEqual(study_type.slug, "medication")
        self.assertEqual(study_type.group, "non_therapy")

    def test_parent_mediated_intervention_is_therapy(self) -> None:
        paper = Paper(
            pmid="therapy",
            title="Parent-mediated intervention for autistic toddlers",
            abstract="A behavioral intervention tested caregiver-mediated therapy outcomes.",
            journal="JAMA Pediatrics",
            publication_date="2026-05-01",
        )

        study_type = classify_study_type(paper)

        self.assertEqual(study_type.slug, "therapy")
        self.assertEqual(study_type.group, "therapy")

    def test_population_cohort_is_epidemiology(self) -> None:
        paper = Paper(
            pmid="epi",
            title="Population-based cohort study of autism risk",
            abstract="A registry cohort estimated prevalence and risk in children.",
            journal="The Lancet",
            publication_date="2026-05-01",
        )

        study_type = classify_study_type(paper)

        self.assertEqual(study_type.slug, "epidemiology-risk")


if __name__ == "__main__":
    unittest.main()
