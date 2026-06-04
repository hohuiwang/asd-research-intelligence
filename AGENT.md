# ASD Research Update Agent

## Operating Policy

- Keep code, data, reports, and tests inside this workspace.
- Use PubMed only for live article metadata discovery.
- Store screened records in `data/autism_research.sqlite3`.
- Write the digest to `reports/latest-weekly-digest.md`.
- Write the shareable website to `site/index.html`.
- Treat journal impact as a triage signal, never proof that a study is good.

## Default Screening Focus

Primary population:

- infants, toddlers, children, adolescents, youth, and young adults through age 24

Companion population:

- adult ASD papers when they are clinically, epidemiologically, services, employment, independent-living, mortality, aging, or policy relevant

Default journal scope:

- elite general or translational journals
- top clinical, pediatric, psychiatry, neuroscience, and mental-health journals
- autism-specialist journals that are highly relevant to the field

## Score Formula

Weights live in `research_agent/config.py` as `SCORE_WEIGHTS`.

Current formula:

```text
overall_score =
  0.278 * venue_score +
  0.222 * article_impact_score +
  0.389 * methods_quality_score +
  0.111 * novelty_score
```

Age relevance is still tagged and shown for filtering, but it is no longer part of the numeric overall score.

Bucket thresholds:

```text
accepted: overall_score >= 0.70
watchlist: overall_score >= 0.50
excluded: below watchlist threshold, or low-value publication type/title signal
```

After changing weights or thresholds, run:

```bash
python3 -m research_agent.cli rescore
python3 -m unittest discover -s tests
```

## Commands

```bash
python3 -m research_agent.cli init-db
python3 -m research_agent.cli demo
python3 -m research_agent.cli run-weekly --days 14 --journal-scope high-impact --population-scope priority
python3 -m research_agent.cli rescore
python3 -m research_agent.cli export-site
python3 -m research_agent.cli serve-site --port 8000
python3 -m unittest discover -s tests
```

Use `--journal-scope broad --population-scope all` when you want a wider sweep and are willing to review more watchlist items.

Share `site/index.html` directly, or publish the whole `site/` folder on a static web host.
