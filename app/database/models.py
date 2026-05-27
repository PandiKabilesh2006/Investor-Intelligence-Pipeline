from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from app.database.db import Base

class Investor(Base):
    __tablename__ = "investors"

    id = Column(Integer, primary_key=True)
    firm_name = Column(String, unique=True, nullable=False)
    website = Column(String)
    source_url = Column(Text)
    focus_sectors = Column(ARRAY(Text))
    investment_stage = Column(ARRAY(Text))
    geography = Column(ARRAY(Text))
    embedding = Column(Vector(384))
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)

    partners = relationship("Partner", back_populates="investor", cascade="all, delete-orphan")
    portfolio_companies = relationship("PortfolioCompany", back_populates="investor", cascade="all, delete-orphan")

class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"))
    name = Column(String)
    role = Column(String)
    linkedin_url = Column(Text)
    twitter_url = Column(Text)

    investor = relationship("Investor", back_populates="partners")

class PortfolioCompany(Base):
    __tablename__ = "portfolio_companies"

    id = Column(Integer, primary_key=True)
    investor_id = Column(Integer, ForeignKey("investors.id"))
    company_name = Column(String)
    sector = Column(String)

    investor = relationship("Investor", back_populates="portfolio_companies")
