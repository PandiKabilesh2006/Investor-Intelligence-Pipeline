import { getInvestors, getMetrics, getPipelineStatus, getPipelineQueueSummary } from "@/lib/api";
import { DashboardClient } from "@/components/dashboard-client";

export const revalidate = 10; // revalidate every 10 seconds

export default async function DashboardPage() {
  // Gracefully fetch all dependencies in parallel on the server
  const [metrics, recentInvestorsRes, allInvestorsRes, pipeline, queueSummary] = await Promise.all([
    getMetrics().catch(() => ({ investors: 0, partners: 0, portfolio_companies: 0, generated_at: "" })),
    getInvestors({ limit: 6 }).catch(() => ({ items: [], total: 0 })),
    getInvestors({ limit: 150 }).catch(() => ({ items: [], total: 0 })),
    getPipelineStatus().catch(() => ({
      pipeline_log: { exists: false, tail: [] },
      scheduler_log: { exists: false, tail: [] },
      latest_run: null
    })),
    getPipelineQueueSummary().catch(() => ({
      queue: { pending: 0, completed: 0, failed: 0, total: 0 },
      crawled_urls: 0,
      failed_urls: 0
    }))
  ]);

  return (
    <DashboardClient 
      metrics={metrics}
      recentInvestors={recentInvestorsRes.items}
      allInvestors={allInvestorsRes.items}
      pipeline={pipeline}
      queueSummary={queueSummary}
    />
  );
}
