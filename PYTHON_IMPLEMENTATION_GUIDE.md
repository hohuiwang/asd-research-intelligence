# Python Implementation Guide

This guide turns `autism-research-agent-blueprint.md` into a Python project you can build one piece at a time.

## Step 0: Understand The Pipeline

Think of the agent as five simple jobs:

1. Discover papers from PubMed.
2. Store them so you do not process duplicates every week.
3. Score them for autism relevance, age relevance, study design, and rough impact.
4. Summarize or extract the scientific signal.
5. Generate a weekly digest.

The first MVP in this folder implements steps 1-5 with simple rules and no paid APIs.

## Step 1: Create A Virtual Environment

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
```

Use `python`, not `python3`, after activation. That confirms you are using the environment.

## Step 2: Initialize The Database

```bash
python -m research_agent.cli init-db
```

This creates:

```text
data/autism_research.sqlite3
```

SQLite is a small local database built into Python. You can migrate to Supabase/Postgres later without changing the conceptual design.

## Step 3: Run The Offline Demo

Before calling any external APIs, run:

```bash
python -m research_agent.cli demo
```

This uses sample autism-paper records to test the scoring, storage, and report-writing pipeline.

## Step 4: Run The Weekly Discovery Job

```bash
python -m research_agent.cli run-weekly --days 14 --journal-scope high-impact --population-scope priority
```

This searches PubMed for autism-related articles from the past 14 days in the curated high-impact journal set, prioritizes under-25 and adult-companion population terms, stores them locally, scores them, and writes a report.

The report appears here:

```text
reports/latest-weekly-digest.md
```

If this fails on macOS with a certificate verification error, run:

```bash
"/Applications/Python 3.14/Install Certificates.command"
```

Then retry the command.

For a wider sweep, use:

```bash
python -m research_agent.cli run-weekly --days 14 --journal-scope broad --population-scope all
```

## Step 5: Read The Generated Digest

The first digest is intentionally cautious. It does not yet claim to understand full methods sections. It uses:

- Publication type
- Journal title
- Title and abstract text
- Age words
- Study-design words
- DOI/PMID metadata

This gives you a useful candidate filter before adding more sophisticated metrics.

## Step 6: Add OpenAlex Enrichment

The next improvement is to query OpenAlex by DOI or PMID and save:

- Citation count
- Open-access status
- Venue information
- Concept/topic metadata
- Retraction status when available

You would add this to `research_agent/enrich.py` and store the result in `metrics`.

## Step 7: Add OpenAI Structured Summaries

Once the discovery/scoring pipeline works, add LLM summaries.

Use a schema-based summary so the output is predictable:

- bibliographic metadata
- population
- age tags
- study design
- sample size
- main findings
- key statistics
- limitations
- interpretation
- confidence

The OpenAI Python SDK automatically reads `OPENAI_API_KEY` from your environment. Official OpenAI docs recommend storing your API key as an environment variable and using structured outputs when you need reliable JSON-shaped results.

## Step 8: Add A Dashboard

After the weekly Markdown report works, build a Streamlit dashboard with:

- Accepted papers
- Watchlist papers
- Excluded papers
- Score breakdown
- Feedback buttons
- Threshold controls

Do not build the dashboard first. The pipeline is the valuable part.

## Step 9: Move To The Cloud

For a durable personal tool:

- Keep Python code in GitHub.
- Use Render Cron Jobs or GitHub Actions to run weekly.
- Use Supabase/Postgres instead of local SQLite.
- Send yourself the digest by email.

## Mental Model

Each week, the agent should answer:

1. What new autism papers appeared?
2. Which ones are worth my attention?
3. Why did they pass the filter?
4. What did the study actually find?
5. How much should I trust it?
