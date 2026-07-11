from sqlalchemy import text
from app.database.db import engine
from app.database.models import Base

print("\nCreating PostgreSQL tables...\n")

# Create SQLAlchemy model tables
Base.metadata.create_all(bind=engine)

# Create raw SQL tables used by the queue and crawl pipeline
raw_tables_sql = [
    """
    CREATE TABLE IF NOT EXISTS crawled_urls (
        url TEXT PRIMARY KEY,
        discovered_query TEXT,
        crawl_status TEXT,
        markdown_saved BOOLEAN,
        updated_at TIMESTAMP WITH TIME ZONE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS crawl_queue (
        id SERIAL PRIMARY KEY,
        url TEXT UNIQUE,
        priority_score DOUBLE PRECISION,
        discovered_at TIMESTAMP WITH TIME ZONE,
        status TEXT,
        last_crawled TIMESTAMP WITH TIME ZONE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS failed_urls (
        id SERIAL PRIMARY KEY,
        url TEXT UNIQUE,
        error_message TEXT,
        retry_count INTEGER,
        last_attempt TIMESTAMP WITH TIME ZONE,
        status TEXT
    );
    """
]

with engine.begin() as connection:
    for sql in raw_tables_sql:
        connection.execute(text(sql))

print("\nPostgreSQL tables created successfully.\n")