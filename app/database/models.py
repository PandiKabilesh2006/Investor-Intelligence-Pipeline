from sqlalchemy import (

    Boolean,

    Column,

    Float,

    Integer,

    String,

    Text,

    ForeignKey,

    TIMESTAMP
)

from sqlalchemy.orm import relationship

from sqlalchemy.dialects.postgresql import ARRAY

from pgvector.sqlalchemy import Vector

from app.database.db import Base


# =========================================
# INVESTOR MODEL
# =========================================

class Investor(Base):

    __tablename__ = "investors"


    # =====================================
    # PRIMARY KEY
    # =====================================

    id = Column(

        Integer,

        primary_key=True
    )


    # =====================================
    # CORE INVESTOR DATA
    # =====================================

    firm = Column(

        String,

        unique=True,

        nullable=False
    )


    website = Column(

        String
    )


    source_url = Column(

        Text
    )


    # =====================================
    # ARRAY FIELDS
    # =====================================

    focus_sectors = Column(

        ARRAY(Text)
    )


    investment_stage = Column(

        ARRAY(Text)
    )


    geography = Column(

        ARRAY(Text)
    )


    contact_links = Column(

        ARRAY(Text)
    )


    # =====================================
    # VECTOR EMBEDDING
    # =====================================

    embedding = Column(

        Vector(384)
    )


    # =====================================
    # TIMESTAMP
    # =====================================

    updated_at = Column(

        TIMESTAMP
    )


    # =====================================
    # RELATIONSHIPS
    # =====================================

    partners = relationship(

        "Partner",

        back_populates="investor",

        cascade="all, delete-orphan"
    )


    portfolio_companies = relationship(

        "PortfolioCompany",

        back_populates="investor",

        cascade="all, delete-orphan"
    )


# =========================================
# PARTNER MODEL
# =========================================

class Partner(Base):

    __tablename__ = "partners"


    id = Column(

        Integer,

        primary_key=True
    )


    investor_id = Column(

        Integer,

        ForeignKey("investors.id")
    )


    name = Column(

        String
    )


    # =====================================
    # RELATIONSHIP
    # =====================================

    investor = relationship(

        "Investor",

        back_populates="partners"
    )


# =========================================
# PORTFOLIO COMPANY MODEL
# =========================================

class PortfolioCompany(Base):

    __tablename__ = "portfolio_companies"


    id = Column(

        Integer,

        primary_key=True
    )


    investor_id = Column(

        Integer,

        ForeignKey("investors.id")
    )


    company_name = Column(

        String
    )


    # =====================================
    # RELATIONSHIP
    # =====================================

    investor = relationship(

        "Investor",

        back_populates="portfolio_companies"
    )


# =========================================
# CRAWLED URL MODEL
# =========================================

class CrawledUrl(Base):

    __tablename__ = "crawled_urls"

    id = Column(Integer, primary_key=True)

    url = Column(Text, unique=True, nullable=False)

    discovered_query = Column(Text)

    crawl_status = Column(String)

    markdown_saved = Column(Boolean, default=False)

    updated_at = Column(TIMESTAMP)


# =========================================
# CRAWL QUEUE MODEL
# =========================================

class CrawlQueue(Base):

    __tablename__ = "crawl_queue"

    id = Column(Integer, primary_key=True)

    url = Column(Text, unique=True, nullable=False)

    priority_score = Column(Float, default=1.0)

    discovered_at = Column(TIMESTAMP)

    status = Column(String, default="pending")

    last_crawled = Column(TIMESTAMP)


# =========================================
# FAILED URL MODEL
# =========================================

class FailedUrl(Base):

    __tablename__ = "failed_urls"

    id = Column(Integer, primary_key=True)

    url = Column(Text)

    error_message = Column(Text)

    retry_count = Column(Integer, default=1)

    last_attempt = Column(TIMESTAMP)

    status = Column(String, default="pending")


# from sqlalchemy import (
#     Column,
#     Integer,
#     String,
#     Text,
#     ForeignKey
# )

# from sqlalchemy.orm import relationship

# from app.database.db import Base
# from pgvector.sqlalchemy import Vector


# class Investor(Base):

#     __tablename__ = "investors"

#     id = Column(Integer, primary_key=True)

#     firm = Column(String, unique=True)

#     website = Column(String)

#     focus_sectors = Column(Text)

#     investment_stage = Column(Text)

#     geography = Column(Text)

#     embedding=Column(Vector(384))

#     contact_links=Column(Array(Text))

#     embedding=Column(vector(384))

#     updated_at=Column(TIMESTAMP)


# class Partner(Base):

#     __tablename__ = "partners"

#     id = Column(Integer, primary_key=True)

#     investor_id = Column(Integer, ForeignKey("investors.id"))

#     name = Column(String)


# class PortfolioCompany(Base):

#     __tablename__ = "portfolio_companies"

#     id = Column(Integer, primary_key=True)

#     investor_id = Column(Integer, ForeignKey("investors.id"))

#     company_name = Column(String)
