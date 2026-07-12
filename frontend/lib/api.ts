const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "";

export type Metrics = {
  investors: number;
  partners: number;
  portfolio_companies: number;
  generated_at: string;
};

export type Investor = {
  id: number;
  firm_name: string;
  website?: string | null;
  source_url?: string | null;
  contact_links?: string[];
  focus_sectors: string[];
  investment_stage: string[];
  geography: string[];
  portfolio_company_names?: string[] | null;
  partner_count: number;
  portfolio_count: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Partner = {
  id: number;
  investor_id: number;
  name: string;
  role?: string | null;
  confidence?: number | null;
  linkedin_url?: string | null;
  twitter_url?: string | null;
  firm_name?: string | null;
};

export type PortfolioCompany = {
  id: number;
  investor_id: number;
  company_name: string;
  sector?: string | null;
  firm_name?: string | null;
};

export type PipelineStatus = {
  pipeline_log: {
    exists: boolean;
    last_modified?: string | null;
    tail: string[];
  };
  scheduler_log: {
    exists: boolean;
    last_modified?: string | null;
    tail: string[];
  };
};

export type SearchResult = Investor & {
  firm_name: string;
  distance: number;
  semantic_score: number;
  hybrid_score: number;
  sector_boost: number;
  stage_boost: number;
  geography_boost: number;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type InvestorDetail = Investor & {
  partners: Partner[];
  portfolio_companies: { id: number; investor_id: number; company_name: string; sector?: string | null }[];
};

export type QueueSummary = {
  queue: {
    pending: number;
    completed: number;
    failed: number;
    total: number;
  };
  crawled_urls: number;
  failed_urls: number;
  error?: string;
};

export type ActiveJobs = {
  active: boolean;
  jobs: { pid: number }[];
};


async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    next: {
      revalidate: 30
    }
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getMetrics() {
  return request<Metrics>("/api/metrics");
}

export function getInvestors(params?: {
  q?: string;
  sector?: string;
  stage?: string;
  geography?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const suffix = searchParams.toString();
  return request<Paginated<Investor>>(
    `/api/investors${suffix ? `?${suffix}` : ""}`
  );
}

export function getPartners(params?: {
  q?: string;
  investor_id?: number;
  firm?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const suffix = searchParams.toString();
  return request<Paginated<Partner>>(
    `/api/partners${suffix ? `?${suffix}` : ""}`
  );
}

export function getPortfolioCompanies(params?: {
  q?: string;
  investor_id?: number;
  firm?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const suffix = searchParams.toString();
  return request<Paginated<PortfolioCompany>>(
    `/api/portfolio-companies${suffix ? `?${suffix}` : ""}`
  );
}

export function getPipelineStatus() {
  return request<PipelineStatus>("/api/pipeline/status");
}

export function semanticSearch(params: {
  q: string;
  sector?: string;
  stage?: string;
  geography?: string;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  return request<{
    items: SearchResult[];
    total: number;
    query: string;
  }>(`/api/search?${searchParams.toString()}`);
}

export function getInvestor(id: number) {
  return request<InvestorDetail>(`/api/investors/${id}`);
}

export function getPipelineQueueSummary() {
  return request<QueueSummary>("/api/pipeline/queue-summary");
}

export async function triggerPipelineRun(q: string) {
  const response = await fetch(`${API_BASE_URL}/api/pipeline/trigger?q=${encodeURIComponent(q)}`, {
    method: "POST",
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API request failed: ${response.status}`);
  }

  return response.json() as Promise<{ status: string; query: string; pid: number }>;
}

export function getActivePipelineJobs() {
  return request<ActiveJobs>("/api/pipeline/active-jobs");
}

export type QueryGenResponse = {
  queries: string[];
  source: "ai" | "rule_based";
};

export async function generateQueries(params: {
  sector?: string;
  stage?: string;
  geography?: string;
  theme?: string;
  use_ai?: boolean;
}) {
  const response = await fetch(`${API_BASE_URL}/api/pipeline/generate-queries`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<QueryGenResponse>;
}

