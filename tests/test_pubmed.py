from __future__ import annotations

import unittest

from research_agent.journals import high_impact_journal_query, journal_tier_for
from research_agent.pubmed import build_search_query


class PubMedQueryTest(unittest.TestCase):
    def test_default_query_filters_to_high_impact_priority_population(self) -> None:
        query = build_search_query(days=14)

        self.assertIn('"Autism Spectrum Disorder"[MeSH Terms]', query)
        self.assertIn('"JAMA Pediatrics"[Journal]', query)
        self.assertIn('"JAMA Psychiatry"[Journal]', query)
        self.assertIn('"The Journal of Clinical Psychiatry"[Journal]', query)
        self.assertIn('"Journal of the American Academy of Child and Adolescent Psychiatry"[Journal]', query)
        self.assertIn('"Proceedings of the National Academy of Sciences of the United States of America"[Journal]', query)
        self.assertIn('"young adult"[Title/Abstract]', query)
        self.assertIn('"Adult"[MeSH Terms]', query)
        self.assertIn('NOT "Editorial"[Publication Type]', query)

    def test_user_requested_journals_are_in_default_query(self) -> None:
        query = build_search_query(days=14)
        requested_journals = (
            "Nature",
            "Science",
            "Cell",
            "The Lancet",
            "The New England Journal of Medicine",
            "JAMA",
            "BMJ",
            "Proceedings of the National Academy of Sciences of the United States of America",
            "JAMA Psychiatry",
            "The Lancet Psychiatry",
            "American Journal of Psychiatry",
            "Molecular Psychiatry",
            "Biological Psychiatry",
            "The Journal of Clinical Psychiatry",
            "Journal of the American Academy of Child and Adolescent Psychiatry",
            "Translational Psychiatry",
            "Nature Neuroscience",
            "Autism Research",
            "Molecular Autism",
            "Autism",
            "Journal of Autism and Developmental Disorders",
            "Development and Psychopathology",
            "Neuropsychopharmacology",
            "Journal of Child Psychology and Psychiatry",
            "Developmental Medicine and Child Neurology",
            "Research in Autism Spectrum Disorders",
            "Journal of Neurodevelopmental Disorders",
        )

        for journal in requested_journals:
            with self.subTest(journal=journal):
                self.assertIn(f'"{journal}"[Journal]', query)

    def test_broad_all_query_removes_journal_and_population_filters(self) -> None:
        query = build_search_query(journal_scope="broad", population_scope="all")

        self.assertNotIn("[Journal]", query)
        self.assertNotIn('"young adult"[Title/Abstract]', query)
        self.assertIn("autism[Title/Abstract]", query)

    def test_journal_tiers_match_full_titles_and_abbreviations(self) -> None:
        self.assertEqual(journal_tier_for("JAMA Pediatr").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(journal_tier_for("JAMA Psychiatry").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(journal_tier_for("J Clin Psychiatry").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(journal_tier_for("Journal of Clinical Psychiatry").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(
            journal_tier_for("Journal of the American Academy of Child and Adolescent Psychiatry").name,
            "top_clinical_pediatric_psychiatry",
        )
        self.assertEqual(journal_tier_for("PNAS").name, "elite_general_or_translational")
        self.assertEqual(journal_tier_for("Nature Human Behaviour").name, "elite_general_or_translational")
        self.assertEqual(journal_tier_for("J Autism Dev Disord").name, "asd_specialist_high_signal")
        self.assertEqual(journal_tier_for("Journal of Neurodevelopmental Disorders").name, "asd_specialist_high_signal")
        self.assertEqual(journal_tier_for("Development and Psychopathology").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(journal_tier_for("Neuropsychopharmacology").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(journal_tier_for("Dev Med Child Neurol").name, "top_clinical_pediatric_psychiatry")
        self.assertEqual(journal_tier_for("Lancet (London, England)").name, "elite_general_or_translational")
        self.assertEqual(
            journal_tier_for("Autism : the international journal of research and practice").name,
            "asd_specialist_high_signal",
        )

    def test_journal_query_is_pubmed_fielded(self) -> None:
        query = high_impact_journal_query()

        self.assertTrue(query.startswith("("))
        self.assertIn('"Molecular Autism"[Journal]', query)


if __name__ == "__main__":
    unittest.main()
