from __future__ import annotations

import json
import socket
from datetime import datetime
from html import escape
from pathlib import Path

from .config import REPORTS_DIR, SITE_DIR, ensure_workspace_path
from .journals import journal_tier_for


def write_static_site(rows: list, output_dir: Path | None = None) -> Path:
    site_dir = ensure_workspace_path(output_dir or SITE_DIR)
    if not isinstance(site_dir, Path):
        site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    payload = _payload_from_rows(rows)
    index_path = site_dir / "index.html"
    index_path.write_text(_render_html(payload), encoding="utf-8")

    readme_path = site_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# ASD Research Site",
                "",
                "This folder is a static website generated from the local ASD research agent database.",
                "",
                "Share `index.html` directly, or publish the whole `site/` folder with GitHub Pages, Netlify, Vercel, or any static web host.",
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


def _payload_from_rows(rows: list) -> dict:
    papers = [_paper_from_row(row) for row in rows]
    buckets = _counts_by(papers, "bucket")
    age_tags = _tag_counts(papers)
    journals = _counts_by(papers, "journal")

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_report": str((REPORTS_DIR / "latest-weekly-digest.md").relative_to(REPORTS_DIR.parent)),
        "counts": {
            "total": len(papers),
            "accepted": buckets.get("accepted", 0),
            "watchlist": buckets.get("watchlist", 0),
            "excluded": buckets.get("excluded", 0),
        },
        "age_tags": age_tags,
        "top_journals": sorted(journals.items(), key=lambda item: (-item[1], item[0]))[:8],
        "papers": papers,
    }


def _paper_from_row(row) -> dict:
    authors = json.loads(row["authors_json"] or "[]")
    publication_types = json.loads(row["publication_types_json"] or "[]")
    age_tags = json.loads(row["age_tags_json"] or "[]")
    reasons = json.loads(row["reasons_json"] or "[]")
    journal_tier = journal_tier_for(row["journal"] or "")
    abstract = (row["abstract"] or "").strip()

    return {
        "pmid": row["pmid"],
        "doi": row["doi"] or "",
        "title": row["title"],
        "journal": row["journal"] or "Unknown journal",
        "journal_tier": journal_tier.name if journal_tier else "unmatched",
        "publication_date": row["publication_date"] or "",
        "url": row["url"] or "",
        "authors": authors,
        "first_author": authors[0] if authors else "Unknown author",
        "publication_types": publication_types,
        "bucket": row["bucket"],
        "included": bool(row["included"]),
        "overall_score": round(float(row["overall_score"] or 0), 3),
        "venue_score": round(float(row["venue_score"] or 0), 3),
        "article_impact_score": round(float(row["article_impact_score"] or 0), 3),
        "methods_quality_score": round(float(row["methods_quality_score"] or 0), 3),
        "age_relevance_score": round(float(row["age_relevance_score"] or 0), 3),
        "novelty_score": round(float(row["novelty_score"] or 0), 3),
        "age_tags": age_tags,
        "reasons": reasons,
        "abstract_excerpt": abstract[:1000] + ("..." if len(abstract) > 1000 else ""),
        "screened_at": row["screened_at"] or "",
    }


def _counts_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = item.get(key) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _tag_counts(papers: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for paper in papers:
        for tag in paper["age_tags"]:
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _render_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")
    title = "ASD Research Intelligence"
    total = payload["counts"]["total"]
    accepted = payload["counts"]["accepted"]
    watchlist = payload["counts"]["watchlist"]
    generated = escape(payload["generated_at"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --surface: #ffffff;
      --text: #20242c;
      --muted: #667085;
      --line: #d7dce5;
      --blue: #2764d8;
      --green: #16785f;
      --amber: #9a6200;
      --red: #b13d3d;
      --ink: #111827;
      --shadow: 0 12px 30px rgba(21, 31, 51, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.6fr);
      gap: 24px;
      align-items: end;
      padding: 18px 0 24px;
    }}
    h1 {{ margin: 0; color: var(--ink); font-size: 32px; line-height: 1.1; letter-spacing: 0; }}
    .subtitle {{ margin: 10px 0 0; color: var(--muted); max-width: 760px; }}
    .meta {{ color: var(--muted); font-size: 14px; text-align: right; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: var(--shadow);
    }}
    .metric b {{ display: block; color: var(--ink); font-size: 30px; line-height: 1; margin-bottom: 6px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }}
    .tools {{
      display: grid;
      grid-template-columns: minmax(240px, 1fr) 190px 190px 170px;
      gap: 12px;
      padding: 14px;
      align-items: end;
    }}
    label {{ display: grid; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    input, select {{
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      color: var(--text);
      background: #fff;
      font: inherit;
    }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 0 14px 14px; }}
    .tab {{
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      min-height: 38px;
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 700;
    }}
    .tab[aria-pressed="true"] {{ border-color: var(--blue); color: var(--blue); background: #eef4ff; }}
    .chart {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; border-top: 1px solid var(--line); }}
    .chart h2 {{ margin: 0 0 10px; font-size: 15px; color: var(--ink); }}
    .bar-row {{ display: grid; grid-template-columns: 150px 1fr 36px; gap: 10px; align-items: center; margin: 8px 0; font-size: 13px; color: var(--muted); }}
    .bar-track {{ height: 9px; background: #eef0f4; border-radius: 999px; overflow: hidden; }}
    .bar {{ height: 100%; background: linear-gradient(90deg, var(--green), var(--blue)); }}
    .result-line {{ display: flex; justify-content: space-between; gap: 16px; color: var(--muted); font-size: 14px; margin: 16px 0 10px; }}
    .papers {{ display: grid; gap: 12px; }}
    .paper {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 5px solid var(--blue);
      border-radius: 8px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .paper[data-bucket="accepted"] {{ border-left-color: var(--green); }}
    .paper[data-bucket="watchlist"] {{ border-left-color: var(--amber); }}
    .paper[data-bucket="excluded"] {{ border-left-color: var(--red); }}
    .paper-head {{ display: grid; grid-template-columns: minmax(0, 1fr) 96px; gap: 16px; align-items: start; }}
    .paper h2 {{ margin: 0; color: var(--ink); font-size: 20px; line-height: 1.25; letter-spacing: 0; }}
    .citation {{ margin: 8px 0 0; color: var(--muted); font-size: 14px; }}
    .score {{ text-align: right; }}
    .score strong {{ display: block; font-size: 24px; color: var(--ink); }}
    .score span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; font-weight: 700; }}
    .score-meter {{ margin-top: 8px; height: 8px; background: #edf0f5; border-radius: 999px; overflow: hidden; }}
    .score-meter div {{ height: 100%; background: var(--blue); }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }}
    .badge {{ border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; font-size: 12px; color: var(--muted); background: #fbfcfe; }}
    .badge.accepted {{ color: var(--green); border-color: #9ed5c5; background: #ecf8f4; }}
    .badge.watchlist {{ color: var(--amber); border-color: #e9c27d; background: #fff7e8; }}
    .badge.excluded {{ color: var(--red); border-color: #e6aaa7; background: #fff0f0; }}
    .breakdown {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin: 14px 0; }}
    .breakdown div {{ background: #f5f7fa; border: 1px solid #e5e9f0; border-radius: 6px; padding: 8px; min-width: 0; }}
    .breakdown b {{ display: block; font-size: 13px; color: var(--ink); }}
    .breakdown span {{ color: var(--muted); font-size: 12px; }}
    details {{ margin-top: 12px; }}
    summary {{ cursor: pointer; font-weight: 800; color: var(--ink); }}
    .reasons {{ margin: 8px 0 0; padding-left: 20px; color: var(--muted); }}
    .abstract {{ color: #3c4656; margin: 12px 0 0; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    .links a {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; background: #fff; font-weight: 700; }}
    .empty {{ padding: 32px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; text-align: center; color: var(--muted); }}
    footer {{ color: var(--muted); font-size: 13px; padding: 28px 0 8px; }}
    @media (max-width: 860px) {{
      .shell {{ padding: 16px; }}
      header, .summary, .chart, .tools, .paper-head, .breakdown {{ grid-template-columns: 1fr; }}
      .meta, .score {{ text-align: left; }}
      h1 {{ font-size: 27px; }}
      .bar-row {{ grid-template-columns: 120px 1fr 32px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>ASD Research Intelligence</h1>
        <p class="subtitle">High-impact autism research triage, weighted toward under-25 populations with selected adult ASD studies retained for clinical and lifespan relevance.</p>
      </div>
      <div class="meta">
        <div>Generated {generated}</div>
        <div>{total} screened records</div>
      </div>
    </header>

    <section class="summary" aria-label="Screening summary">
      <div class="metric"><b>{total}</b><span>Total screened</span></div>
      <div class="metric"><b>{accepted}</b><span>Accepted</span></div>
      <div class="metric"><b>{watchlist}</b><span>Watchlist</span></div>
      <div class="metric"><b id="visibleCount">{total}</b><span>Currently visible</span></div>
    </section>

    <section class="panel" aria-label="Research filters">
      <div class="tools">
        <label>Search
          <input id="searchInput" type="search" placeholder="Title, journal, author, reason">
        </label>
        <label>Age Tag
          <select id="ageFilter"></select>
        </label>
        <label>Sort
          <select id="sortSelect">
            <option value="score">Score</option>
            <option value="date">Publication date</option>
            <option value="journal">Journal</option>
          </select>
        </label>
        <label>Minimum Score
          <input id="scoreFilter" type="range" min="0" max="1" step="0.05" value="0">
        </label>
      </div>
      <div class="tabs" aria-label="Bucket filters">
        <button class="tab" data-bucket="all" aria-pressed="true">All</button>
        <button class="tab" data-bucket="accepted" aria-pressed="false">Accepted</button>
        <button class="tab" data-bucket="watchlist" aria-pressed="false">Watchlist</button>
        <button class="tab" data-bucket="excluded" aria-pressed="false">Excluded</button>
      </div>
      <div class="chart" aria-label="Screening charts">
        <div>
          <h2>Age Coverage</h2>
          <div id="ageChart"></div>
        </div>
        <div>
          <h2>Top Journals</h2>
          <div id="journalChart"></div>
        </div>
      </div>
    </section>

    <div class="result-line">
      <span id="filterSummary">Showing all records</span>
      <span id="scoreSummary">Minimum score 0.00</span>
    </div>

    <main id="paperList" class="papers" aria-live="polite"></main>
    <footer>Generated from PubMed metadata and local rule-based screening. Treat this as triage, not final scientific appraisal.</footer>
  </div>

  <script>
    window.RESEARCH_DATA = {data_json};
  </script>
  <script>
    const data = window.RESEARCH_DATA;
    const state = {{ bucket: "all", query: "", age: "all", sort: "score", minScore: 0 }};
    const paperList = document.getElementById("paperList");
    const visibleCount = document.getElementById("visibleCount");
    const filterSummary = document.getElementById("filterSummary");
    const scoreSummary = document.getElementById("scoreSummary");
    const searchInput = document.getElementById("searchInput");
    const ageFilter = document.getElementById("ageFilter");
    const sortSelect = document.getElementById("sortSelect");
    const scoreFilter = document.getElementById("scoreFilter");

    function clean(value) {{
      return String(value ?? "").replace(/[&<>"']/g, char => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }}[char]));
    }}

    function bucketLabel(bucket) {{
      return bucket.charAt(0).toUpperCase() + bucket.slice(1);
    }}

    function fillAgeFilter() {{
      const tags = new Set();
      data.papers.forEach(paper => paper.age_tags.forEach(tag => tags.add(tag)));
      ageFilter.innerHTML = '<option value="all">All age tags</option>' +
        [...tags].sort().map(tag => `<option value="${{clean(tag)}}">${{clean(tag.replaceAll("_", " "))}}</option>`).join("");
    }}

    function renderBars(id, rows) {{
      const target = document.getElementById(id);
      const max = Math.max(1, ...rows.map(row => row[1]));
      target.innerHTML = rows.length ? rows.map(([label, count]) => `
        <div class="bar-row">
          <span title="${{clean(label)}}">${{clean(label.replaceAll("_", " "))}}</span>
          <div class="bar-track"><div class="bar" style="width:${{Math.max(5, (count / max) * 100)}}%"></div></div>
          <b>${{count}}</b>
        </div>
      `).join("") : '<div class="empty">No chart data</div>';
    }}

    function paperMatches(paper) {{
      const haystack = [
        paper.title, paper.journal, paper.first_author, paper.bucket,
        paper.age_tags.join(" "), paper.reasons.join(" "), paper.abstract_excerpt
      ].join(" ").toLowerCase();
      return (state.bucket === "all" || paper.bucket === state.bucket)
        && (state.age === "all" || paper.age_tags.includes(state.age))
        && paper.overall_score >= state.minScore
        && (!state.query || haystack.includes(state.query));
    }}

    function sortedPapers(papers) {{
      return [...papers].sort((a, b) => {{
        if (state.sort === "date") return String(b.publication_date).localeCompare(String(a.publication_date));
        if (state.sort === "journal") return a.journal.localeCompare(b.journal) || b.overall_score - a.overall_score;
        return b.overall_score - a.overall_score || String(b.publication_date).localeCompare(String(a.publication_date));
      }});
    }}

    function renderPaper(paper) {{
      const doi = paper.doi ? `<a href="https://doi.org/${{clean(paper.doi)}}" target="_blank" rel="noreferrer">DOI</a>` : "";
      const pubmed = paper.url ? `<a href="${{clean(paper.url)}}" target="_blank" rel="noreferrer">PubMed</a>` : "";
      const ageBadges = paper.age_tags.map(tag => `<span class="badge">${{clean(tag.replaceAll("_", " "))}}</span>`).join("");
      const reasons = paper.reasons.slice(0, 8).map(reason => `<li>${{clean(reason)}}</li>`).join("");
      const scoreWidth = Math.max(3, Math.min(100, paper.overall_score * 100));
      return `
        <article class="paper" data-bucket="${{clean(paper.bucket)}}">
          <div class="paper-head">
            <div>
              <h2>${{clean(paper.title)}}</h2>
              <p class="citation">${{clean(paper.first_author)}}. ${{clean(paper.journal)}}. ${{clean(paper.publication_date || "Date unavailable")}}.</p>
            </div>
            <div class="score">
              <strong>${{paper.overall_score.toFixed(3)}}</strong>
              <span>Score</span>
              <div class="score-meter" aria-hidden="true"><div style="width:${{scoreWidth}}%"></div></div>
            </div>
          </div>
          <div class="badges">
            <span class="badge ${{clean(paper.bucket)}}">${{bucketLabel(paper.bucket)}}</span>
            <span class="badge">${{clean(paper.journal_tier.replaceAll("_", " "))}}</span>
            ${{ageBadges}}
          </div>
          <div class="breakdown">
            <div><b>${{paper.venue_score.toFixed(2)}}</b><span>Venue</span></div>
            <div><b>${{paper.article_impact_score.toFixed(2)}}</b><span>Impact</span></div>
            <div><b>${{paper.methods_quality_score.toFixed(2)}}</b><span>Methods</span></div>
            <div><b>${{paper.age_relevance_score.toFixed(2)}}</b><span>Age fit</span></div>
            <div><b>${{paper.novelty_score.toFixed(2)}}</b><span>Novelty</span></div>
          </div>
          <p class="abstract">${{clean(paper.abstract_excerpt || "No abstract available from PubMed.")}}</p>
          <details>
            <summary>Why this was triaged here</summary>
            <ul class="reasons">${{reasons}}</ul>
          </details>
          <div class="links">${{pubmed}}${{doi}}</div>
        </article>
      `;
    }}

    function render() {{
      const matches = sortedPapers(data.papers.filter(paperMatches));
      visibleCount.textContent = matches.length;
      filterSummary.textContent = `Showing ${{matches.length}} of ${{data.papers.length}} records`;
      scoreSummary.textContent = `Minimum score ${{state.minScore.toFixed(2)}}`;
      paperList.innerHTML = matches.length
        ? matches.map(renderPaper).join("")
        : '<div class="empty">No papers match the current filters.</div>';
    }}

    document.querySelectorAll(".tab").forEach(button => {{
      button.addEventListener("click", () => {{
        document.querySelectorAll(".tab").forEach(tab => tab.setAttribute("aria-pressed", "false"));
        button.setAttribute("aria-pressed", "true");
        state.bucket = button.dataset.bucket;
        render();
      }});
    }});
    searchInput.addEventListener("input", event => {{ state.query = event.target.value.toLowerCase().trim(); render(); }});
    ageFilter.addEventListener("change", event => {{ state.age = event.target.value; render(); }});
    sortSelect.addEventListener("change", event => {{ state.sort = event.target.value; render(); }});
    scoreFilter.addEventListener("input", event => {{ state.minScore = Number(event.target.value); render(); }});

    fillAgeFilter();
    renderBars("ageChart", data.age_tags);
    renderBars("journalChart", data.top_journals);
    render();
  </script>
</body>
</html>
"""
