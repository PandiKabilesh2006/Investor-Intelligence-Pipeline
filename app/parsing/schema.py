from pydantic import BaseModel
from typing import List

class InvestorSchema(BaseModel):
    firm: str
    website: str
    focus_sectors: List[str]
    investment_stage: List[str]
    partners: List[str]