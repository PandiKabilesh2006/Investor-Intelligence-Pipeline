"use client";

import { useEffect, useState } from "react";
import { getInvestors, getMetrics, getPipelineStatus, getPipelineQueueSummary, Metrics, Investor, PipelineStatus, QueueSummary } from "@/lib/api";
import { DashboardClient } from "@/components/dashboard-client";
import { Loader2 } from "lucide-react";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<{
    metrics: Metrics;
    recentInvestors: Investor[];
    allInvestors: Investor[];
    pipeline: PipelineStatus;
    queueSummary: QueueSummary;
  } | null>(null);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const [metrics, recentInvestorsRes, allInvestorsRes, pipeline, queueSummary] = await Promise.all([
          getMetrics().catch(() => ({ investors: 0, partners: 0, portfolio_companies: 0, generated_at: "" })),
          getInvestors({ limit: 6 }).catch(() => ({ items: [], total: 0 })),
          getInvestors({ limit: 150 }).catch(() => ({ items: [], total: 0 })),
          getPipelineStatus().catch(() => ({
            pipeline_log: { exists: false, tail: [] },
            scheduler_log: { exists: false, tail: [] }
          })),
          getPipelineQueueSummary().catch(() => ({
            queue: { pending: 0, completed: 0, failed: 0, total: 0 },
            crawled_urls: 0,
            failed_urls: 0
          }))
        ]);

        setData({
          metrics,
          recentInvestors: recentInvestorsRes.items,
          allInvestors: allInvestorsRes.items,
          pipeline,
          queueSummary
        });
      } catch (error) {
        console.error("Failed to load dashboard data", error);
      } finally {
        setLoading(false);
      }
    }

    loadDashboardData();
  }, []);

  if (loading || !data) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
        <p className="text-sm text-muted-foreground font-medium">Loading Dashboard...</p>
      </div>
    );
  }

  return (
    <DashboardClient 
      metrics={data.metrics}
      recentInvestors={data.recentInvestors}
      allInvestors={data.allInvestors}
      pipeline={data.pipeline}
      queueSummary={data.queueSummary}
    />
  );
}
