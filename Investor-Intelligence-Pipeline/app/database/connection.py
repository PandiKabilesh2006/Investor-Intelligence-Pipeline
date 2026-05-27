import contextlib
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config.settings import DATABASE_URL

logger = logging.getLogger("investor_pipeline.database")

Base = declarative_base()
_engine = None
_SessionFactory = None

def is_db_enabled() -> bool:
    """Check if the database is configured in the environment."""
    return bool(DATABASE_URL)

def get_engine():
    """Retrieve or create the SQLAlchemy engine."""
    global _engine
    if not is_db_enabled():
        return None
    if _engine is None:
        try:
            _engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 10} if "postgresql" in DATABASE_URL else {}
            )
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            _engine = None
    return _engine

def get_session_factory():
    """Retrieve or create the session factory."""
    global _SessionFactory
    engine = get_engine()
    if engine is None:
        return None
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    return _SessionFactory

@contextlib.contextmanager
def get_db_session():
    """
    Context manager to yield a database session.
    If database is disabled or engine fails, yields None.
    Automatically commits on success or rolls back on exception.
    """
    if not is_db_enabled():
        yield None
        return

    factory = get_session_factory()
    if factory is None:
        yield None
        return

    session = factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()

def init_db() -> bool:
    """
    Initialize the database, creating all tables if they don't exist.
    Returns True if successfully initialized, False otherwise.
    """
    if not is_db_enabled():
        logger.info("Database URL not set. Skipping DB initialization (falling back to JSON/CSV).")
        return False

    engine = get_engine()
    if engine is None:
        logger.error("Could not connect to database. Falling back to local files.")
        return False

    try:
        # Import models here to ensure they are registered on the Base metadata
        from app.database.models import InvestorModel, PartnerModel, PortfolioCompanyModel
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        return False
