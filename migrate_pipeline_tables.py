"""
Align postgres pipeline tables with run_pipeline / SQLAlchemy models.
Run once after switching DB_NAME to postgres:  python migrate_pipeline_tables.py
"""

from sqlalchemy import text

from app.database.db import engine
from app.database.models import (
    Base,
    CrawlQueue,
    CrawledUrl,
    FailedUrl,
    PipelineRun,
    ReviewQueue,
)


def migrate():

    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:

        # crawled_urls: legacy DB used last_crawled; code expects updated_at
        conn.execute(
            text(
                """
                ALTER TABLE crawled_urls
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP
                """
            )
        )

        has_last_crawled = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'crawled_urls'
                    AND column_name = 'last_crawled'
                )
                """
            )
        ).scalar()

        if has_last_crawled:

            conn.execute(
                text(
                    """
                    UPDATE crawled_urls
                    SET updated_at = last_crawled
                    WHERE updated_at IS NULL AND last_crawled IS NOT NULL
                    """
                )
            )

        conn.execute(
            text(
                """
                ALTER TABLE investors
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE investors
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS role TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS title TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS linkedin_url TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS twitter_url TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS source_url TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS extraction_confidence DOUBLE PRECISION
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMP
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE partners
                SET title = role
                WHERE title IS NULL AND role IS NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE partners
                SET source_url = COALESCE(NULLIF(linkedin_url, ''), NULLIF(twitter_url, ''))
                WHERE source_url IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE partners
                SET extraction_confidence = CASE
                    WHEN source_url IS NOT NULL AND COALESCE(title, role) IS NOT NULL THEN 0.95
                    WHEN COALESCE(title, role) IS NOT NULL THEN 0.80
                    ELSE 0.65
                END
                WHERE extraction_confidence IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE partners
                SET scraped_at = COALESCE(updated_at, NOW())
                WHERE scraped_at IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE portfolio_companies
                ADD COLUMN IF NOT EXISTS sector TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE failed_urls
                ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE failed_urls
                SET status = 'pending'
                WHERE status IS NULL
                """
            )
        )

        conn.commit()

    # crawl_queue, failed_urls, crawled_urls (if missing) from models
    CrawledUrl.__table__.create(engine, checkfirst=True)
    CrawlQueue.__table__.create(engine, checkfirst=True)
    FailedUrl.__table__.create(engine, checkfirst=True)
    PipelineRun.__table__.create(engine, checkfirst=True)
    ReviewQueue.__table__.create(engine, checkfirst=True)

    print("Pipeline table migration complete.")


if __name__ == "__main__":
    migrate()
