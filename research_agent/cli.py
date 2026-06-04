from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver

from .config import SITE_DIR
from .models import Paper
from .pubmed import fetch_recent_papers
from .reports import write_weekly_digest
from .samples import SAMPLE_PAPERS
from .scoring import score_paper
from .site_export import find_available_port, write_static_site
from .storage import connect, init_db, load_screened_papers, upsert_paper, upsert_score


def main() -> None:
    parser = argparse.ArgumentParser(description="Autism research intelligence agent MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create the local SQLite database")
    subparsers.add_parser("demo", help="Run the pipeline with built-in sample papers")
    subparsers.add_parser("export-site", help="Generate the static website from screened papers")
    subparsers.add_parser("rescore", help="Recompute stored paper scores and regenerate report/site outputs")

    serve_parser = subparsers.add_parser("serve-site", help="Generate and preview the static website locally")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface for the preview server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Preferred preview server port")
    serve_parser.add_argument("--no-export", action="store_true", help="Serve the existing site without regenerating it")

    run_parser = subparsers.add_parser("run-weekly", help="Fetch, score, store, and report recent PubMed papers")
    run_parser.add_argument("--days", type=int, default=7, help="Publication-date lookback window")
    run_parser.add_argument("--max-results", type=int, default=100, help="Maximum PubMed records to fetch")
    run_parser.add_argument(
        "--journal-scope",
        choices=("high-impact", "broad"),
        default="high-impact",
        help="Use the curated high-impact journal filter, or search PubMed broadly and let scoring triage",
    )
    run_parser.add_argument(
        "--population-scope",
        choices=("priority", "all"),
        default="priority",
        help="Prioritize under-25 and adult ASD population terms, or search all ASD records",
    )

    args = parser.parse_args()

    if args.command == "init-db":
        with connect() as conn:
            init_db(conn)
        print("Database initialized.")
        return

    if args.command == "demo":
        with connect() as conn:
            init_db(conn)
            for paper in SAMPLE_PAPERS:
                score = score_paper(paper)
                upsert_paper(conn, paper)
                upsert_score(conn, paper, score)

            rows = load_screened_papers(conn, pmids=[paper.pmid for paper in SAMPLE_PAPERS])
            report_path = write_weekly_digest(rows)
            site_path = write_static_site(rows)

        print(f"Screened {len(SAMPLE_PAPERS)} sample papers.")
        print(f"Report written to {report_path}")
        print(f"Website written to {site_path}")
        return

    if args.command == "export-site":
        with connect() as conn:
            init_db(conn)
            rows = load_screened_papers(conn)
            site_path = write_static_site(rows)

        print(f"Exported {len(rows)} screened papers.")
        print(f"Website written to {site_path}")
        return

    if args.command == "rescore":
        with connect() as conn:
            init_db(conn)
            rows = load_screened_papers(conn)
            papers = [_paper_from_row(row) for row in rows]
            for paper in papers:
                upsert_score(conn, paper, score_paper(paper))

            rescored_rows = load_screened_papers(conn)
            report_path = write_weekly_digest(rescored_rows)
            site_path = write_static_site(rescored_rows)

        print(f"Rescored {len(papers)} stored papers.")
        print(f"Report written to {report_path}")
        print(f"Website written to {site_path}")
        return

    if args.command == "serve-site":
        with connect() as conn:
            init_db(conn)
            rows = load_screened_papers(conn)
            site_path = write_static_site(rows) if not args.no_export else None

        site_dir = (site_path.parent if site_path else SITE_DIR).resolve()
        port = find_available_port(args.port, args.host)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))

        with socketserver.TCPServer((args.host, port), handler) as server:
            print(f"Serving {site_dir}")
            print(f"Open http://{args.host}:{port}")
            if port != args.port:
                print(f"Preferred port {args.port} was busy; using {port}.")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
        return

    if args.command == "run-weekly":
        with connect() as conn:
            init_db(conn)
            papers = fetch_recent_papers(
                days=args.days,
                max_results=args.max_results,
                journal_scope=args.journal_scope,
                population_scope=args.population_scope,
            )
            for paper in papers:
                score = score_paper(paper)
                upsert_paper(conn, paper)
                upsert_score(conn, paper, score)

            rows = load_screened_papers(conn, pmids=[paper.pmid for paper in papers])
            report_path = write_weekly_digest(rows)
            site_path = write_static_site(rows)

        print(f"Fetched and screened {len(papers)} papers.")
        print(f"Journal scope: {args.journal_scope}")
        print(f"Population scope: {args.population_scope}")
        print(f"Report written to {report_path}")
        print(f"Website written to {site_path}")
        return


def _paper_from_row(row) -> Paper:
    return Paper(
        pmid=row["pmid"],
        title=row["title"],
        abstract=row["abstract"] or "",
        journal=row["journal"] or "",
        publication_date=row["publication_date"] or "",
        doi=row["doi"] or None,
        authors=tuple(json.loads(row["authors_json"] or "[]")),
        publication_types=tuple(json.loads(row["publication_types_json"] or "[]")),
    )


if __name__ == "__main__":
    main()
