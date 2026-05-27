from sqlalchemy import text

from app.database.db import engine


with engine.begin() as connection:
    connection.execute(
        text(
            """
            ALTER TABLE investors
            ADD COLUMN IF NOT EXISTS source_url TEXT
            """
        )
    )


print("Investor source_url column is ready.")
