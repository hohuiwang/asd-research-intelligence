from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Paper:
    pmid: str
    title: str
    abstract: str
    journal: str
    publication_date: str
    doi: str | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    publication_types: tuple[str, ...] = field(default_factory=tuple)

    @property
    def pubmed_url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"


@dataclass(frozen=True)
class Score:
    venue_score: float
    article_impact_score: float
    methods_quality_score: float
    age_relevance_score: float
    novelty_score: float
    overall_score: float
    age_tags: tuple[str, ...]
    reasons: tuple[str, ...]
    included: bool
    bucket: str

