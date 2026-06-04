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
        papers = [
            Paper(
                pmid="site-1",
                title="Randomized parent-mediated intervention study for autistic adolescents",
                abstract="A randomized behavioral intervention studied 160 autistic adolescents ages 13 to 17.",
                journal="JAMA Psychiatry",
                publication_date="2026-05-20",
                doi="10.0000/site",
                authors=("Example A", "Example B"),
                publication_types=("Clinical Trial",),
            ),
            Paper(
                pmid="site-2",
                title="Medication trial for irritability in autism",
                abstract="A placebo-controlled dose study tested medication for irritability in autism.",
                journal="Journal of the American Academy of Child and Adolescent Psychiatry",
                publication_date="2026-05-21",
                authors=("Example C",),
                publication_types=("Clinical Trial",),
            ),
        ]

        with connect(":memory:") as conn:
            init_db(conn)
            for paper in papers:
                upsert_paper(conn, paper)
                upsert_score(conn, paper, score_paper(paper))
            rows = load_screened_papers(conn)

        with tempfile.TemporaryDirectory(dir=ROOT_DIR) as temp_dir:
            site_dir = Path(temp_dir) / "site"
            index_path = write_static_site(rows, output_dir=site_dir)
            html = index_path.read_text(encoding="utf-8")
            therapy_page_exists = (site_dir / "topics" / "therapy" / "index.html").exists()
            non_therapy_page_exists = (site_dir / "topics" / "non-therapy" / "index.html").exists()
            medication_page_exists = (site_dir / "topics" / "medication" / "index.html").exists()

        self.assertIn("ASD Research Weekly Update", html)
        self.assertIn("Randomized parent-mediated intervention study", html)
        self.assertIn("JAMA Psychiatry", html)
        self.assertIn("Therapy", html)
        self.assertIn("Medication", html)
        self.assertIn("window.RESEARCH_DATA", html)
        self.assertTrue(therapy_page_exists)
        self.assertTrue(non_therapy_page_exists)
        self.assertTrue(medication_page_exists)


if __name__ == "__main__":
    unittest.main()
