from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research_agent.config import ROOT_DIR
from research_agent.models import Paper
from research_agent.scoring import score_paper
from research_agent.site_export import write_static_site
from research_agent.storage import connect, init_db, load_screened_papers, upsert_paper, upsert_score


class SiteExportTest(unittest.TestCase):
    def test_static_site_contains_screened_paper_data(self) -> None:
        paper = Paper(
            pmid="site-1",
            title="Randomized intervention study for autistic adolescents",
            abstract="A randomized trial studied 160 autistic adolescents ages 13 to 17.",
            journal="JAMA Psychiatry",
            publication_date="2026-05-20",
            doi="10.0000/site",
            authors=("Example A", "Example B"),
            publication_types=("Clinical Trial",),
        )

        with connect(":memory:") as conn:
            init_db(conn)
            upsert_paper(conn, paper)
            upsert_score(conn, paper, score_paper(paper))
            rows = load_screened_papers(conn)

        with tempfile.TemporaryDirectory(dir=ROOT_DIR) as temp_dir:
            index_path = write_static_site(rows, output_dir=Path(temp_dir) / "site")
            html = index_path.read_text(encoding="utf-8")

        self.assertIn("ASD Research Intelligence", html)
        self.assertIn("Randomized intervention study", html)
        self.assertIn("JAMA Psychiatry", html)
        self.assertIn("window.RESEARCH_DATA", html)


if __name__ == "__main__":
    unittest.main()
