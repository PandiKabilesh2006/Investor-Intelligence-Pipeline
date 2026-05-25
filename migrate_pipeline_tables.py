"""
Align postgres pipeline tables with run_pipeline / SQLAlchemy models.
Run once after switching DB_NAME to postgres:  python migrate_pipeline_tables.py
"""

from sqlalchemy import text

from app.database.db import engine
from app.database.models import Base, CrawlQueue, CrawledUrl, FailedUrl


def migrate():

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
        conn.execute(
            text(
                """
                UPDATE crawled_urls
                SET updated_at = last_crawled
                WHERE updated_at IS NULL AND last_crawled IS NOT NULL
                """
            )
        )

        conn.commit()

    # crawl_queue, failed_urls, crawled_urls (if missing) from models
    CrawledUrl.__table__.create(engine, checkfirst=True)
    CrawlQueue.__table__.create(engine, checkfirst=True)
    FailedUrl.__table__.create(engine, checkfirst=True)

    print("Pipeline table migration complete.")


if __name__ == "__main__":
    migrate()
