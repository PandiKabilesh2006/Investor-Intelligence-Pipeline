from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    Boolean,
    DateTime,
    func,
)

from sqlalchemy.orm import relationship

from app.database.db import Base
from pgvector.sqlalchemy import Vector


class Investor(Base):

    __tablename__ = "investors"

    id = Column(Integer, primary_key=True)

    firm_name = Column(String, unique=True)

    website = Column(String)

    focus_sectors = Column(Text)

    investment_stage = Column(Text)

    geography = Column(Text)

    embedding=Column(Vector(384))


class Partner(Base):

    __tablename__ = "partners"

    id = Column(Integer, primary_key=True)

    investor_id = Column(Integer, ForeignKey("investors.id"))

    name = Column(String)


class PortfolioCompany(Base):

    __tablename__ = "portfolio_companies"

    id = Column(Integer, primary_key=True)

    investor_id = Column(Integer, ForeignKey("investors.id"))

    company_name = Column(String)


class CrawledURL(Base):

    __tablename__ = "crawled_urls"

    id = Column(Integer, primary_key=True)

    url = Column(String, unique=True, nullable=False)

    discovered_query = Column(Text)

    crawl_status = Column(String)

    markdown_saved = Column(Boolean, default=False)

    last_crawled = Column(DateTime, server_default=func.now(), onupdate=func.now())
