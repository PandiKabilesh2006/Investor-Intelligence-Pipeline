import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()


# =========================================
# POSTGRESQL DATABASE URL
# =========================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "1234")
DB_NAME = os.getenv("DB_NAME", "investor_intelligence")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "2111")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
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