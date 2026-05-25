from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config.settings import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD
)

# =========================================
# POSTGRESQL DATABASE URL
# =========================================

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# =========================================
# SQLALCHEMY ENGINE
# =========================================

engine = create_engine(

    DATABASE_URL,

    pool_pre_ping=True
)


# =========================================
# SESSION
# =========================================

SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine
)


# =========================================
# BASE MODEL
# =========================================

Base = declarative_base()