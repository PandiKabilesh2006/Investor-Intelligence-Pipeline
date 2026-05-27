from pydantic import BaseModel, field_validator
from typing import List, Optional, Any


class Partner(BaseModel):
    name: str = ""
    role: str = ""


class ContactLink(BaseModel):
    type: str = ""
    value: str = ""


class InvestorSchema(BaseModel):
    firm: str = ""
    website: str = ""
    thesis: str = ""
    focus_sectors: List[str] = []
    domain_specializations: List[str] = []
    investment_stage: List[str] = []
    check_size: str = ""
    fund_number: str = ""
    fund_size: str = ""
    active_status: str = ""
    pitch_process: str = ""
    partners: List[Partner] = []
    portfolio_companies: List[str] = []
    geography: List[str] = []
    contact_links: List[ContactLink] = []

    # ------------------------------------------------------------------
    # Coerce portfolio_companies: model sometimes returns list of dicts
    # like [{"name": "Acme", "status": "Series A"}] instead of ["Acme"]
    # ------------------------------------------------------------------
    @field_validator("portfolio_companies", mode="before")
    @classmethod
    def coerce_portfolio(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                # Try common name keys
                name = (
                    item.get("name")
                    or item.get("company")
                    or item.get("company_name")
                    or item.get("title")
                    or ""
                )
                if isinstance(name, str) and name.strip():
                    result.append(name.strip())
        return result

    # ------------------------------------------------------------------
    # Coerce partners: model sometimes returns flat strings
    # ------------------------------------------------------------------
    @field_validator("partners", mode="before")
    @classmethod
    def coerce_partners(cls, v: Any) -> List[dict]:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str) and item.strip():
                result.append({"name": item.strip(), "role": ""})
        return result

    # ------------------------------------------------------------------
    # Coerce contact_links: model sometimes returns raw strings
    # ------------------------------------------------------------------
    @field_validator("contact_links", mode="before")
    @classmethod
    def coerce_contact_links(cls, v: Any) -> List[dict]:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str) and item.strip():
                result.append({"type": "url", "value": item.strip()})
        return result

    # ------------------------------------------------------------------
    # Normalize website: ensure https:// prefix, reject blocked domains
    # ------------------------------------------------------------------
    @field_validator("website", mode="before")
    @classmethod
    def normalize_website(cls, v: Any) -> str:
        if isinstance(v, list):
            v = ", ".join(str(i).strip() for i in v if str(i).strip())
        if not isinstance(v, str):
            return ""
        v = v.strip()
        if not v:
            return ""
        blocked = {
            "linkedin.com", "twitter.com", "x.com", "facebook.com",
            "instagram.com", "youtube.com", "crunchbase.com",
            "pitchbook.com", "wellfound.com", "angellist.com", "tracxn.com",
        }
        v_lower = v.lower()
        if any(b in v_lower for b in blocked):
            return ""
        # Ensure scheme
        if v and not v.startswith("http"):
            v = "https://" + v
        return v

    # ------------------------------------------------------------------
    # Coerce string fields that model sometimes returns as lists or other types
    # ------------------------------------------------------------------
    @field_validator("firm", "thesis", "check_size", "fund_number", "fund_size",
                     "active_status", "pitch_process", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> str:
        if isinstance(v, list):
            return ", ".join(str(i).strip() for i in v if str(i).strip())
        if v is None:
            return ""
        return str(v).strip()

    # ------------------------------------------------------------------
    # Coerce list fields that model sometimes returns as a single string
    # ------------------------------------------------------------------
    @field_validator("focus_sectors", "domain_specializations",
                     "investment_stage", "geography", mode="before")
    @classmethod
    def coerce_str_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return []