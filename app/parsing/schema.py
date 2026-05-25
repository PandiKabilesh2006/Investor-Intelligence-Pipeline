from pydantic import BaseModel
from typing import List


class PartnerSchema(BaseModel):
    name: str
    role: str = ""
    linkedin_url: str = ""
    twitter_url: str = ""
    source_url: str = ""
    confidence: float = 0.0


class InvestorSchema(BaseModel):
    firm: str
    website: str
    focus_sectors: List[str]
    investment_stage: List[str]
    partners: List[PartnerSchema]
