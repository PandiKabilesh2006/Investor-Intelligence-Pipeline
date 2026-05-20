from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# =========================================
# POSTGRESQL DATABASE URL
# =========================================

DATABASE_URL = (

    "postgresql+psycopg2://"

    "postgres:LiveClass2270157"

    "@localhost:5432/"

    "investor_intelligence"
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