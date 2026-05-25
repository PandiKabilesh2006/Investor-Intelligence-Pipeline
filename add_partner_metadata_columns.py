from sqlalchemy import text

from app.database.db import engine


PARTNER_METADATA_COLUMNS = [
    ("role", "TEXT"),
    ("linkedin_url", "TEXT"),
    ("twitter_url", "TEXT"),
    ("source_url", "TEXT"),
    ("confidence", "DOUBLE PRECISION"),
    ("updated_at", "TIMESTAMP")
]


with engine.begin() as connection:
    for column_name, column_type in PARTNER_METADATA_COLUMNS:
        connection.execute(
            text(
                f"""
                ALTER TABLE partners
                ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                """
            )
        )


print("Partner metadata columns are ready.")
