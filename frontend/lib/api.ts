function getApiBaseUrl() {
  if (typeof window === "undefined") {
    return process.env.API_BASE_URL || "http://127.0.0.1:8000";
  }

  return process.env.NEXT_PUBLIC_API_BASE_URL || "";
}

const ADMIN_API_KEY = process.env.NEXT_PUBLIC_ADMIN_API_KEY || "";

export type Metrics = {
  investors: number;
  partners: number;
  portfolio_companies: number;
  generated_at: string;
};

export type Investor = {
  id: number;
  firm: string;
  website?: string | null;
  source_url?: string | null;
  focus_sectors: string[];
  investment_stage: string[];
  geography: string[];
  contact_links: string[];
  updated_at?: string | null;
};

export type Partner = {
  id: number;
  investor_id: number;
  name: string;
  role?: string | null;
  title?: string | null;
  linkedin_url?: string | null;
  twitter_url?: string | null;
  source_url?: string | null;
  confidence?: number | null;
  extraction_confidence?: number | null;
  scraped_at?: string | null;
  updated_at?: string | null;
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
  latest_run?: {
    id: number;
    status: string;
    trigger: string;
    started_at?: string | null;
    ended_at?: string | null;
    error_message?: string | null;
  } | null;
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
  portfolio_companies: { id: number; investor_id: number; company_name: string }[];
};

export type QueueSummary = {
  queue: {
    pending: number;
    completed: number;
    failed: number;
    total: number;
  };
  pending_urls?: { id: number; url: string; discovered_at?: string | null }[];
  crawled_urls: number;
  failed_urls: number;
  error?: string;
};

export type ActiveJobs = {
  active: boolean;
  jobs: { pid: number }[];
};

export type QueryPreviewRequest = {
  sector?: string;
  stage?: string;
  geography?: string;
  business_model?: string;
  theme?: string;
  manual_queries?: string[];
  use_expansion?: boolean;
};


async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
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

export async function clearPendingQueue() {
  const response = await fetch(`${getApiBaseUrl()}/api/pipeline/queue/clear-pending`, {
    method: "POST",
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API request failed: ${response.status}`);
  }

  return response.json() as Promise<{ updated: number; status: string }>;
}

export async function previewQueries(payload: QueryPreviewRequest) {
  const response = await fetch(`${getApiBaseUrl()}/api/queries/preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API request failed: ${response.status}`);
  }

  return response.json() as Promise<{ queries: string[] }>;
}

export async function triggerPipelineRun(q: string) {
  const response = await fetch(`${getApiBaseUrl()}/api/pipeline/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(ADMIN_API_KEY ? { "x-admin-key": ADMIN_API_KEY } : {}),
    },
    body: JSON.stringify({
      trigger: "manual",
      queries: [q],
      run_parse: true,
      run_insert: true,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API request failed: ${response.status}`);
  }

  const run = await response.json() as { id: number; status: string };

  return {
    status: run.status,
    query: q,
    pid: run.id,
  };
}

export function getActivePipelineJobs() {
  return request<ActiveJobs>("/api/pipeline/active-jobs");
}

