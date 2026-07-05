# Autism Research Agent

This workspace contains a step-by-step Python MVP for the autism research intelligence agent described in `autism-research-agent-blueprint.md`.

The first version uses only Python's standard library:

- PubMed discovery through NCBI E-utilities, defaulting to a curated high-impact journal filter
- SQLite storage
- Rule-based age/design/impact scoring tuned for under-25 ASD research, with adult ASD companion tracking
- Markdown weekly digest generation
- GitHub Pages-ready static dashboard export for sharing screened papers with colleagues

The agent keeps its database, reports, tests, and configuration inside this folder. Live discovery still calls PubMed for current article metadata; local writes outside this workspace are refused.

Later steps can add OpenAlex, Semantic Scholar, Altmetric, Supabase, Render cron jobs, Streamlit, and OpenAI structured summaries.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m research_agent.cli init-db
python -m research_agent.cli demo
python -m research_agent.cli run-weekly --days 14
```

The report will be written to:

```text
reports/latest-weekly-digest.md
```

The shareable website will be written to:

```text
site/index.html
```

The export now includes a full ASD dashboard bundle:

```text
site/styles.css
site/app.js
site/assets/research-banner.svg
```

Study-type subpages are written to:

```text
site/topics/therapy/index.html
site/topics/non-therapy/index.html
site/topics/medication/index.html
```

If live PubMed access fails with a certificate error on macOS, run:

```bash
"/Applications/Python 3.14/Install Certificates.command"
```

Then retry the `run-weekly` command.

Useful options:

```bash
python -m research_agent.cli run-weekly --days 14 --journal-scope high-impact --population-scope priority
python -m research_agent.cli run-weekly --days 14 --journal-scope broad --population-scope all
python -m research_agent.cli rescore
python -m research_agent.cli export-site
python -m research_agent.cli serve-site --port 8000
python3 -m unittest discover -s tests
```

To share the website, send `site/index.html` directly or publish the `site/` folder with any static host.

The public GitHub Pages links will also support study-type pages such as:

```text
https://YOUR-USERNAME.github.io/YOUR-REPO/topics/therapy/
https://YOUR-USERNAME.github.io/YOUR-REPO/topics/non-therapy/
https://YOUR-USERNAME.github.io/YOUR-REPO/topics/medication/
```

## Scoring

The score weights are in `research_agent/config.py` as `SCORE_WEIGHTS`.

Current formula:

```text
overall_score =
  0.278 * venue_score +
  0.222 * article_impact_score +
  0.389 * methods_quality_score +
  0.111 * novelty_score
```

Age relevance is still tagged and displayed for filtering, but it is no longer part of the numeric overall score.

Accepted papers default to `overall_score >= 0.70`; watchlist papers default to `overall_score >= 0.50`.

After changing score weights, run:

```bash
python3 -m research_agent.cli rescore
```

## GitHub Pages

This repo includes a GitHub Actions workflow that publishes the generated `site/` folder to GitHub Pages.
The workflow can now regenerate the latest PubMed-backed site export on push and on a weekly schedule, as long as the repository secret `PUBMED_CONTACT_EMAIL` is configured.

See:

```text
docs/github-pages.md
```
