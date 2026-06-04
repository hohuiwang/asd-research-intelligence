# Autism Research Intelligence Agent Blueprint

## Goal

Track new autism spectrum disorder research on a weekly cadence, with a monthly synthesis layer. Prioritize high-impact, methodologically credible papers, especially studies involving people under 25, while still capturing important adult ASD research.

The agent should not treat journal impact as proof of study quality. It should use journal-level metrics, article-level signals, and study-quality checks together.

## Core Sources

1. PubMed / MEDLINE via NCBI E-utilities
   - Best default source for biomedical, clinical, psychiatric, genetics, neuroscience, epidemiology, and review literature.
   - Use PMID as a stable primary identifier when available.

2. Europe PMC / PubMed Central
   - Useful for abstracts, open-access full text, citations, grants, and linked full-text content.
   - Prefer full text when available, but summarize only from accessible source material.

3. OpenAlex
   - Use for DOI/PMID normalization, citation counts, field-weighted citation impact when available, concepts/topics, venue metadata, open-access links, and retraction flags.

4. Crossref
   - Use for DOI metadata, publication dates, journal ISSN, funder metadata, relations, updates, corrections, and retractions/crossmark metadata when available.

5. Semantic Scholar
   - Use as a secondary citation graph and for influential citation count, related papers, and broad coverage outside strict biomedical indexing.

6. Altmetric / Dimensions / Scopus / Web of Science, if licensed
   - Altmetric helps detect fast attention, but should never be used as a quality score.
   - Clarivate Journal Citation Reports gives official Journal Impact Factor but requires a paid license.
   - Scopus CiteScore is useful as a broader journal metric and is visible for many sources.

7. ClinicalTrials.gov
   - Optional companion feed for major ASD trials, completed studies, status changes, posted results, and trial-to-publication matching.

## Search Scope

Base autism query:

```text
("autism spectrum disorder"[Title/Abstract] OR autism[Title/Abstract] OR autistic[Title/Abstract] OR ASD[Title/Abstract] OR "pervasive developmental disorder"[Title/Abstract])
```

MeSH expansion for PubMed:

```text
("Autism Spectrum Disorder"[MeSH] OR "autism spectrum disorder"[tiab] OR autism[tiab] OR autistic[tiab])
```

Primary age focus:

```text
(infant OR child OR children OR adolescent OR adolescents OR youth OR young adult OR pediatric OR paediatric OR teen OR toddler OR preschool OR "under 25" OR "0-25")
```

Adult companion scope:

```text
(adult OR adults OR aging OR ageing OR lifespan OR "transition age" OR employment OR independent living)
```

Include:

- Original research: cohort, case-control, longitudinal, randomized trial, quasi-experimental, meta-analysis, systematic review, population registry, large-scale genetics, neuroimaging, digital phenotyping, intervention, services, health outcomes.
- High-quality reviews and meta-analyses.
- Major consensus/guideline papers when published in strong journals or from authoritative groups.

Exclude by default:

- Editorials, letters, narrative commentaries, single case reports, conference abstracts, non-systematic opinion pieces, small uncontrolled studies unless they introduce a genuinely important dataset or method.
- Animal-only studies unless the user enables a mechanistic/basic-science track.
- Preprints unless separately labeled as "not peer reviewed."

## Impact And Quality Gate

Pass an article into the candidate set if it meets at least one impact gate and one quality gate.

Impact gates:

- Journal is in top quartile for a relevant category, or Journal Impact Factor >= 8, or CiteScore >= 8, or SJR Q1.
- Article is in the top 10-20% of recent autism-related candidates by age-normalized citations or field-weighted citation impact.
- Altmetric Attention Score is unusually high for publication age, but use this only as an attention flag.
- Semantic Scholar influential citation count is high for age, or the paper is rapidly cited by high-quality papers.
- Paper comes from a major registry, consortium, RCT, guideline body, or multi-site dataset even if journal metrics are moderate.

Quality gates:

- Clear research question and appropriate design.
- Human ASD population clearly defined, with age range extractable.
- Adequate sample size for the claim, or strong design for a rare/specialized cohort.
- Validated ASD ascertainment or clearly stated diagnostic criteria.
- Appropriate comparator/control group when needed.
- Confounders handled credibly.
- Effect sizes, uncertainty intervals, and absolute numbers extracted where available.
- Multiple testing, missingness, attrition, and bias risks addressed.
- Funding/conflict statements captured.

Suggested scoring:

```text
overall_score =
  0.25 * venue_score +
  0.20 * article_impact_score +
  0.35 * methods_quality_score +
  0.10 * age_relevance_score +
  0.10 * novelty_or_field_importance_score
```

Minimum default threshold: `overall_score >= 0.70`, with "must include" overrides for major clinical trials, guidelines, large registries, or landmark mechanisms.

## Age Tagging

Each paper should receive one or more tags:

- `infant_0_2`
- `child_3_12`
- `adolescent_13_17`
- `young_adult_18_24`
- `adult_25_plus`
- `mixed_lifespan`
- `age_unclear`

Priority order:

1. Under-25 original data.
2. Mixed lifespan studies with extractable under-25 subgroup.
3. Adult ASD papers with strong clinical, epidemiologic, intervention, employment, healthcare, mortality, or aging relevance.

## Weekly Output

The weekly digest should be short and selective: usually 5-10 papers.

For each paper:

- Citation and link: title, journal, date, DOI, PMID.
- Why it passed the filter.
- Population: age range, sample size, ASD definition, comparator.
- Study design and data source.
- Main result: include effect sizes, confidence intervals, p values, model type, or key descriptive numbers where available.
- Interpretation: what the finding probably means.
- Caution: what could be wrong, biased, underpowered, or overinterpreted.
- Practical relevance: clinical, research, policy, education, family, or adult-life relevance.
- Confidence rating: high, moderate, low.

## Monthly Output

The monthly report should synthesize, not list.

Sections:

- Top 3-5 papers this month.
- Emerging themes.
- Contradictions or unsettled findings.
- Methods watch: strong datasets, better measurement, weak designs to discount.
- Under-25 research update.
- Adult ASD research update.
- What I would change my beliefs about.
- What still needs replication.

## LLM Extraction Prompt Skeleton

```text
You are summarizing an autism research paper for a scientifically literate reader.

Use only the provided abstract/full-text excerpts and metadata.
Do not infer statistics that are not reported.
Separate results from interpretation.
If data are missing, say "not reported in available text."

Return JSON with:
- bibliographic_metadata
- population
- age_tags
- study_design
- data_source
- exposure_or_intervention
- outcomes
- key_statistics
- main_findings
- interpretation
- limitations
- conflicts_and_funding
- relevance_to_under_25
- relevance_to_adults
- confidence
- reason_for_inclusion
- reason_for_exclusion_if_any
```

## MVP Build Plan

1. Discovery job
   - Run weekly PubMed search for the last 7-10 days.
   - Normalize DOI, PMID, title, journal, date, authors.
   - Deduplicate against stored records.

2. Enrichment job
   - Query OpenAlex, Crossref, Semantic Scholar, and optionally Altmetric/Scopus/JCR.
   - Add citations, journal metrics, article metrics, open-access links, and retraction/update flags.

3. Filtering job
   - Apply inclusion/exclusion rules.
   - Score impact and method quality.
   - Route borderline papers to "watchlist" rather than the digest.

4. Summarization job
   - Summarize abstract first.
   - If full text is available, extract methods/results tables and update the summary.
   - Require citations and exact numbers from source text.

5. Report job
   - Produce weekly digest.
   - Update monthly synthesis memory with accepted papers only.

6. Review loop
   - User marks papers as useful/not useful.
   - Adjust thresholds and topic weighting.

## Suggested Default Cadence

- Weekly digest: Monday morning, covering the prior Monday-Sunday.
- Monthly synthesis: first Monday of each month, covering accepted weekly papers plus any late-indexed major papers.

## Data Storage

Minimum schema:

```text
papers(id, doi, pmid, title, journal, publication_date, first_seen_date, abstract, url)
metrics(paper_id, source, metric_name, metric_value, observed_at)
screening(paper_id, included, exclusion_reason, overall_score, quality_score, impact_score, age_tags)
summaries(paper_id, summary_json, model, created_at)
reports(id, report_type, period_start, period_end, markdown, created_at)
feedback(paper_id, user_rating, notes, created_at)
```

