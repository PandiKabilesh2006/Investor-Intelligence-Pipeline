from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiMessage(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str


class PartnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = ""
    role: str | None = ""
    title: str | None = ""
    linkedin_url: str | None = ""
    twitter_url: str | None = ""
    source_url: str | None = ""
    extraction_confidence: float | None = None
    scraped_at: datetime | None = None
    updated_at: datetime | None = None


class PortfolioCompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str | None = ""
    sector: str | None = ""


class InvestorListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    firm: str
    website: str | None = None
    source_url: str | None = None
    focus_sectors: list[str] = Field(default_factory=list)
    investment_stage: list[str] = Field(default_factory=list)
    geography: list[str] = Field(default_factory=list)
    contact_links: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvestorDetail(InvestorListItem):
    partners: list[PartnerOut] = Field(default_factory=list)
    portfolio_companies: list[PortfolioCompanyOut] = Field(default_factory=list)


class InvestorListResponse(BaseModel):
    items: list[InvestorListItem]
    total: int
    limit: int
    offset: int


class SemanticSearchRequest(BaseModel):
    query: str
    sector: str | None = None
    stage: str | None = None
    geography: str | None = None
    limit: int = 20


class SemanticInvestorResult(BaseModel):
    id: int
    firm_name: str
    website: str | None = None
    source_url: str | None = None
    updated_at: datetime | None = None
    focus_sectors: list[str] | None = None
    investment_stage: list[str] | None = None
    geography: list[str] | None = None
    contact_links: list[str] | None = None
    distance: float
    semantic_score: float | None = None
    hybrid_score: float | None = None
    sector_boost: float | None = None
    stage_boost: float | None = None
    geography_boost: float | None = None


class OperationsMetrics(BaseModel):
    total_investors: int
    total_partners: int
    total_portfolio_companies: int
    total_crawled_urls: int
    total_failed_urls: int
    pending_failed_urls: int
    queue_depth: int
    last_investor_update: datetime | None = None
    last_pipeline_run: dict[str, Any] | None = None


class CrawlQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    priority_score: float | None = None
    discovered_at: datetime | None = None
    status: str | None = None
    last_crawled: datetime | None = None


class CrawledUrlItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    discovered_query: str | None = None
    crawl_status: str | None = None
    markdown_saved: bool | None = None
    updated_at: datetime | None = None


class FailedUrlItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str | None = None
    error_message: str | None = None
    retry_count: int | None = None
    last_attempt: datetime | None = None
    status: str | None = None


class QueryPreviewRequest(BaseModel):
    sector: str | None = None
    stage: str | None = None
    geography: str | None = None
    business_model: str | None = None
    theme: str | None = None
    manual_queries: list[str] = Field(default_factory=list)
    use_expansion: bool = False


class QueryPreviewResponse(BaseModel):
    queries: list[str]


class PipelineRunCreate(BaseModel):
    trigger: str = "manual"
    queries: list[str] = Field(default_factory=list)
    run_parse: bool = True
    run_insert: bool = True


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    trigger: str
    params: dict[str, Any] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    stats: dict[str, Any] | None = None
    error_message: str | None = None


class LogTailResponse(BaseModel):
    lines: list[str]
