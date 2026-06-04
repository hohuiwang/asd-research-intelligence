from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class JournalTier:
    name: str
    score: float
    journals: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    rationale: str = ""

    @property
    def search_terms(self) -> tuple[str, ...]:
        return self.journals + self.aliases


JOURNAL_TIERS = (
    JournalTier(
        name="elite_general_or_translational",
        score=1.0,
        journals=(
            "Nature",
            "Science",
            "Cell",
            "The New England Journal of Medicine",
            "The Lancet",
            "JAMA",
            "JAMA Network Open",
            "BMJ",
            "Proceedings of the National Academy of Sciences of the United States of America",
            "Nature Medicine",
            "Nature Neuroscience",
            "Nature Human Behaviour",
            "Science Translational Medicine",
            "Neuron",
            "Cell Reports Medicine",
        ),
        aliases=(
            "N Engl J Med",
            "NEJM",
            "Lancet",
            "Lancet London England",
            "PNAS",
            "Proceedings of the National Academy of Sciences",
            "Proc Natl Acad Sci U S A",
            "Nat Med",
            "Nat Neurosci",
            "Nat Hum Behav",
            "Sci Transl Med",
            "Cell Rep Med",
        ),
        rationale="Very selective general, medical, neuroscience, or translational venue.",
    ),
    JournalTier(
        name="top_clinical_pediatric_psychiatry",
        score=0.92,
        journals=(
            "JAMA Pediatrics",
            "JAMA Psychiatry",
            "The Lancet Child & Adolescent Health",
            "The Lancet Psychiatry",
            "Pediatrics",
            "Journal of the American Academy of Child and Adolescent Psychiatry",
            "Journal of Child Psychology and Psychiatry",
            "American Journal of Psychiatry",
            "Molecular Psychiatry",
            "Biological Psychiatry",
            "The Journal of Clinical Psychiatry",
            "World Psychiatry",
            "Nature Mental Health",
            "Psychological Medicine",
            "Translational Psychiatry",
            "European Child & Adolescent Psychiatry",
            "Development and Psychopathology",
            "Developmental Medicine and Child Neurology",
            "Neuropsychopharmacology",
        ),
        aliases=(
            "JAMA Pediatr",
            "JAMA Psychiatry",
            "Lancet Child Adolesc Health",
            "Lancet Psychiatry",
            "J Am Acad Child Adolesc Psychiatry",
            "J Child Psychol Psychiatry",
            "Am J Psychiatry",
            "Mol Psychiatry",
            "Biol Psychiatry",
            "Journal of Clinical Psychiatry",
            "J Clin Psychiatry",
            "World Psychiatry",
            "Nat Ment Health",
            "Psychol Med",
            "Transl Psychiatry",
            "Eur Child Adolesc Psychiatry",
            "Dev Psychopathol",
            "Developmental Medicine & Child Neurology",
            "Dev Med Child Neurol",
            "Neuropsychopharmacology",
        ),
        rationale="Leading child, adolescent, psychiatry, pediatrics, or mental-health venue.",
    ),
    JournalTier(
        name="asd_specialist_high_signal",
        score=0.80,
        journals=(
            "Molecular Autism",
            "Autism Research",
            "Autism",
            "Journal of Autism and Developmental Disorders",
            "Autism in Adulthood",
            "Research in Autism Spectrum Disorders",
            "Journal of Neurodevelopmental Disorders",
            "Research in Developmental Disabilities",
        ),
        aliases=(
            "Mol Autism",
            "Autism Res",
            "Autism The International Journal of Research and Practice",
            "J Autism Dev Disord",
            "Autism Adulthood",
            "Res Autism Spectr Disord",
            "J Neurodev Disord",
            "Res Dev Disabil",
        ),
        rationale="Autism-specialist venue to retain field-specific work that may not land in general journals.",
    ),
)


def high_impact_journal_query() -> str:
    terms = []
    seen = set()
    for tier in JOURNAL_TIERS:
        for term in tier.search_terms:
            if term not in seen:
                terms.append(term)
                seen.add(term)

    return "(" + " OR ".join(f'"{term}"[Journal]' for term in terms) + ")"


def journal_tier_for(journal: str) -> JournalTier | None:
    normalized = _normalize(journal)
    if not normalized:
        return None

    for tier in JOURNAL_TIERS:
        for term in tier.search_terms:
            normalized_term = _normalize(term)
            if normalized == normalized_term:
                return tier

    for tier in JOURNAL_TIERS:
        for term in tier.search_terms:
            normalized_term = _normalize(term)
            if normalized_term and len(normalized_term.split()) > 1 and normalized_term in normalized:
                return tier

    return None


def _normalize(value: str) -> str:
    value = value.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
