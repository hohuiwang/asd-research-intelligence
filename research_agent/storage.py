from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import DATA_DIR, DB_PATH, ensure_workspace_path
from .models import Paper, Score


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ensure_workspace_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS papers (
            pmid TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT NOT NULL,
            abstract TEXT,
            journal TEXT,
            publication_date TEXT,
            url TEXT,
            authors_json TEXT,
            publication_types_json TEXT,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS screening (
            pmid TEXT PRIMARY KEY,
            venue_score REAL,
            article_impact_score REAL,
            methods_quality_score REAL,
            age_relevance_score REAL,
            novelty_score REAL,
            overall_score REAL,
            age_tags_json TEXT,
            reasons_json TEXT,
            included INTEGER,
            bucket TEXT,
            screened_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pmid) REFERENCES papers (pmid)
        );
        """
    )
    conn.commit()


def upsert_paper(conn: sqlite3.Connection, paper: Paper) -> None:
    conn.execute(
        """
        INSERT INTO papers (
            pmid, doi, title, abstract, journal, publication_date, url,
            authors_json, publication_types_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pmid) DO UPDATE SET
            doi = excluded.doi,
            title = excluded.title,
            abstract = excluded.abstract,
            journal = excluded.journal,
            publication_date = excluded.publication_date,
            url = excluded.url,
            authors_json = excluded.authors_json,
            publication_types_json = excluded.publication_types_json
        """,
        (
            paper.pmid,
            paper.doi,
            paper.title,
            paper.abstract,
            paper.journal,
            paper.publication_date,
            paper.pubmed_url,
            json.dumps(paper.authors),
            json.dumps(paper.publication_types),
        ),
    )
    conn.commit()


def upsert_score(conn: sqlite3.Connection, paper: Paper, score: Score) -> None:
    conn.execute(
        """
        INSERT INTO screening (
            pmid, venue_score, article_impact_score, methods_quality_score,
            age_relevance_score, novelty_score, overall_score, age_tags_json,
            reasons_json, included, bucket
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pmid) DO UPDATE SET
            venue_score = excluded.venue_score,
            article_impact_score = excluded.article_impact_score,
            methods_quality_score = excluded.methods_quality_score,
            age_relevance_score = excluded.age_relevance_score,
            novelty_score = excluded.novelty_score,
            overall_score = excluded.overall_score,
            age_tags_json = excluded.age_tags_json,
            reasons_json = excluded.reasons_json,
            included = excluded.included,
            bucket = excluded.bucket,
            screened_at = CURRENT_TIMESTAMP
        """,
        (
            paper.pmid,
            score.venue_score,
            score.article_impact_score,
            score.methods_quality_score,
            score.age_relevance_score,
            score.novelty_score,
            score.overall_score,
            json.dumps(score.age_tags),
            json.dumps(score.reasons),
            int(score.included),
            score.bucket,
        ),
    )
    conn.commit()


def load_screened_papers(
    conn: sqlite3.Connection,
    bucket: str | None = None,
    pmids: list[str] | tuple[str, ...] | None = None,
) -> list[sqlite3.Row]:
    where_parts = []
    args: list[str] = []

    if bucket:
        where_parts.append("s.bucket = ?")
        args.append(bucket)

    if pmids is not None:
        if not pmids:
            return []
        placeholders = ", ".join("?" for _ in pmids)
        where_parts.append(f"p.pmid IN ({placeholders})")
        args.extend(pmids)

    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    return conn.execute(
        f"""
        SELECT p.*, s.*
        FROM papers p
        JOIN screening s ON p.pmid = s.pmid
        {where}
        ORDER BY s.overall_score DESC, p.publication_date DESC
        """,
        tuple(args),
    ).fetchall()
