from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database.db import Base


class Investor(Base):

    __tablename__ = "investors"

    id = Column(Integer, primary_key=True)

    firm_name = Column(String, unique=True)

    website = Column(String)

    focus_sectors = Column(Text)

    investment_stage = Column(Text)

    geography = Column(Text)


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