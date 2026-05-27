import logging
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from app.database.connection import get_db_session, is_db_enabled
from app.database.models import InvestorModel, PartnerModel, PortfolioCompanyModel

logger = logging.getLogger("investor_pipeline.db_ops")

def _get_domain_name(url: str) -> str:
    """Helper to extract clean domain name from URL."""
    if not url:
        return ""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.strip()
    except Exception:
        return ""

def get_existing_domains_from_db() -> set:
    """
    Fetch all processed domains from the PostgreSQL database.
    If DB is disabled, returns an empty set.
    """
    if not is_db_enabled():
        return set()
    
    domains = set()
    try:
        with get_db_session() as session:
            if session is None:
                return set()
            results = session.query(InvestorModel.domain_name).all()
            for r in results:
                if r[0]:
                    domains.add(r[0])
    except Exception as e:
        logger.error(f"Failed to fetch existing domains from DB: {e}")
    
    return domains

def get_cached_investor_count(category_slug: str) -> int:
    """Get the count of investors matching a specific category slug in the database."""
    if not is_db_enabled():
        return 0
    try:
        with get_db_session() as session:
            if session is None:
                return 0
            return session.query(InvestorModel).filter(InvestorModel.category == category_slug).count()
    except Exception as e:
        logger.error(f"Failed to get cached count from DB: {e}")
        return 0

def get_cached_investors_by_category(category_slug: str) -> list:
    """Fetch all investors matching a specific category slug, formatted as standard dicts."""
    if not is_db_enabled():
        return []
    try:
        with get_db_session() as session:
            if session is None:
                return []
            investors = session.query(InvestorModel).filter(InvestorModel.category == category_slug).all()
            return [inv.to_dict() for inv in investors]
    except Exception as e:
        logger.error(f"Failed to get cached investors from DB: {e}")
        return []

def upsert_investor_to_db(session: Session, inv_data: dict, category_slug: str) -> bool:
    """
    Upsert a single investor record, along with their partners and portfolio companies.
    Ensures that domain name is unique. If domain already exists, updates metadata and replaces relationships.
    """
    website = inv_data.get("website", "")
    domain = _get_domain_name(website)
    firm_name = inv_data.get("firm", "").strip()
    
    if not domain or not firm_name:
        return False

    # Check if investor already exists by domain or firm name
    db_investor = session.query(InvestorModel).filter(
        (InvestorModel.domain_name == domain) | (InvestorModel.firm_name == firm_name)
    ).first()

    if db_investor:
        # Update fields if new data has a higher confidence score or we are updating it
        new_score = inv_data.get("confidence_score", 0)
        
        # We always update the category to associate it with the active preset
        db_investor.category = category_slug
        
        if new_score >= db_investor.confidence_score:
            db_investor.firm_name = firm_name
            db_investor.website = website
            db_investor.focus_sectors = inv_data.get("focus_sectors", [])
            db_investor.investment_stage = inv_data.get("investment_stage", [])
            db_investor.geography = inv_data.get("geography", [])
            db_investor.thesis = inv_data.get("thesis", "")
            db_investor.fund_number = inv_data.get("fund_number", "")
            db_investor.fund_size = inv_data.get("fund_size", "")
            db_investor.active_status = inv_data.get("active_status", "")
            db_investor.pitch_process = inv_data.get("pitch_process", "")
            db_investor.confidence_score = new_score
            
            # Rebuild relations: delete old partners/portfolio and insert new ones
            session.query(PartnerModel).filter(PartnerModel.investor_id == db_investor.id).delete()
            session.query(PortfolioCompanyModel).filter(PortfolioCompanyModel.investor_id == db_investor.id).delete()
            
            _add_relationships(session, db_investor.id, inv_data)
    else:
        # Create new record
        db_investor = InvestorModel(
            firm_name=firm_name,
            website=website,
            domain_name=domain,
            category=category_slug,
            focus_sectors=inv_data.get("focus_sectors", []),
            investment_stage=inv_data.get("investment_stage", []),
            geography=inv_data.get("geography", []),
            thesis=inv_data.get("thesis", ""),
            fund_number=inv_data.get("fund_number", ""),
            fund_size=inv_data.get("fund_size", ""),
            active_status=inv_data.get("active_status", ""),
            pitch_process=inv_data.get("pitch_process", ""),
            confidence_score=inv_data.get("confidence_score", 0)
        )
        session.add(db_investor)
        session.flush() # Flush to populate db_investor.id
        
        _add_relationships(session, db_investor.id, inv_data)
        
    return True

def _add_relationships(session: Session, investor_id: int, inv_data: dict):
    """Helper to add Partner and PortfolioCompany records."""
    # Add partners
    for p in inv_data.get("partners", []):
        if isinstance(p, dict) and p.get("name"):
            partner = PartnerModel(
                investor_id=investor_id,
                name=p.get("name"),
                role=p.get("role", ""),
                linkedin_url=p.get("linkedin_url", ""),
                twitter_url=p.get("twitter_url", "")
            )
            session.add(partner)

    # Add portfolio companies
    for company_name in inv_data.get("portfolio_companies", []):
        if company_name and isinstance(company_name, str):
            company = PortfolioCompanyModel(
                investor_id=investor_id,
                company_name=company_name
            )
            session.add(company)

def save_investors_to_db(investors: list, category_slug: str) -> int:
    """
    Save list of parsed investor dicts to the database using the upsert logic.
    Returns the count of successfully saved records.
    """
    if not is_db_enabled():
        return 0
        
    saved_count = 0
    try:
        with get_db_session() as session:
            if session is None:
                return 0
            for inv in investors:
                if upsert_investor_to_db(session, inv, category_slug):
                    saved_count += 1
    except Exception as e:
        logger.error(f"Failed to bulk upsert investors: {e}")
        
    return saved_count
