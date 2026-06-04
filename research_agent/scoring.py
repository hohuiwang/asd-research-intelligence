from __future__ import annotations

import re

from .config import DEFAULT_THRESHOLD, SCORE_WEIGHTS, WATCHLIST_THRESHOLD
from .journals import journal_tier_for
from .models import Paper, Score


LOW_VALUE_PUBLICATION_TYPES = {
    "comment",
    "editorial",
    "letter",
    "case reports",
    "news",
}

LOW_VALUE_TITLE_SIGNALS = {
    "commentary",
    "editorial",
    "letter to",
    "case report",
}

DESIGN_TERMS = {
    "randomized": 1.0,
    "randomised": 1.0,
    "clinical trial": 1.0,
    "systematic review": 0.95,
    "meta-analysis": 0.95,
    "cohort": 0.85,
    "longitudinal": 0.85,
    "registry": 0.85,
    "population-based": 0.85,
    "case-control": 0.75,
    "multicenter": 0.75,
    "multi-center": 0.75,
    "cross-sectional": 0.55,
}

UNDER_25_TERMS = {
    "infants",
    "infant",
    "toddlers",
    "toddler",
    "preschool",
    "child",
    "children",
    "adolescent",
    "adolescents",
    "youth",
    "young adult",
    "student",
    "pediatric",
    "paediatric",
    "teen",
}

def score_paper(paper: Paper) -> Score:
    evidence_text = f"{paper.title}\n{paper.abstract}\n{' '.join(paper.publication_types)}".lower()
    low_value_types = sorted(
        {
            bad_type
            for bad_type in LOW_VALUE_PUBLICATION_TYPES
            for publication_type in paper.publication_types
            if bad_type in publication_type.lower()
        }
    )
    low_value_text_signals = sorted(
        signal for signal in LOW_VALUE_TITLE_SIGNALS if signal in paper.title.lower()
    )

    venue_score, venue_reasons = _venue_score(paper.journal)
    article_score, article_reasons = _article_impact_score(paper, evidence_text)
    methods_score, methods_reasons = _methods_quality_score(evidence_text)
    age_score, age_tags, age_reasons = _age_relevance_score(evidence_text)
    novelty_score, novelty_reasons = _novelty_score(evidence_text)

    exclusion_reasons = []
    if low_value_types or low_value_text_signals:
        article_score = min(article_score, 0.05)
        methods_score = min(methods_score, 0.05)
        novelty_score = min(novelty_score, 0.05)
        low_value_reasons = low_value_types + low_value_text_signals
        exclusion_reasons.append(f"excluded low-value publication signal by default: {', '.join(low_value_reasons)}")

    overall = _weighted_overall_score(
        venue_score=venue_score,
        article_score=article_score,
        methods_score=methods_score,
        novelty_score=novelty_score,
    )

    included = overall >= DEFAULT_THRESHOLD and not low_value_types and not low_value_text_signals
    if low_value_types or low_value_text_signals:
        bucket = "excluded"
    elif included:
        bucket = "accepted"
    elif overall >= WATCHLIST_THRESHOLD:
        bucket = "watchlist"
    else:
        bucket = "excluded"

    reasons = tuple(
        exclusion_reasons + venue_reasons + article_reasons + methods_reasons + age_reasons + novelty_reasons
    )
    return Score(
        venue_score=round(venue_score, 3),
        article_impact_score=round(article_score, 3),
        methods_quality_score=round(methods_score, 3),
        age_relevance_score=round(age_score, 3),
        novelty_score=round(novelty_score, 3),
        overall_score=round(overall, 3),
        age_tags=tuple(age_tags),
        reasons=reasons,
        included=included,
        bucket=bucket,
    )


def _weighted_overall_score(
    *,
    venue_score: float,
    article_score: float,
    methods_score: float,
    novelty_score: float,
) -> float:
    return (
        SCORE_WEIGHTS["venue"] * venue_score
        + SCORE_WEIGHTS["article_impact"] * article_score
        + SCORE_WEIGHTS["methods_quality"] * methods_score
        + SCORE_WEIGHTS["novelty"] * novelty_score
    )


def _venue_score(journal: str) -> tuple[float, list[str]]:
    tier = journal_tier_for(journal)
    if tier:
        return tier.score, [f"journal tier {tier.name}: {journal}"]

    normalized = journal.lower()
    if "autism" in normalized or "psychiatry" in normalized or "development" in normalized:
        return 0.65, [f"journal appears field-relevant: {journal}"]
    return 0.45, ["journal impact unknown in local MVP"]


def _article_impact_score(paper: Paper, text: str) -> tuple[float, list[str]]:
    publication_types = {pt.lower() for pt in paper.publication_types}
    if any("meta-analysis" in pt for pt in publication_types):
        return 0.85, ["publication type is meta-analysis"]
    if any("systematic review" in pt for pt in publication_types):
        return 0.80, ["publication type is systematic review"]
    if "systematic review" in text:
        return 0.80, ["title/abstract indicates systematic review"]
    if re.search(r"(?<!without )\bmeta-analysis\b", text):
        return 0.85, ["title/abstract indicates meta-analysis"]
    if any("clinical trial" in pt for pt in publication_types):
        return 0.85, ["publication type is clinical trial"]
    if "randomized trial" in text or "randomised trial" in text or "randomized controlled trial" in text:
        return 0.85, ["title/abstract indicates randomized trial"]
    if "consortium" in text or "registry" in text or "population-based" in text:
        return 0.75, ["large dataset or consortium signal in title/abstract"]
    return 0.50, ["article-level impact not yet enriched"]


def _methods_quality_score(text: str) -> tuple[float, list[str]]:
    matched = [(term, score) for term, score in DESIGN_TERMS.items() if term in text]
    if not matched:
        return 0.35, ["study design unclear from title/abstract"]

    term, score = max(matched, key=lambda item: item[1])
    reasons = [f"study design signal: {term}"]

    sample_size = _extract_largest_sample_size(text)
    if sample_size >= 1000:
        score = min(1.0, score + 0.10)
        reasons.append(f"large sample size signal: n={sample_size}")
    elif sample_size >= 100:
        score = min(1.0, score + 0.05)
        reasons.append(f"moderate sample size signal: n={sample_size}")

    return score, reasons


def _age_relevance_score(text: str) -> tuple[float, list[str], list[str]]:
    tags = []
    reasons = []
    age_ranges = _extract_age_ranges(text)

    if _contains_any_term(text, ("infant", "infants", "toddler", "toddlers")) or _range_overlaps(age_ranges, 0, 2):
        tags.append("infant_0_2")
    if _contains_any_term(
        text,
        ("child", "children", "preschool", "pediatric", "paediatric"),
    ) or _range_overlaps(age_ranges, 3, 12):
        tags.append("child_3_12")
    if _contains_any_term(text, ("adolescent", "adolescents", "teen", "teens", "youth")) or _range_overlaps(
        age_ranges,
        13,
        17,
    ):
        tags.append("adolescent_13_17")
    if _contains_any_phrase(text, ("young adult", "young adults", "transition age", "transition-age")) or _range_overlaps(
        age_ranges,
        18,
        24,
    ):
        tags.append("young_adult_18_24")
    if _has_adult_25_plus_signal(text, age_ranges):
        tags.append("adult_25_plus")

    has_under_25 = any(_contains_term(text, term) for term in UNDER_25_TERMS) or any(
        tag in tags for tag in ["infant_0_2", "child_3_12", "adolescent_13_17", "young_adult_18_24"]
    )
    has_adult = "adult_25_plus" in tags

    if has_under_25 and has_adult:
        tags.append("mixed_lifespan")
        reasons.append("mentions both under-25 and adult-relevant terms")
        return 0.95, sorted(set(tags)), reasons
    if has_under_25:
        reasons.append("matches primary under-25 interest")
        return 1.0, sorted(set(tags)), reasons
    if has_adult:
        reasons.append("matches adult ASD companion interest")
        return 0.70, sorted(set(tags)), reasons

    return 0.30, ("age_unclear",), ["age group unclear from title/abstract"]


def _novelty_score(text: str) -> tuple[float, list[str]]:
    signals = [
        "first",
        "novel",
        "genome-wide",
        "whole-genome",
        "single-cell",
        "longitudinal",
        "randomized",
        "population-based",
        "machine learning",
        "digital phenotype",
        "biomarker",
    ]
    matched = [signal for signal in signals if signal in text]
    if matched:
        return min(0.85, 0.55 + 0.05 * len(matched)), [f"novelty/importance signals: {', '.join(matched[:4])}"]
    return 0.45, ["no strong novelty signal in local MVP"]


def _extract_largest_sample_size(text: str) -> int:
    matches = re.findall(r"(?:n\s*=\s*|sample of\s+|included\s+)(\d[\d,]{1,9})", text, flags=re.IGNORECASE)
    return max((int(match.replace(",", "")) for match in matches), default=0)


def _extract_age_ranges(text: str) -> list[tuple[int, int]]:
    ranges = []
    for low, high in re.findall(
        r"(?:ages?|aged|participants aged|children aged|adults aged)\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})",
        text,
    ):
        ranges.append((int(low), int(high)))
    return ranges


def _range_overlaps(ranges: list[tuple[int, int]], low: int, high: int) -> bool:
    return any(range_low <= high and range_high >= low for range_low, range_high in ranges)


def _has_adult_25_plus_signal(text: str, age_ranges: list[tuple[int, int]]) -> bool:
    if any(high >= 25 for _, high in age_ranges):
        return True

    only_explicit_young_adult_ranges = bool(age_ranges) and max(high for _, high in age_ranges) <= 24
    if only_explicit_young_adult_ranges:
        return False

    if re.search(r"(?<!young )\badults?\b|\badulthood\b|\bmiddle[- ]aged\b|\bolder adults?\b", text):
        return True

    return _contains_any_phrase(
        text,
        (
            "aging",
            "ageing",
            "employment",
            "independent living",
            "adult services",
            "adult healthcare",
            "adult health care",
        ),
    )


def _contains_any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _contains_term(text: str, term: str) -> bool:
    pattern = r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
    return re.search(pattern, text) is not None


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
    return re.search(pattern, text) is not None
