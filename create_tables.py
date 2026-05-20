from app.database.db import engine

from app.database.models import Base


print(

    "\nCreating PostgreSQL tables...\n"
)


Base.metadata.create_all(

    bind=engine
)


print(

    "\nPostgreSQL tables created successfully.\n"
)