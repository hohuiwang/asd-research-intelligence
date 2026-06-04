from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import REPORTS_DIR, ensure_workspace_path
from .journals import journal_tier_for


def write_weekly_digest(rows: list, path: Path | None = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ensure_workspace_path(path or REPORTS_DIR / "latest-weekly-digest.md")
    if not isinstance(output_path, Path):
        output_path = Path(output_path)

    accepted = [row for row in rows if row["bucket"] == "accepted"]
    watchlist = [row for row in rows if row["bucket"] == "watchlist"]

    lines = [
        f"# Autism Research Weekly Digest - {date.today().isoformat()}",
        "",
        "This workspace-bound MVP uses PubMed metadata plus rule-based scoring. Treat it as triage, not final scientific appraisal.",
        "",
        "Focus: high-impact venues, ASD, primary interest in under-25 populations, with adult ASD papers retained when the signal is strong.",
        "",
        f"- Accepted papers: {len(accepted)}",
        f"- Watchlist papers: {len(watchlist)}",
        "",
        "## Accepted",
        "",
    ]

    if not accepted:
        lines.extend(["No papers crossed the default inclusion threshold.", ""])
    else:
        for row in accepted:
            lines.extend(_paper_section(row))

    lines.extend(["## Watchlist", ""])
    if not watchlist:
        lines.extend(["No watchlist papers for this run.", ""])
    else:
        for row in watchlist[:20]:
            lines.extend(_paper_section(row))

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _paper_section(row) -> list[str]:
    authors = json.loads(row["authors_json"] or "[]")
    age_tags = json.loads(row["age_tags_json"] or "[]")
    reasons = json.loads(row["reasons_json"] or "[]")
    doi = row["doi"] or "not found"
    first_author = authors[0] if authors else "Unknown author"
    abstract = (row["abstract"] or "").strip()
    short_abstract = abstract[:900] + ("..." if len(abstract) > 900 else "")
    journal_tier = journal_tier_for(row["journal"])
    journal_tier_name = journal_tier.name if journal_tier else "not in curated high-impact list"

    return [
        f"### {row['title']}",
        "",
        f"- Citation: {first_author}. {row['journal']}. {row['publication_date']}.",
        f"- PMID: [{row['pmid']}]({row['url']})",
        f"- DOI: {doi}",
        f"- Journal tier: {journal_tier_name}",
        f"- Score: {row['overall_score']:.3f}",
        f"- Age tags: {', '.join(age_tags)}",
        f"- Score breakdown: venue {row['venue_score']:.2f}, article impact {row['article_impact_score']:.2f}, methods {row['methods_quality_score']:.2f}, age {row['age_relevance_score']:.2f}, novelty {row['novelty_score']:.2f}",
        "- Why it passed/watched:",
        *[f"  - {reason}" for reason in reasons[:6]],
        "",
        "**Abstract excerpt**",
        "",
        short_abstract or "No abstract available from PubMed.",
        "",
    ]
