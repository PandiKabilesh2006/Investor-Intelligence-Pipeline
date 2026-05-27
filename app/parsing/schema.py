from pydantic import BaseModel
from typing import List


class PartnerSchema(BaseModel):
    name: str = ""
    role: str = ""
    title: str = ""
    linkedin_url: str = ""
    twitter_url: str = ""
    source_url: str = ""
    extraction_confidence: float = 0.0


class PortfolioCompanySchema(BaseModel):
    company_name: str = ""
    sector: str = ""


class InvestorSchema(BaseModel):
    firm: str
    website: str
    focus_sectors: List[str]
    investment_stage: List[str]
    partners: List[PartnerSchema]
    portfolio_companies: List[PortfolioCompanySchema]
    geography: List[str]
    contact_links: List[str]
