from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database.connection import Base

class InvestorModel(Base):
    __tablename__ = "investors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    firm_name = Column(String(255), unique=True, nullable=False)
    website = Column(String(1024))
    domain_name = Column(String(255), unique=True, index=True, nullable=False)
    category = Column(String(100), index=True)
    
    # Using JSON column for maximum portability (compatible with Postgres JSONB and SQLite JSON)
    focus_sectors = Column(JSON, default=list)
    investment_stage = Column(JSON, default=list)
    geography = Column(JSON, default=list)
    
    thesis = Column(Text)
    fund_number = Column(String(100))
    fund_size = Column(String(100))
    active_status = Column(String(50))
    pitch_process = Column(Text)
    confidence_score = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    partners = relationship("PartnerModel", back_populates="investor", cascade="all, delete-orphan")
    portfolio_companies = relationship("PortfolioCompanyModel", back_populates="investor", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert model attributes to a standard investor dictionary."""
        return {
            "firm": self.firm_name,
            "website": self.website,
            "thesis": self.thesis or "",
            "focus_sectors": self.focus_sectors or [],
            "investment_stage": self.investment_stage or [],
            "geography": self.geography or [],
            "fund_number": self.fund_number or "",
            "fund_size": self.fund_size or "",
            "active_status": self.active_status or "",
            "pitch_process": self.pitch_process or "",
            "confidence_score": self.confidence_score,
            "partners": [{"name": p.name, "role": p.role, "linkedin_url": p.linkedin_url, "twitter_url": p.twitter_url} for p in self.partners],
            "portfolio_companies": [c.company_name for c in self.portfolio_companies],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PartnerModel(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investor_id = Column(Integer, ForeignKey("investors.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(255))
    linkedin_url = Column(String(1024))
    twitter_url = Column(String(1024))

    # Relationship back to parent
    investor = relationship("InvestorModel", back_populates="partners")


class PortfolioCompanyModel(Base):
    __tablename__ = "portfolio_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investor_id = Column(Integer, ForeignKey("investors.id", ondelete="CASCADE"), nullable=False)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(255))

    # Relationship back to parent
    investor = relationship("InvestorModel", back_populates="portfolio_companies")
