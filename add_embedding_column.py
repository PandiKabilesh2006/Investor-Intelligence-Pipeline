from sqlalchemy import text

from app.database.db import engine


with engine.connect() as connection:

    connection.execute(

        text(

            """
            ALTER TABLE investors
            ADD COLUMN IF NOT EXISTS
            embedding vector(384);
            """
        )
    )

    connection.commit()


print(

    "\nEmbedding column added successfully.\n"
)