"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { Activity, Building2, Users, FileText, CheckCircle2, AlertTriangle, Play, Loader2, Calendar } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Investor, Metrics, PipelineStatus, QueueSummary } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { InvestorDetailModal } from "./investor-detail-modal";
import { ClientIcon } from "@/components/ui/client-icon";

interface DashboardClientProps {
  metrics: Metrics;
  recentInvestors: Investor[];
  allInvestors: Investor[];
  pipeline: PipelineStatus;
  queueSummary: QueueSummary;
}

const COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#06b6d4"];

export function DashboardClient({ metrics, recentInvestors, allInvestors, pipeline, queueSummary }: DashboardClientProps) {
  const [mounted, setMounted] = useState(false);
  const [selectedInvestorId, setSelectedInvestorId] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const lastSyncTime = (
    pipeline.latest_run?.ended_at ||
    pipeline.latest_run?.started_at ||
    pipeline.pipeline_log.last_modified
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  // Compute sector distribution from all available investors
  const sectorData = (() => {
    const counts: Record<string, number> = {};
    allInvestors.forEach((inv) => {
      (inv.focus_sectors || []).forEach((sector) => {
        if (!sector) return;
        const normalized = sector.trim();
        counts[normalized] = (counts[normalized] || 0) + 1;
      });
    });
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);
  })();

  // Compute stage distribution from all available investors
  const stageData = (() => {
    const counts: Record<string, number> = {};
    allInvestors.forEach((inv) => {
      (inv.investment_stage || []).forEach((stage) => {
        if (!stage) return;
        const normalized = stage.trim();
        counts[normalized] = (counts[normalized] || 0) + 1;
      });
    });
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  })();

  const stats = [
    { label: "Total Investors", value: metrics.investors, icon: Building2, color: "text-violet-600" },
    { label: "Active Partners", value: metrics.partners, icon: Users, color: "text-blue-600" },
    { label: "Portfolio Companies", value: metrics.portfolio_companies, icon: FileText, color: "text-emerald-600" },
  ];

  const chartTooltipStyle = {
    contentStyle: { backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "10px" },
    labelStyle: { color: "#0f172a", fontWeight: "bold" as const },
    itemStyle: { color: "#6d28d9" },
  };

  return (
    <div className="space-y-8">
      {/* Page Title */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Investor Intelligence Platform
        </p>
        <h2 className="mt-1 text-3xl font-extrabold tracking-tight text-foreground glow-accent">
          Intelligence Dashboard
        </h2>
      </div>

      {/* Top Stats Cards */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label} className="glass-card glass-card-hover border-border relative overflow-hidden">
              <div className="absolute top-0 left-0 h-1 w-full bg-gradient-to-r from-violet-600 to-blue-500" />
              <CardContent className="p-6 flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{stat.label}</p>
                  <p className="text-4xl font-extrabold text-foreground tracking-tight">{stat.value}</p>
                </div>
                <div className={`rounded-xl bg-muted p-3.5 ${stat.color}`}>
                  <ClientIcon icon={Icon} className="h-6 w-6" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Ingestion & Scrape Summary Indicators */}
      <div className="grid gap-5 md:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-5 flex items-center gap-4 shadow-sm">
          <div className="rounded-lg bg-yellow-500/10 p-2.5 text-yellow-600 shrink-0">
            <ClientIcon icon={Loader2} className="h-5 w-5 animate-spin" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase text-muted-foreground">Pending URL Queue</p>
            <p className="text-lg font-bold text-foreground">{queueSummary.queue.pending}</p>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 flex items-center gap-4 shadow-sm">
          <div className="rounded-lg bg-emerald-500/10 p-2.5 text-emerald-600 shrink-0">
            <ClientIcon icon={CheckCircle2} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase text-muted-foreground">Successfully Crawled</p>
            <p className="text-lg font-bold text-foreground">{queueSummary.crawled_urls}</p>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 flex items-center gap-4 shadow-sm">
          <div className="rounded-lg bg-red-500/10 p-2.5 text-red-600 shrink-0">
            <ClientIcon icon={AlertTriangle} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase text-muted-foreground">Failed Crawl Jobs</p>
            <p className="text-lg font-bold text-foreground">{queueSummary.queue.failed}</p>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 flex items-center gap-4 shadow-sm">
          <div className="rounded-lg bg-blue-500/10 p-2.5 text-blue-600 shrink-0">
            <ClientIcon icon={Calendar} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase text-muted-foreground">Last Sync Time</p>
            <p className="text-sm font-bold text-foreground leading-5">
              {lastSyncTime
                ? formatDate(lastSyncTime) 
                : "N/A"}
            </p>
            {pipeline.latest_run?.status && (
              <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                {pipeline.latest_run.status}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Analytics Charts */}
      {mounted && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Sectors Bar Chart */}
          <Card className="glass-card border-border p-6">
            <CardHeader className="p-0 pb-4">
              <h3 className="text-base font-bold text-foreground">Top Focus Sectors</h3>
              <p className="text-xs text-muted-foreground">Most active sectors mapped to VCs in the pipeline</p>
            </CardHeader>
            <div className="h-[280px] w-full">
              {sectorData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sectorData} layout="vertical" margin={{ left: 15, right: 10, top: 10, bottom: 5 }}>
                    <XAxis type="number" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                    <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={10} width={100} axisLine={false} tickLine={false} />
                    <Tooltip {...chartTooltipStyle} />
                    <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} barSize={16}>
                      {sectorData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  No sector distribution data available
                </div>
              )}
            </div>
          </Card>

          {/* Investment Stages Donut Chart */}
          <Card className="glass-card border-border p-6">
            <CardHeader className="p-0 pb-4">
              <h3 className="text-base font-bold text-foreground">Target Investment Stages</h3>
              <p className="text-xs text-muted-foreground">Distribution of funding stages supported by in-db investors</p>
            </CardHeader>
            <div className="h-[280px] w-full">
              {stageData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={stageData}
                      cx="50%"
                      cy="45%"
                      innerRadius={60}
                      outerRadius={85}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {stageData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[(index + 1) % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip {...chartTooltipStyle} />
                    <Legend verticalAlign="bottom" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "11px", color: "#64748b" }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  No investment stage data available
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Recently Updated & Pipeline log */}
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* Recently Updated Investors */}
        <Card className="glass-card border-border overflow-hidden">
          <CardHeader className="px-6 py-5 border-b border-border">
            <h3 className="text-base font-bold text-foreground">Recently Updated Investors</h3>
            <p className="text-xs text-muted-foreground">Fresh profiles scraped and synchronized recently</p>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-muted-foreground text-xs font-semibold bg-muted/50">
                <tr>
                  <th className="px-6 py-3.5">Firm</th>
                  <th className="px-6 py-3.5">Stage focus</th>
                  <th className="px-6 py-3.5">Last Sync</th>
                  <th className="px-6 py-3.5 text-right">Profile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recentInvestors.map((investor) => (
                  <tr key={investor.id} className="hover:bg-muted/50 transition duration-150">
                    <td className="px-6 py-4 font-semibold text-foreground">
                      {investor.firm}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-xs">
                      {investor.investment_stage.join(", ") || "Not specified"}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-xs">
                      {formatDate(investor.updated_at)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button 
                        onClick={() => {
                          setSelectedInvestorId(investor.id);
                          setIsModalOpen(true);
                        }}
                        className="rounded-lg bg-violet-600/10 px-3 py-1.5 text-xs font-bold text-violet-700 hover:bg-violet-600/20 hover:text-violet-800 transition"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Pipeline Console health log */}
        <Card className="glass-card border-border flex flex-col overflow-hidden">
          <CardHeader className="px-6 py-5 border-b border-border">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <ClientIcon icon={Activity} className="h-4.5 w-4.5 text-violet-600" />
                Pipeline Console
              </h3>
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <p className="text-xs text-muted-foreground">Real-time sync agent execution status</p>
          </CardHeader>
          <CardContent className="p-6 flex-1 flex flex-col justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Last activity recorded on</p>
              <p className="text-lg font-bold text-foreground mt-1">
                {lastSyncTime
                  ? formatDate(lastSyncTime) 
                  : "No recent activity log"}
              </p>
              <div className="mt-4 rounded-xl bg-muted p-4 border border-border flex-1 max-h-[160px] overflow-y-auto">
                <p className="font-mono text-[10px] leading-relaxed text-muted-foreground">
                  {pipeline.pipeline_log.tail.at(-1) || "Pipeline listener waiting for event..."}
                </p>
              </div>
            </div>
            <div className="mt-6 border-t border-border pt-4 flex justify-between items-center">
              <span className="text-[10px] font-semibold text-muted-foreground">Scheduler active</span>
              <a href="/pipeline" className="text-xs font-bold text-violet-600 hover:underline flex items-center gap-1">
                View logs console
                <span>→</span>
              </a>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Investor Profile Modal Sheet */}
      <InvestorDetailModal 
        investorId={selectedInvestorId}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedInvestorId(null);
        }}
      />
    </div>
  );
}
