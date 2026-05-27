from sqlalchemy import text

from app.database.db import engine

from app.database.models import Base


print(

    "\nCreating PostgreSQL tables...\n"
)


with engine.connect() as connection:

    try:
        connection.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        connection.commit()
    except Exception as exc:
        raise RuntimeError(
            "PostgreSQL pgvector extension is required. "
            "Install the vector extension on your PostgreSQL server before running create_tables.py."
        ) from exc


Base.metadata.create_all(

    bind=engine
)


print(

    "\nPostgreSQL tables created successfully.\n"
)