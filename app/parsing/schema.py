from pydantic import BaseModel
from typing import List

class PartnerSchema(BaseModel):
    name: str
    role: str = ""
    linkedin_url: str = ""
    twitter_url: str = ""

class PortfolioCompanySchema(BaseModel):
    company_name: str
    sector: str = ""

class InvestorSchema(BaseModel):
    firm_name: str
    website: str
    focus_sectors: List[str]
    investment_stage: List[str]
    geography: List[str]
    partners: List[PartnerSchema]
    portfolio_companies: List[PortfolioCompanySchema]
