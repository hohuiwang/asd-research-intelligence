from __future__ import annotations

import unittest

from research_agent.models import Paper
from research_agent.scoring import score_paper
from research_agent.storage import connect, init_db, load_screened_papers, upsert_paper, upsert_score


class StorageTest(unittest.TestCase):
    def test_load_screened_papers_can_filter_to_current_run_pmids(self) -> None:
        papers = [
            Paper(
                pmid="current",
                title="Randomized trial for autistic children",
                abstract="A randomized trial included 150 children with autism.",
                journal="JAMA Pediatrics",
                publication_date="2026-05-01",
                publication_types=("Clinical Trial",),
            ),
            Paper(
                pmid="old",
                title="Older database record",
                abstract="A cohort of adults with autism.",
                journal="Autism",
                publication_date="2026-04-01",
                publication_types=("Journal Article",),
            ),
        ]

        with connect(":memory:") as conn:
            init_db(conn)
            for paper in papers:
                upsert_paper(conn, paper)
                upsert_score(conn, paper, score_paper(paper))

            rows = load_screened_papers(conn, pmids=["current"])

        self.assertEqual([row["pmid"] for row in rows], ["current"])


if __name__ == "__main__":
    unittest.main()
