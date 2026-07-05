from __future__ import annotations

import json
import socket
import urllib.parse
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .config import REPORTS_DIR, SITE_DIR, ensure_workspace_path
from .journals import JOURNAL_TIERS, journal_tier_for
from .models import Paper
from .pubmed import build_search_query
from .topics import STUDY_TYPE_NAV, classify_study_type


def write_static_site(
    rows: list,
    output_dir: Path | None = None,
    run_context: dict[str, Any] | None = None,
) -> Path:
    site_dir = ensure_workspace_path(output_dir or SITE_DIR)
    if not isinstance(site_dir, Path):
        site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    payload = _payload_from_rows(rows, run_context=run_context)
    _write_shared_assets(site_dir)

    index_path = site_dir / "index.html"
    index_path.write_text(_render_html(payload, active_topic="all", path_prefix=""), encoding="utf-8")

    topics_dir = site_dir / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    for nav_item in STUDY_TYPE_NAV:
        if nav_item.slug == "all":
            continue
        topic_dir = topics_dir / nav_item.slug
        topic_dir.mkdir(parents=True, exist_ok=True)
        topic_path = topic_dir / "index.html"
        topic_path.write_text(
            _render_html(payload, active_topic=nav_item.slug, path_prefix="../../"),
            encoding="utf-8",
        )

    readme_path = site_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# ASD Research Radar",
                "",
                "This folder is a static website generated from the local ASD research agent database.",
                "",
                "Share `index.html` directly, or publish the whole `site/` folder with GitHub Pages, Netlify, Vercel, or any static web host.",
                "",
                "Study-type subpages are generated under `topics/`, including `topics/therapy/`, `topics/non-therapy/`, and `topics/medication/`.",
                "",
                "Regenerate it with:",
                "",
                "```bash",
                "python3 -m research_agent.cli export-site",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return index_path


def find_available_port(start: int = 8000, host: str = "127.0.0.1") -> int:
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No available port found from {start} to {start + 99}.")


def _write_shared_assets(site_dir: Path) -> None:
    (site_dir / "assets").mkdir(parents=True, exist_ok=True)
    (site_dir / "styles.css").write_text(_styles_css(), encoding="utf-8")
    (site_dir / "app.js").write_text(_app_js(), encoding="utf-8")
    (site_dir / "assets" / "research-banner.svg").write_text(_banner_svg(), encoding="utf-8")


def _payload_from_rows(rows: list, run_context: dict[str, Any] | None = None) -> dict[str, Any]:
    papers = [_paper_from_row(row) for row in rows]
    bucket_counts = Counter(paper["bucket"] for paper in papers)
    journal_counts = Counter(paper["journal"] for paper in papers)
    age_tag_counts = Counter(tag for paper in papers for tag in paper["age_tags"])
    run = _normalize_run_context(run_context, len(rows))

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "generated_at_iso": datetime.now().isoformat(timespec="minutes"),
        "source_report": str((REPORTS_DIR / "latest-weekly-digest.md").relative_to(REPORTS_DIR.parent)),
        "run": run,
        "counts": {
            "total": len(papers),
            "accepted": bucket_counts.get("accepted", 0),
            "watchlist": bucket_counts.get("watchlist", 0),
            "excluded": bucket_counts.get("excluded", 0),
            "under_25": sum(1 for paper in papers if paper["is_under_25"]),
            "reviews": sum(1 for paper in papers if paper["is_review"]),
        },
        "bucket_options": [
            {"id": "accepted", "label": "Accepted", "count": bucket_counts.get("accepted", 0)},
            {"id": "watchlist", "label": "Watchlist", "count": bucket_counts.get("watchlist", 0)},
            {"id": "excluded", "label": "Excluded", "count": bucket_counts.get("excluded", 0)},
        ],
        "age_tags": [
            {"id": tag, "label": _age_tag_label(tag), "count": count}
            for tag, count in sorted(age_tag_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "study_types": [
            {
                "slug": nav_item.slug,
                "label": nav_item.label,
                "description": nav_item.description,
                "count": sum(1 for paper in papers if _paper_matches_topic(paper, nav_item.slug)),
            }
            for nav_item in STUDY_TYPE_NAV
        ],
        "journals": [
            {
                "id": _slugify(journal),
                "label": journal,
                "count": count,
                "tier": papers_by_journal[0]["journal_tier_label"] if papers_by_journal else "Other journals",
            }
            for journal, count in sorted(journal_counts.items(), key=lambda item: (-item[1], item[0].lower()))
            for papers_by_journal in [[paper for paper in papers if paper["journal"] == journal]]
        ],
        "journal_watchlist": _journal_watchlist(),
        "papers": papers,
    }


def _paper_from_row(row) -> dict[str, Any]:
    authors = json.loads(row["authors_json"] or "[]")
    publication_types = json.loads(row["publication_types_json"] or "[]")
    age_tags = json.loads(row["age_tags_json"] or "[]")
    reasons = json.loads(row["reasons_json"] or "[]")
    abstract = (row["abstract"] or "").strip()
    paper = Paper(
        pmid=row["pmid"],
        title=row["title"],
        abstract=abstract,
        journal=row["journal"] or "",
        publication_date=row["publication_date"] or "",
        doi=row["doi"] or None,
        authors=tuple(authors),
        publication_types=tuple(publication_types),
    )
    study_type = classify_study_type(paper)
    journal_tier = journal_tier_for(row["journal"] or "")
    evidence_labels = _evidence_labels(publication_types, abstract, row["title"] or "", reasons)
    tags = [{"label": _bucket_label(row["bucket"]), "kind": "type"}]
    tags.append({"label": study_type.label, "kind": "topic"})
    tags.extend({"label": _age_tag_label(tag), "kind": "guideline"} for tag in age_tags[:3])
    tags.extend({"label": label, "kind": "type"} for label in evidence_labels[:3])

    is_under_25 = any(
        tag in age_tags for tag in ("infant_0_2", "child_3_12", "adolescent_13_17", "young_adult_18_24")
    )
    is_review = any("review" in label.lower() or "meta-analysis" in label.lower() for label in evidence_labels)

    return {
        "uid": row["pmid"],
        "pmid": row["pmid"],
        "doi": row["doi"] or "",
        "title": row["title"],
        "journal": row["journal"] or "Unknown journal",
        "journal_tier": journal_tier.name if journal_tier else "unmatched",
        "journal_tier_label": _journal_tier_label(journal_tier.name if journal_tier else "unmatched"),
        "publication_date": row["publication_date"] or "",
        "url": row["url"] or "",
        "authors": authors,
        "authors_display": _authors_display(authors),
        "first_author": authors[0] if authors else "Unknown author",
        "publication_types": publication_types,
        "study_type_slug": study_type.slug,
        "study_type_label": study_type.label,
        "study_type_group": study_type.group,
        "study_type_reason": study_type.reason,
        "bucket": row["bucket"],
        "bucket_label": _bucket_label(row["bucket"]),
        "included": bool(row["included"]),
        "overall_score": round(float(row["overall_score"] or 0), 3),
        "display_score": int(round(float(row["overall_score"] or 0) * 100)),
        "venue_score": round(float(row["venue_score"] or 0), 3),
        "article_impact_score": round(float(row["article_impact_score"] or 0), 3),
        "methods_quality_score": round(float(row["methods_quality_score"] or 0), 3),
        "age_relevance_score": round(float(row["age_relevance_score"] or 0), 3),
        "novelty_score": round(float(row["novelty_score"] or 0), 3),
        "age_tags": age_tags,
        "age_labels": [_age_tag_label(tag) for tag in age_tags],
        "evidence_labels": evidence_labels,
        "tags": tags[:8],
        "reasons": reasons,
        "reasons_summary": "; ".join(reasons[:3]) if reasons else "Autism research relevance",
        "abstract": abstract,
        "abstract_excerpt": abstract[:1000] + ("..." if len(abstract) > 1000 else ""),
        "screened_at": row["screened_at"] or "",
        "level": _priority_level(row["bucket"]),
        "is_under_25": is_under_25,
        "is_review": is_review,
    }


def _normalize_run_context(run_context: dict[str, Any] | None, row_count: int) -> dict[str, Any]:
    context = dict(run_context or {})
    days = int(context.get("days") or 14)
    max_results = int(context.get("max_results") or max(row_count, 50))
    journal_scope = context.get("journal_scope") or "high-impact"
    population_scope = context.get("population_scope") or "priority"

    query = context.get("query")
    if not query and journal_scope in {"high-impact", "broad"} and population_scope in {"priority", "all"}:
        query = build_search_query(
            days=days,
            journal_scope=journal_scope,
            population_scope=population_scope,
        )

    pubmed_url = context.get("pubmed_url")
    if not pubmed_url and query:
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={urllib.parse.quote(query)}"

    command = context.get("command") or (
        "python3 -m research_agent.cli run-weekly "
        f"--days {days} --max-results {max_results} "
        f"--journal-scope {journal_scope} --population-scope {population_scope}"
    )

    return {
        "days": days,
        "max_results": max_results,
        "journal_scope": journal_scope,
        "population_scope": population_scope,
        "query": query or "PubMed strategy unavailable for this export.",
        "pubmed_url": pubmed_url or "https://pubmed.ncbi.nlm.nih.gov/",
        "command": command,
    }


def _journal_watchlist() -> list[dict[str, str]]:
    journals: list[dict[str, str]] = []
    for tier in JOURNAL_TIERS:
        for journal in tier.journals:
            journals.append(
                {
                    "label": journal,
                    "tier": _journal_tier_label(tier.name),
                }
            )
    return journals


def _paper_matches_topic(paper: dict[str, Any], slug: str) -> bool:
    if slug == "all":
        return True
    if slug == "therapy":
        return paper["study_type_group"] == "therapy"
    if slug == "non-therapy":
        return paper["study_type_group"] == "non_therapy"
    return paper["study_type_slug"] == slug


def _priority_level(bucket: str) -> str:
    if bucket == "accepted":
        return "high"
    if bucket == "watchlist":
        return "watch"
    return "standard"


def _bucket_label(bucket: str) -> str:
    return {
        "accepted": "Accepted",
        "watchlist": "Watchlist",
        "excluded": "Excluded",
    }.get(bucket, bucket.title())


def _age_tag_label(tag: str) -> str:
    return {
        "infant_0_2": "Infant 0-2",
        "child_3_12": "Child 3-12",
        "adolescent_13_17": "Adolescent 13-17",
        "young_adult_18_24": "Young adult 18-24",
        "adult_25_plus": "Adult 25+",
        "mixed_lifespan": "Mixed lifespan",
        "age_unclear": "Age unclear",
    }.get(tag, tag.replace("_", " ").title())


def _journal_tier_label(tier_name: str) -> str:
    return {
        "elite_general_or_translational": "Elite general/translational",
        "top_clinical_pediatric_psychiatry": "Top clinical/pediatric psychiatry",
        "asd_specialist_high_signal": "ASD specialist high-signal",
        "unmatched": "Other journals",
    }.get(tier_name, tier_name.replace("_", " ").title())


def _authors_display(authors: list[str]) -> str:
    if not authors:
        return "Authors unavailable"
    if len(authors) <= 3:
        return ", ".join(authors)
    return f"{', '.join(authors[:3])} et al."


def _evidence_labels(
    publication_types: list[str],
    abstract: str,
    title: str,
    reasons: list[str],
) -> list[str]:
    text = f"{title}\n{abstract}\n{' '.join(publication_types)}\n{' '.join(reasons)}".lower()
    labels: list[str] = []

    if "randomized" in text or "randomised" in text:
        labels.append("Randomized trial")
    if "clinical trial" in text:
        labels.append("Clinical trial")
    if "systematic review" in text:
        labels.append("Systematic review")
    if "meta-analysis" in text:
        labels.append("Meta-analysis")
    if "cohort" in text or "population-based" in text or "registry" in text:
        labels.append("Cohort/population")
    if "longitudinal" in text:
        labels.append("Longitudinal")
    if "guideline" in text or "consensus" in text:
        labels.append("Guideline/consensus")

    seen: set[str] = set()
    unique: list[str] = []
    for label in labels:
        if label not in seen:
            unique.append(label)
            seen.add(label)
    return unique


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _render_html(payload: dict[str, Any], active_topic: str, path_prefix: str) -> str:
    title = "ASD Research Radar"
    if active_topic != "all":
        topic = next((item["label"] for item in payload["study_types"] if item["slug"] == active_topic), active_topic)
        title = f"{title} - {topic}"
    data_json = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")
    config_json = json.dumps({"activeTopic": active_topic, "pathPrefix": path_prefix}, ensure_ascii=True)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <link rel="stylesheet" href="{path_prefix}styles.css" />
    <script defer src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <script>
      window.RESEARCH_DATA = {data_json};
      window.RESEARCH_PAGE_CONFIG = {config_json};
    </script>
    <script defer src="{path_prefix}app.js"></script>
  </head>
  <body>
    <header class="app-shell">
      <nav class="topbar" aria-label="Application">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">AR</span>
          <div>
            <p class="eyebrow">ASD Research Radar</p>
            <h1>Autism evidence monitor</h1>
          </div>
        </div>
        <div class="topbar-actions">
          <button class="icon-button" id="copy-query-button" type="button">
            <i data-lucide="clipboard-list" aria-hidden="true"></i>
            <span>Copy query</span>
          </button>
          <button class="primary-button" id="refresh-button" type="button">
            <i data-lucide="refresh-cw" aria-hidden="true"></i>
            <span>Refresh</span>
          </button>
        </div>
      </nav>

      <section class="masthead" aria-label="Research monitor summary">
        <div class="masthead-copy">
          <p class="eyebrow">High-impact journals • trials • reviews • services • lifespan</p>
          <h2>Weekly intelligence for autism spectrum disorder research.</h2>
          <div class="status-row">
            <span id="source-status">Static export ready</span>
            <span id="last-updated">Generated {escape(payload["generated_at"])}</span>
          </div>
        </div>
        <img src="{path_prefix}assets/research-banner.svg" alt="" />
      </section>
    </header>

    <main class="app-shell layout">
      <aside class="filter-panel" aria-label="Research filters">
        <div class="panel-block">
          <div class="panel-heading">
            <h2>Scope</h2>
            <button class="text-button" id="reset-button" type="button">Reset</button>
          </div>

          <label class="field-label" for="date-window">Publication window</label>
          <select id="date-window">
            <option value="7">Past 7 days</option>
            <option value="14">Past 14 days</option>
            <option value="30">Past 30 days</option>
            <option value="90">Past 90 days</option>
            <option value="180">Past 180 days</option>
          </select>

          <label class="field-label" for="max-results">Result limit</label>
          <input id="max-results" type="number" min="10" max="250" step="5" value="50" />
        </div>

        <div class="panel-block">
          <h2>Screening Buckets</h2>
          <div class="check-grid" id="bucket-filters"></div>
        </div>

        <div class="panel-block">
          <h2>Study Types</h2>
          <div class="check-grid" id="topic-filters"></div>
        </div>

        <div class="panel-block">
          <h2>Age Focus</h2>
          <div class="check-grid" id="age-filters"></div>
        </div>

        <div class="panel-block">
          <div class="panel-heading">
            <h2>Journals</h2>
            <button class="text-button" id="select-journals-button" type="button">All</button>
          </div>
          <div class="journal-list" id="journal-filters"></div>
        </div>
      </aside>

      <section class="workbench" aria-live="polite">
        <div class="metrics-bar" aria-label="Current queue metrics">
          <div class="metric">
            <span id="metric-total">0</span>
            <p>Articles</p>
          </div>
          <div class="metric">
            <span id="metric-accepted">0</span>
            <p>Accepted</p>
          </div>
          <div class="metric">
            <span id="metric-watchlist">0</span>
            <p>Watchlist</p>
          </div>
          <div class="metric">
            <span id="metric-under25">0</span>
            <p>Under-25 focus</p>
          </div>
        </div>

        <div class="toolbar">
          <div class="tabs" role="tablist" aria-label="Research views">
            <button class="tab is-active" id="queue-tab" type="button" role="tab" aria-selected="true" data-view="queue">Queue</button>
            <button class="tab" id="digest-tab" type="button" role="tab" aria-selected="false" data-view="digest">Digest</button>
            <button class="tab" id="sources-tab" type="button" role="tab" aria-selected="false" data-view="sources">Sources</button>
          </div>
          <div class="toolbar-actions">
            <button class="icon-button" id="export-button" type="button">
              <i data-lucide="download" aria-hidden="true"></i>
              <span>CSV</span>
            </button>
            <button class="icon-button" id="copy-digest-button" type="button">
              <i data-lucide="copy" aria-hidden="true"></i>
              <span>Copy digest</span>
            </button>
          </div>
        </div>

        <section class="view is-active" id="queue-view" role="tabpanel" aria-labelledby="queue-tab">
          <div class="queue-header">
            <div>
              <p class="eyebrow">Ranked by screening score</p>
              <h2>Priority queue</h2>
            </div>
            <div class="sort-control">
              <label for="sort-order">Sort</label>
              <select id="sort-order">
                <option value="score">Impact</option>
                <option value="date">Newest</option>
                <option value="journal">Journal</option>
              </select>
            </div>
          </div>
          <div class="topic-links" id="topic-links"></div>
          <div id="article-list" class="article-list"></div>
        </section>

        <section class="view" id="digest-view" role="tabpanel" aria-labelledby="digest-tab">
          <div class="digest-header">
            <div>
              <p class="eyebrow">Markdown-ready</p>
              <h2>Weekly digest</h2>
            </div>
            <span id="digest-count">0 items</span>
          </div>
          <textarea id="digest-output" readonly spellcheck="false"></textarea>
        </section>

        <section class="view" id="sources-view" role="tabpanel" aria-labelledby="sources-tab">
          <div class="sources-grid">
            <div>
              <p class="eyebrow">Active search</p>
              <h2>PubMed strategy</h2>
              <pre id="query-output"></pre>
            </div>
            <div>
              <p class="eyebrow">Default coverage</p>
              <h2>Journal watchlist</h2>
              <ul id="journal-output"></ul>
            </div>
          </div>
        </section>
      </section>
    </main>
  </body>
</html>
"""


def _styles_css() -> str:
    return """\
:root {
  color-scheme: light;
  --ink: #1c2524;
  --muted: #5d6b68;
  --subtle: #eef3f1;
  --surface: #ffffff;
  --line: #d8e1df;
  --teal: #176d67;
  --teal-strong: #0f504c;
  --coral: #bb624f;
  --gold: #a7772b;
  --blue: #355f84;
  --plum: #66527a;
  --shadow: 0 18px 45px rgba(31, 43, 41, 0.1);
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  letter-spacing: 0;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  background: #f8faf9;
  color: var(--ink);
}

button,
input,
select,
textarea {
  font: inherit;
  letter-spacing: 0;
}

button {
  cursor: pointer;
}

.app-shell {
  width: min(1440px, calc(100% - 32px));
  margin: 0 auto;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 76px;
  gap: 18px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 8px;
  background: var(--teal-strong);
  color: #fff;
  font-weight: 800;
}

.brand h1,
.brand p,
.masthead h2,
.masthead p,
.queue-header h2,
.queue-header p,
.digest-header h2,
.digest-header p,
.sources-grid h2,
.sources-grid p,
.panel-block h2,
.metric p,
.article-card h3,
.article-card p {
  margin: 0;
}

.brand h1 {
  font-size: clamp(1.15rem, 2vw, 1.55rem);
  line-height: 1.15;
}

.eyebrow {
  color: var(--teal-strong);
  font-size: 0.73rem;
  font-weight: 800;
  text-transform: uppercase;
}

.topbar-actions,
.toolbar-actions,
.status-row,
.article-actions,
.article-meta,
.tag-row,
.score-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.primary-button,
.icon-button,
.text-button,
.tab,
.topic-link {
  border: 1px solid transparent;
  border-radius: 8px;
  min-height: 38px;
  padding: 0 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #fff;
  color: var(--ink);
  text-decoration: none;
}

.primary-button {
  background: var(--teal-strong);
  color: #fff;
  border-color: var(--teal-strong);
}

.icon-button,
.topic-link {
  border-color: var(--line);
}

.text-button {
  min-height: 30px;
  padding: 0 4px;
  background: transparent;
  color: var(--teal-strong);
  font-weight: 800;
}

.primary-button:hover,
.icon-button:hover,
.tab:hover,
.topic-link:hover {
  box-shadow: 0 0 0 3px rgba(23, 109, 103, 0.12);
}

.primary-button svg,
.icon-button svg {
  width: 17px;
  height: 17px;
}

.masthead {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(260px, 1.08fr);
  align-items: stretch;
  min-height: 236px;
  overflow: hidden;
  border: 1px solid #c9d8d4;
  border-radius: 8px;
  background: #102f2e;
  box-shadow: var(--shadow);
}

.masthead::before {
  position: absolute;
  inset: 0;
  content: "";
  background:
    linear-gradient(90deg, rgba(16, 47, 46, 0.96) 0%, rgba(16, 47, 46, 0.82) 43%, rgba(16, 47, 46, 0.06) 77%),
    linear-gradient(0deg, rgba(9, 24, 24, 0.24), rgba(9, 24, 24, 0));
  z-index: 1;
}

.masthead-copy {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  padding: clamp(24px, 5vw, 48px);
  color: #fff;
}

.masthead-copy .eyebrow {
  color: #d9b66c;
}

.masthead h2 {
  max-width: 700px;
  font-size: clamp(1.85rem, 4.8vw, 4.5rem);
  line-height: 0.96;
  font-weight: 850;
}

.masthead img {
  width: 100%;
  height: 100%;
  min-height: 236px;
  object-fit: cover;
}

.status-row span {
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  padding: 4px 10px;
  color: #f2fbf8;
  background: rgba(255, 255, 255, 0.1);
  font-size: 0.86rem;
}

.layout {
  display: grid;
  grid-template-columns: minmax(250px, 310px) minmax(0, 1fr);
  gap: 18px;
  padding: 18px 0 44px;
}

.filter-panel,
.workbench {
  min-width: 0;
}

.filter-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-self: start;
  position: sticky;
  top: 12px;
}

.panel-block {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 14px;
}

.panel-block h2 {
  font-size: 0.96rem;
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.field-label {
  display: block;
  margin: 12px 0 6px;
  color: var(--muted);
  font-size: 0.84rem;
  font-weight: 700;
}

select,
input[type="number"] {
  width: 100%;
  min-height: 38px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
  padding: 0 10px;
}

.check-grid,
.journal-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.filter-option {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
  color: var(--ink);
  font-size: 0.9rem;
  line-height: 1.25;
}

.filter-option input {
  width: 16px;
  height: 16px;
  accent-color: var(--teal);
  margin-top: 2px;
}

.filter-option small {
  display: block;
  color: var(--muted);
  margin-top: 2px;
}

.journal-list {
  max-height: 258px;
  overflow: auto;
  padding-right: 4px;
}

.workbench {
  display: grid;
  gap: 14px;
}

.metrics-bar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 14px;
  min-height: 82px;
}

.metric span {
  display: block;
  color: var(--teal-strong);
  font-size: clamp(1.45rem, 2.8vw, 2.3rem);
  font-weight: 850;
  line-height: 1;
}

.metric p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 0.88rem;
  font-weight: 700;
}

.toolbar,
.queue-header,
.digest-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar {
  min-height: 48px;
}

.tabs {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.tab {
  border: 0;
  border-radius: 0;
  min-width: 96px;
  font-weight: 800;
  color: var(--muted);
}

.tab.is-active {
  background: var(--teal-strong);
  color: #fff;
}

.view {
  display: none;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 18px;
}

.view.is-active {
  display: block;
}

.queue-header {
  margin-bottom: 14px;
}

.queue-header h2,
.digest-header h2,
.sources-grid h2 {
  font-size: clamp(1.35rem, 2.6vw, 2rem);
}

.sort-control {
  display: grid;
  grid-template-columns: auto 150px;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-weight: 700;
}

.topic-links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.topic-link {
  justify-content: space-between;
  min-height: 42px;
  padding: 8px 10px;
}

.topic-link.active {
  border-color: var(--teal-strong);
  background: #edf7f4;
  color: var(--teal-strong);
}

.topic-link span {
  font-weight: 800;
  font-size: 0.82rem;
}

.topic-link b {
  color: var(--muted);
  font-size: 0.82rem;
}

.article-list {
  display: grid;
  gap: 12px;
}

.article-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(86px, 118px);
  gap: 16px;
  border: 1px solid var(--line);
  border-left: 5px solid var(--teal);
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.article-card.priority-high {
  border-left-color: var(--coral);
}

.article-card.priority-watch {
  border-left-color: var(--gold);
}

.article-card h3 {
  font-size: clamp(1rem, 1.7vw, 1.24rem);
  line-height: 1.25;
}

.article-card h3 a {
  color: var(--ink);
  text-decoration-color: rgba(23, 109, 103, 0.34);
  text-underline-offset: 3px;
}

.article-card h3 a:hover {
  color: var(--teal-strong);
}

.article-meta {
  margin: 8px 0 10px;
  color: var(--muted);
  font-size: 0.84rem;
}

.article-meta span:not(:last-child)::after {
  content: "•";
  margin-left: 8px;
  color: #a4b2af;
}

.abstract {
  color: #354340;
  font-size: 0.94rem;
  line-height: 1.5;
  white-space: pre-line;
}

.tag-row {
  margin: 12px 0;
}

.tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 999px;
  background: var(--subtle);
  color: var(--teal-strong);
  padding: 2px 9px;
  font-size: 0.78rem;
  font-weight: 800;
}

.tag.type {
  color: #7a3f32;
  background: #faeee9;
}

.tag.topic {
  color: #294f72;
  background: #eaf1f7;
}

.tag.guideline {
  color: #5d4a15;
  background: #fbf3d9;
}

.article-actions {
  margin-top: 12px;
}

.score-card {
  display: grid;
  align-content: start;
  justify-items: end;
  gap: 8px;
}

.score-number {
  display: grid;
  width: 74px;
  height: 74px;
  place-items: center;
  border-radius: 8px;
  background: #ecf5f2;
  color: var(--teal-strong);
  font-size: 1.55rem;
  font-weight: 900;
}

.priority-high .score-number {
  background: #faeee9;
  color: #8c3c2e;
}

.priority-watch .score-number {
  background: #fbf3d9;
  color: #6e4e15;
}

.score-label {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 800;
  text-align: right;
}

.score-line {
  justify-content: flex-end;
  color: var(--muted);
  font-size: 0.78rem;
}

.empty-state {
  border: 1px dashed #b9c8c4;
  border-radius: 8px;
  padding: 28px;
  text-align: center;
  color: var(--muted);
  background: #fbfdfc;
}

.empty-state strong {
  display: block;
  margin-bottom: 6px;
  color: var(--ink);
  font-size: 1.05rem;
}

.digest-header {
  margin-bottom: 14px;
}

#digest-count {
  color: var(--muted);
  font-weight: 800;
}

#digest-output {
  width: 100%;
  min-height: 620px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  color: var(--ink);
  background: #fbfdfc;
  line-height: 1.45;
}

.sources-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(240px, 0.8fr);
  gap: 18px;
}

pre {
  min-height: 420px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: #102f2e;
  color: #effaf7;
  white-space: pre-wrap;
  line-height: 1.42;
}

#journal-output {
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

#journal-output li {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
  color: var(--muted);
}

#journal-output strong {
  display: block;
  color: var(--ink);
  margin-bottom: 2px;
}

.toast {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 10;
  max-width: min(380px, calc(100vw - 36px));
  border-radius: 8px;
  background: #1f2b29;
  color: #fff;
  padding: 12px 14px;
  box-shadow: var(--shadow);
  font-weight: 700;
}

@media (max-width: 1040px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .filter-panel {
    position: static;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .panel-block:first-child,
  .panel-block:last-child {
    grid-column: 1 / -1;
  }

  .journal-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-height: none;
  }
}

@media (max-width: 760px) {
  .app-shell {
    width: min(100% - 20px, 1440px);
  }

  .topbar,
  .toolbar,
  .queue-header,
  .digest-header {
    align-items: stretch;
    flex-direction: column;
  }

  .topbar-actions,
  .toolbar-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .primary-button,
  .icon-button {
    width: 100%;
  }

  .masthead {
    grid-template-columns: 1fr;
    min-height: 360px;
  }

  .masthead::before {
    background:
      linear-gradient(180deg, rgba(16, 47, 46, 0.97) 0%, rgba(16, 47, 46, 0.76) 62%, rgba(16, 47, 46, 0.15) 100%),
      linear-gradient(0deg, rgba(9, 24, 24, 0.24), rgba(9, 24, 24, 0));
  }

  .masthead-copy {
    position: absolute;
    inset: 0;
    justify-content: flex-start;
  }

  .masthead img {
    min-height: 360px;
  }

  .filter-panel,
  .metrics-bar,
  .sources-grid {
    grid-template-columns: 1fr;
  }

  .journal-list,
  .topic-links {
    grid-template-columns: 1fr;
  }

  .tabs {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
  }

  .tab {
    min-width: 0;
  }

  .article-card {
    grid-template-columns: 1fr;
  }

  .score-card {
    justify-items: start;
    grid-template-columns: auto 1fr;
    align-items: center;
  }

  .score-label,
  .score-line {
    text-align: left;
    justify-content: flex-start;
  }

  .sort-control {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 430px) {
  .topbar-actions,
  .toolbar-actions {
    grid-template-columns: 1fr;
  }

  .brand-mark {
    width: 38px;
    height: 38px;
  }

  .view,
  .panel-block,
  .article-card {
    padding: 12px;
  }
}
"""


def _app_js() -> str:
    return """\
const STORAGE_KEY = "asd-radar-preferences-v2";
const elements = {};
const data = window.RESEARCH_DATA || {};
const pageConfig = window.RESEARCH_PAGE_CONFIG || { activeTopic: "all", pathPrefix: "" };

const state = {
  allArticles: Array.isArray(data.papers) ? data.papers : [],
  filteredArticles: [],
  view: "queue",
  activeTopic: pageConfig.activeTopic || "all"
};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  renderTopicLinks();
  renderFilters();
  hydrateDefaults();
  loadPreferences();
  bindEvents();
  applyFilters();
  updateQueryPreview();
  if (window.lucide) {
    window.lucide.createIcons();
  }
});

function cacheElements() {
  [
    "refresh-button",
    "copy-query-button",
    "copy-digest-button",
    "export-button",
    "reset-button",
    "select-journals-button",
    "date-window",
    "max-results",
    "bucket-filters",
    "topic-filters",
    "age-filters",
    "journal-filters",
    "article-list",
    "source-status",
    "last-updated",
    "metric-total",
    "metric-accepted",
    "metric-watchlist",
    "metric-under25",
    "sort-order",
    "query-output",
    "journal-output",
    "digest-output",
    "digest-count",
    "topic-links"
  ].forEach((id) => {
    elements[id] = document.getElementById(id);
  });
}

function renderTopicLinks() {
  if (!elements["topic-links"]) return;
  const pathPrefix = pageConfig.pathPrefix || "";
  const links = (data.study_types || []).map((item) => {
    const link = document.createElement("a");
    link.className = `topic-link${item.slug === state.activeTopic ? " active" : ""}`;
    link.href = item.slug === "all" ? `${pathPrefix}index.html` : `${pathPrefix}topics/${item.slug}/`;
    link.innerHTML = `<span>${item.label}</span><b>${item.count}</b>`;
    return link;
  });
  elements["topic-links"].replaceChildren(...links);
}

function renderFilters() {
  renderFilterGroup("bucket-filters", data.bucket_options || [], "bucket", (item) => item.label, (item) => `${item.count} papers`);
  renderFilterGroup("topic-filters", (data.study_types || []).filter((item) => item.slug !== "all"), "topic", (item) => item.label, (item) => item.description);
  renderFilterGroup("age-filters", data.age_tags || [], "age", (item) => item.label, (item) => `${item.count} papers`);
  renderFilterGroup("journal-filters", data.journals || [], "journal", (item) => item.label, (item) => `${item.count} papers • ${item.tier}`);
}

function renderFilterGroup(containerId, items, group, labelFn, hintFn) {
  const container = elements[containerId];
  if (!container) return;
  container.replaceChildren(...items.map((item) => makeFilterOption(item, group, labelFn(item), hintFn ? hintFn(item) : "")));
}

function makeFilterOption(item, group, label, hint) {
  const option = document.createElement("label");
  option.className = "filter-option";

  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = item.id || item.slug || item.label;
  input.dataset.group = group;
  input.checked = group !== "bucket" || input.value !== "excluded";
  if (group === "topic" && state.activeTopic !== "all") {
    input.checked = input.value === state.activeTopic;
    input.disabled = input.value !== state.activeTopic;
  }

  const text = document.createElement("span");
  text.textContent = label;
  if (hint) {
    const small = document.createElement("small");
    small.textContent = hint;
    text.appendChild(small);
  }

  option.append(input, text);
  return option;
}

function hydrateDefaults() {
  elements["date-window"].value = String(data.run?.days || 14);
  elements["max-results"].value = String(Math.min(data.run?.max_results || Math.max(state.allArticles.length, 50), 250));
  elements["source-status"].textContent = state.allArticles.length ? "Static export ready" : "No screened papers";
  if (data.generated_at) {
    elements["last-updated"].textContent = `Generated ${data.generated_at}`;
  }
}

function bindEvents() {
  elements["refresh-button"].addEventListener("click", () => {
    window.location.reload();
  });
  elements["copy-query-button"].addEventListener("click", () => copyText(data.run?.query || "", "Search query copied"));
  elements["copy-digest-button"].addEventListener("click", () => copyText(buildDigest(), "Weekly digest copied"));
  elements["export-button"].addEventListener("click", exportCsv);
  elements["reset-button"].addEventListener("click", resetPreferences);
  elements["select-journals-button"].addEventListener("click", selectAllJournals);
  elements["sort-order"].addEventListener("change", () => renderArticles(state.filteredArticles));

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => setView(tab.dataset.view));
  });

  document.querySelectorAll("input, select").forEach((control) => {
    control.addEventListener("change", () => {
      savePreferences();
      applyFilters();
      updateQueryPreview();
    });
  });
}

function loadPreferences() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  if (!saved) return;

  if (saved.days) elements["date-window"].value = String(saved.days);
  if (saved.maxResults) elements["max-results"].value = String(saved.maxResults);
  applyCheckedValues("bucket", saved.buckets);
  applyCheckedValues("topic", saved.topics);
  applyCheckedValues("age", saved.ages);
  applyCheckedValues("journal", saved.journals);
}

function applyCheckedValues(group, values) {
  if (!Array.isArray(values)) return;
  document.querySelectorAll(`input[data-group="${group}"]`).forEach((input) => {
    if (!input.disabled) {
      input.checked = values.includes(input.value);
    }
  });
}

function savePreferences() {
  const prefs = {
    days: Number(elements["date-window"].value),
    maxResults: Number(elements["max-results"].value),
    buckets: selectedIds("bucket"),
    topics: selectedIds("topic"),
    ages: selectedIds("age"),
    journals: selectedIds("journal")
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

function resetPreferences() {
  localStorage.removeItem(STORAGE_KEY);
  document.querySelectorAll('input[data-group="bucket"]').forEach((input) => {
    input.checked = input.value !== "excluded";
  });
  document.querySelectorAll('input[data-group="topic"]').forEach((input) => {
    input.checked = state.activeTopic === "all" ? true : input.value === state.activeTopic;
  });
  document.querySelectorAll('input[data-group="age"], input[data-group="journal"]').forEach((input) => {
    input.checked = true;
  });
  elements["date-window"].value = String(data.run?.days || 14);
  elements["max-results"].value = String(Math.min(data.run?.max_results || Math.max(state.allArticles.length, 50), 250));
  applyFilters();
  updateQueryPreview();
}

function selectAllJournals() {
  document.querySelectorAll('input[data-group="journal"]').forEach((input) => {
    input.checked = true;
  });
  savePreferences();
  applyFilters();
  updateQueryPreview();
}

function selectedIds(group) {
  return [...document.querySelectorAll(`input[data-group="${group}"]:checked`)].map((input) => input.value);
}

function applyFilters() {
  const days = Number(elements["date-window"].value);
  const maxResults = clamp(Number(elements["max-results"].value), 10, 250);
  const buckets = new Set(selectedIds("bucket"));
  const topics = new Set(selectedIds("topic"));
  const ages = new Set(selectedIds("age"));
  const journals = new Set(selectedIds("journal"));

  const filtered = state.allArticles.filter((article) => {
    if (buckets.size && !buckets.has(article.bucket)) return false;
    if (state.activeTopic !== "all" && !paperMatchesLockedTopic(article, state.activeTopic)) return false;
    if (topics.size && !topics.has(article.study_type_slug)) return false;
    if (ages.size && article.age_tags.length && !article.age_tags.some((tag) => ages.has(tag))) return false;
    if (ages.size && !article.age_tags.length) return false;
    if (journals.size && !journals.has(slugify(article.journal))) return false;
    if (!withinDays(article.publication_date, days)) return false;
    return true;
  });

  state.filteredArticles = filtered.sort(sortArticles).slice(0, maxResults);
  renderArticles(state.filteredArticles);
}

function paperMatchesLockedTopic(article, topic) {
  if (topic === "therapy") return article.study_type_group === "therapy";
  if (topic === "non-therapy") return article.study_type_group === "non_therapy";
  return article.study_type_slug === topic;
}

function sortArticles(a, b) {
  const order = elements["sort-order"].value;
  if (order === "date") return compareDates(b.publication_date, a.publication_date) || b.display_score - a.display_score;
  if (order === "journal") return a.journal.localeCompare(b.journal) || b.display_score - a.display_score;
  return b.display_score - a.display_score || compareDates(b.publication_date, a.publication_date);
}

function renderArticles(articles) {
  elements["article-list"].replaceChildren();
  updateMetrics(articles);
  updateDigest();

  if (!articles.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>No articles in the current queue</strong><span>Try a wider window or broader filters.</span>";
    elements["article-list"].append(empty);
    return;
  }

  articles.forEach((article) => {
    elements["article-list"].append(renderArticleCard(article));
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderArticleCard(article) {
  const card = document.createElement("article");
  card.className = `article-card priority-${article.level}`;

  const content = document.createElement("div");
  const title = document.createElement("h3");
  const link = document.createElement("a");
  link.href = article.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = article.title;
  title.append(link);

  const meta = document.createElement("div");
  meta.className = "article-meta";
  [article.journal, formatDate(article.publication_date), article.authors_display, `PMID ${article.pmid}`].forEach((value) => {
    const span = document.createElement("span");
    span.textContent = value;
    meta.append(span);
  });

  const tagRow = document.createElement("div");
  tagRow.className = "tag-row";
  (article.tags.length ? article.tags : [{ label: "ASD", kind: "topic" }]).slice(0, 8).forEach((tag) => {
    const pill = document.createElement("span");
    pill.className = `tag ${tag.kind || ""}`.trim();
    pill.textContent = tag.label;
    tagRow.append(pill);
  });

  const abstract = document.createElement("p");
  abstract.className = "abstract";
  abstract.textContent = article.abstract || article.abstract_excerpt || "Abstract not available from PubMed for this record.";

  const actions = document.createElement("div");
  actions.className = "article-actions";

  const openButton = document.createElement("a");
  openButton.className = "icon-button";
  openButton.href = article.url;
  openButton.target = "_blank";
  openButton.rel = "noreferrer";
  openButton.innerHTML = '<i data-lucide="external-link" aria-hidden="true"></i><span>Open</span>';

  const copyButton = document.createElement("button");
  copyButton.className = "icon-button";
  copyButton.type = "button";
  copyButton.innerHTML = '<i data-lucide="clipboard" aria-hidden="true"></i><span>Copy note</span>';
  copyButton.addEventListener("click", () => copyText(formatArticleNote(article), "Article note copied"));

  actions.append(openButton, copyButton);
  content.append(title, meta, tagRow, abstract, actions);

  const score = document.createElement("aside");
  score.className = "score-card";
  score.setAttribute("aria-label", `Impact score ${article.display_score}`);
  score.innerHTML = `
    <div class="score-number">${article.display_score}</div>
    <div>
      <div class="score-label">${priorityLabel(article.level)}</div>
      <div class="score-line">${article.reasons_summary}</div>
    </div>
  `;

  card.append(content, score);
  return card;
}

function updateMetrics(articles) {
  elements["metric-total"].textContent = String(articles.length);
  elements["metric-accepted"].textContent = String(articles.filter((article) => article.bucket === "accepted").length);
  elements["metric-watchlist"].textContent = String(articles.filter((article) => article.bucket === "watchlist").length);
  elements["metric-under25"].textContent = String(articles.filter((article) => article.is_under_25).length);
}

function updateDigest() {
  const digest = buildDigest();
  elements["digest-output"].value = digest;
  elements["digest-count"].textContent = `${state.filteredArticles.length} item${state.filteredArticles.length === 1 ? "" : "s"}`;
}

function buildDigest() {
  const sorted = [...state.filteredArticles].sort(sortArticles);
  const accepted = sorted.filter((article) => article.bucket === "accepted");
  const watch = sorted.filter((article) => article.bucket === "watchlist");
  const lines = [
    `# ASD Research Digest - ${formatDateForFile(new Date())}`,
    "",
    `Screened records in view: ${sorted.length}`,
    `Accepted records: ${accepted.length}`,
    `Watchlist records: ${watch.length}`,
    `Publication window filter: past ${elements["date-window"].value} days`,
    "",
    "## Accepted"
  ];

  lines.push(...formatDigestGroup(accepted));
  lines.push("", "## Watchlist");
  lines.push(...formatDigestGroup(watch.slice(0, 20)));
  lines.push("", "## Search");
  lines.push(data.run?.pubmed_url || "PubMed URL unavailable");

  return lines.join("\\n");
}

function formatDigestGroup(group) {
  if (!group.length) return ["- None in the current queue."];
  return group.map((article) => {
    const tags = article.tags.map((tag) => tag.label).join(", ") || "ASD";
    return `- **${article.title}** (${article.journal}, ${formatDate(article.publication_date)}). Score ${article.display_score}. ${tags}. ${article.reasons_summary}. ${article.url}`;
  });
}

function formatArticleNote(article) {
  return [
    `Title: ${article.title}`,
    `Journal/date: ${article.journal}, ${formatDate(article.publication_date)}`,
    `Bucket: ${article.bucket_label}`,
    `Priority: ${priorityLabel(article.level)} (${article.display_score})`,
    `Signals: ${article.reasons_summary}`,
    `Study type: ${article.study_type_label}`,
    `PubMed: ${article.url}`,
    article.doi ? `DOI: ${article.doi}` : ""
  ].filter(Boolean).join("\\n");
}

function exportCsv() {
  const header = ["score", "bucket", "study_type", "title", "journal", "date", "authors", "age_tags", "pmid", "doi", "url"];
  const rows = state.filteredArticles.map((article) => [
    article.display_score,
    article.bucket_label,
    article.study_type_label,
    article.title,
    article.journal,
    formatDate(article.publication_date),
    article.authors_display,
    article.age_labels.join("; "),
    article.pmid,
    article.doi,
    article.url
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `asd-research-radar-${formatDateForFile(new Date())}.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function updateQueryPreview() {
  const lines = [
    data.run?.query || "Query unavailable",
    "",
    data.run?.pubmed_url || "PubMed URL unavailable",
    "",
    `Weekly command: ${data.run?.command || "python3 -m research_agent.cli run-weekly"}`
  ];
  elements["query-output"].textContent = lines.join("\\n");
  renderJournalOutput();
}

function renderJournalOutput() {
  if (!elements["journal-output"]) return;
  const items = (data.journal_watchlist || []).map((journal) => {
    const item = document.createElement("li");
    item.innerHTML = `<strong>${journal.label}</strong><span>${journal.tier}</span>`;
    return item;
  });
  elements["journal-output"].replaceChildren(...items);
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".view").forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === `${view}-view`);
  });
  updateDigest();
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    showToast(message);
  } catch (error) {
    console.error(error);
    showToast("Clipboard unavailable");
  }
}

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.append(toast);
  setTimeout(() => toast.remove(), 2400);
}

function withinDays(dateValue, days) {
  if (!dateValue) return false;
  const candidate = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(candidate.getTime())) return false;
  const now = data.generated_at_iso ? new Date(data.generated_at_iso) : new Date();
  const diff = Math.round((now - candidate) / 86400000);
  return diff <= days;
}

function compareDates(left, right) {
  const leftDate = new Date(`${left || "1900-01-01"}T00:00:00`).getTime();
  const rightDate = new Date(`${right || "1900-01-01"}T00:00:00`).getTime();
  return leftDate - rightDate;
}

function formatDate(value) {
  if (!value) return "Date unavailable";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
}

function formatDateForFile(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function priorityLabel(level) {
  if (level === "high") return "High priority";
  if (level === "watch") return "Watch";
  return "Background";
}

function csvEscape(value) {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value || min));
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
"""


def _banner_svg() -> str:
    return """\
<svg width="1200" height="720" viewBox="0 0 1200 720" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="1200" height="720" fill="#133A38"/>
  <g opacity="0.92">
    <circle cx="914" cy="160" r="244" fill="#1E5E59"/>
    <circle cx="1070" cy="420" r="214" fill="#2E756E"/>
    <circle cx="760" cy="506" r="186" fill="#D9B66C"/>
  </g>
  <path d="M739 157C796 174 856 226 888 292C924 367 912 444 868 510" stroke="#F6F1E7" stroke-width="10" stroke-linecap="round"/>
  <path d="M618 247C693 260 772 330 809 403C838 459 840 527 818 585" stroke="#F6F1E7" stroke-width="8" stroke-linecap="round" opacity="0.85"/>
  <path d="M520 176C555 204 585 251 598 298C618 369 602 445 560 512" stroke="#8FD0C5" stroke-width="8" stroke-linecap="round" opacity="0.75"/>
  <g opacity="0.82">
    <rect x="650" y="92" width="264" height="168" rx="18" fill="#0F2F2D"/>
    <rect x="675" y="125" width="134" height="18" rx="9" fill="#D9B66C"/>
    <rect x="675" y="156" width="202" height="12" rx="6" fill="#8FD0C5"/>
    <rect x="675" y="180" width="176" height="12" rx="6" fill="#8FD0C5"/>
    <rect x="675" y="204" width="150" height="12" rx="6" fill="#8FD0C5"/>
  </g>
  <g opacity="0.7">
    <rect x="792" y="394" width="248" height="154" rx="18" fill="#102F2E"/>
    <rect x="821" y="428" width="112" height="16" rx="8" fill="#D9B66C"/>
    <rect x="821" y="458" width="176" height="12" rx="6" fill="#CFE8E2"/>
    <rect x="821" y="482" width="146" height="12" rx="6" fill="#CFE8E2"/>
    <rect x="821" y="506" width="188" height="12" rx="6" fill="#CFE8E2"/>
  </g>
</svg>
"""
