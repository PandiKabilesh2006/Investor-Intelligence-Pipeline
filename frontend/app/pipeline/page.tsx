"use client";

import { useEffect, useState } from "react";
import { getPipelineStatus, getPipelineQueueSummary, triggerPipelineRun, getActivePipelineJobs, PipelineStatus, QueueSummary } from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { Settings, Play, RefreshCw, Loader2, AlertCircle, CheckCircle2, Terminal, Search, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function PipelinePage() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [queue, setQueue] = useState<QueueSummary | null>(null);
  const [activeJobs, setActiveJobs] = useState({ active: false, jobs: [] as { pid: number }[] });
  
  const [searchQuery, setSearchQuery] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [triggerMessage, setTriggerMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<number>(5); // Refresh logs every 5 seconds
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [logFilter, setLogFilter] = useState<"all" | "info" | "error" | "warning">("all");

  const loadData = async () => {
    try {
      const [statusRes, queueRes, jobsRes] = await Promise.all([
        getPipelineStatus(),
        getPipelineQueueSummary(),
        getActivePipelineJobs()
      ]);
      setStatus(statusRes);
      setQueue(queueRes);
      setActiveJobs(jobsRes);
    } catch (err) {
      console.error("Failed to load pipeline stats:", err);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadData();
  }, []);

  // Auto-refresh logs loop
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadData();
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  const handleTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim().length < 2) return;
    
    setTriggering(true);
    setTriggerMessage(null);
    try {
      const res = await triggerPipelineRun(searchQuery.trim());
      setTriggerMessage({
        type: "success",
        text: `Pipeline ingestion job successfully triggered for query "${searchQuery}" (PID: ${res.pid})`
      });
      setSearchQuery("");
      // Reload stats immediately
      loadData();
    } catch (err: any) {
      setTriggerMessage({
        type: "error",
        text: err.message || "Failed to trigger pipeline ingestion run."
      });
    } finally {
      setTriggering(false);
    }
  };

  // Highlight log levels in logs output
  const formatLogLine = (line: string) => {
    const isError = line.toLowerCase().includes("error") || line.toLowerCase().includes("fail");
    const isWarning = line.toLowerCase().includes("warn");
    const isInfo = line.toLowerCase().includes("info");

    if (isError) return <span className="text-red-600 font-semibold dark:text-red-400">{line}</span>;
    if (isWarning) return <span className="text-amber-700 dark:text-yellow-400">{line}</span>;
    if (isInfo) return <span className="text-cyan-700 dark:text-cyan-400">{line}</span>;
    return <span className="text-muted-foreground">{line}</span>;
  };

  const getFilteredLogs = (lines: string[]) => {
    if (logFilter === "all") return lines;
    return lines.filter(line => {
      const lower = line.toLowerCase();
      if (logFilter === "error") return lower.includes("error") || lower.includes("fail");
      if (logFilter === "warning") return lower.includes("warn");
      if (logFilter === "info") return lower.includes("info");
      return true;
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Scheduler and Ingestion</p>
          <h2 className="mt-1 text-3xl font-extrabold text-foreground glow-accent">Pipeline Control Room</h2>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-input bg-background text-violet-600 focus:ring-0 focus:ring-offset-0"
            />
            Auto-refresh logs ({refreshInterval}s)
          </label>
          <button 
            onClick={loadData}
            className="flex items-center gap-1.5 rounded-xl bg-muted border border-border px-4 py-2 text-xs font-bold text-muted-foreground hover:text-foreground hover:bg-muted/80 transition"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Control room grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Scraper Trigger console */}
        <Card className="glass-card border-border p-6 space-y-4 lg:col-span-2">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Play className="h-4.5 w-4.5 text-violet-400" />
            <h3 className="text-sm font-bold text-foreground">Manual Ingestion Trigger</h3>
          </div>
          
          <p className="text-xs text-muted-foreground">
            Launch a background scraping worker process to discover and parse new investors based on a target query. This executes the AI-enabled web pipeline.
          </p>

          <form onSubmit={handleTrigger} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute top-3 left-3.5 h-4.5 w-4.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="e.g., Enterprise B2B SaaS VC firms in US"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                disabled={activeJobs.active || triggering}
                className={cn(fieldInputClassName, "pl-11 pr-4 py-2.5 disabled:opacity-50")}
              />
            </div>
            <button
              type="submit"
              disabled={activeJobs.active || triggering || searchQuery.trim().length < 2}
              className="rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-violet-500 disabled:bg-violet-800/40 disabled:text-muted-foreground transition flex items-center gap-1.5 shrink-0"
            >
              {triggering ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Triggering
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-current" />
                  Launch Scraper
                </>
              )}
            </button>
          </form>

          {activeJobs.active && (
            <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 flex items-center gap-3 text-xs text-violet-400">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              <div>
                <p className="font-semibold">Background pipeline crawl process active</p>
                <p className="mt-0.5 text-muted-foreground text-[10px]">
                  PID: {activeJobs.jobs.map(j => j.pid).join(", ")}. Log streams are printing below.
                </p>
              </div>
            </div>
          )}

          {triggerMessage && (
            <div className={`rounded-xl border p-4 flex gap-3 text-xs ${
              triggerMessage.type === "success" 
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" 
                : "border-red-500/25 bg-red-500/10 text-red-400"
            }`}>
              {triggerMessage.type === "success" 
                ? <CheckCircle2 className="h-4.5 w-4.5 shrink-0" /> 
                : <AlertCircle className="h-4.5 w-4.5 shrink-0" />
              }
              <span>{triggerMessage.text}</span>
            </div>
          )}
        </Card>

        {/* Queue Statistics panel */}
        <Card className="glass-card border-border p-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Terminal className="h-4.5 w-4.5 text-violet-400" />
              <h3 className="text-sm font-bold text-foreground">Queue Diagnostics</h3>
            </div>
            
            {queue ? (
              <div className="space-y-3">
                <div className="flex justify-between text-xs py-1 border-b border-border">
                  <span className="text-muted-foreground font-medium">Pending Crawler Queue:</span>
                  <span className="text-foreground font-bold">{queue.queue.pending} URLs</span>
                </div>
                <div className="flex justify-between text-xs py-1 border-b border-border">
                  <span className="text-muted-foreground font-medium">Successfully Synced:</span>
                  <span className="text-emerald-400 font-bold">{queue.crawled_urls} URLs</span>
                </div>
                <div className="flex justify-between text-xs py-1 border-b border-border">
                  <span className="text-muted-foreground font-medium">Failed Extraction Jobs:</span>
                  <span className="text-red-400 font-bold">{queue.queue.failed} URLs</span>
                </div>
                <div className="flex justify-between text-xs py-1">
                  <span className="text-muted-foreground font-medium">Total Crawl Queue:</span>
                  <span className="text-foreground font-bold">{queue.queue.total} URLs</span>
                </div>
              </div>
            ) : (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-violet-400" />
              </div>
            )}
          </div>
          
          <div className="bg-muted/50 rounded-xl p-3 border border-border text-[10px] text-muted-foreground flex gap-2 mt-4">
            <Info className="h-4 w-4 shrink-0 text-violet-400" />
            <span>The nightly pipeline queries Tavily for candidate firms, pushes urls to queue, crawls markdown via Firecrawl, and parses via LLM schema extraction.</span>
          </div>
        </Card>
      </div>

      {/* Log level filter bar */}
      <div className="flex items-center gap-2 bg-muted/50 border border-border rounded-xl px-4 py-2.5 w-fit text-xs text-muted-foreground">
        <span>Log Filter:</span>
        <button 
          onClick={() => setLogFilter("all")} 
          className={`rounded px-2.5 py-1 font-semibold transition ${logFilter === "all" ? "bg-violet-600 text-white" : "hover:text-foreground"}`}
        >
          All
        </button>
        <button 
          onClick={() => setLogFilter("info")} 
          className={`rounded px-2.5 py-1 font-semibold transition ${logFilter === "info" ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/20" : "hover:text-foreground"}`}
        >
          Info
        </button>
        <button 
          onClick={() => setLogFilter("warning")} 
          className={`rounded px-2.5 py-1 font-semibold transition ${logFilter === "warning" ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/20" : "hover:text-foreground"}`}
        >
          Warning
        </button>
        <button 
          onClick={() => setLogFilter("error")} 
          className={`rounded px-2.5 py-1 font-semibold transition ${logFilter === "error" ? "bg-red-500/20 text-red-400 border border-red-500/20" : "hover:text-foreground"}`}
        >
          Error
        </button>
      </div>

      {/* Real-time consoles */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Pipeline Ingestion Console */}
        <Card className="glass-card border-border flex flex-col h-[520px]">
          <CardHeader className="px-6 py-4.5 border-b border-border flex flex-row items-center justify-between shrink-0">
            <div>
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Terminal className="h-4 w-4 text-violet-400" />
                Ingestion Engine (pipeline.log)
              </h3>
              <p className="text-[10px] text-muted-foreground">
                Updated {status ? formatDate(status.pipeline_log.last_modified) : "Loading..."}
              </p>
            </div>
            {status?.pipeline_log.exists && (
              <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20">LOG FOUND</Badge>
            )}
          </CardHeader>
          <div className="flex-1 bg-muted p-5 font-mono text-[10px] leading-relaxed overflow-y-auto select-text scrollbar-thin">
            {status ? (
              <div className="space-y-1.5">
                {getFilteredLogs(status.pipeline_log.tail).map((line, idx) => (
                  <div key={idx} className="whitespace-pre-wrap">{formatLogLine(line)}</div>
                ))}
                {getFilteredLogs(status.pipeline_log.tail).length === 0 && (
                  <p className="text-muted-foreground text-center py-20">No matching log lines recorded</p>
                )}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
              </div>
            )}
          </div>
        </Card>

        {/* Scheduler Cron log Console */}
        <Card className="glass-card border-border flex flex-col h-[520px]">
          <CardHeader className="px-6 py-4.5 border-b border-border flex flex-row items-center justify-between shrink-0">
            <div>
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Terminal className="h-4 w-4 text-violet-400" />
                Scheduler Daemon (scheduler.log)
              </h3>
              <p className="text-[10px] text-muted-foreground">
                Updated {status ? formatDate(status.scheduler_log.last_modified) : "Loading..."}
              </p>
            </div>
            {status?.scheduler_log.exists && (
              <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20">LOG FOUND</Badge>
            )}
          </CardHeader>
          <div className="flex-1 bg-muted p-5 font-mono text-[10px] leading-relaxed overflow-y-auto select-text scrollbar-thin">
            {status ? (
              <div className="space-y-1.5">
                {getFilteredLogs(status.scheduler_log.tail).map((line, idx) => (
                  <div key={idx} className="whitespace-pre-wrap">{formatLogLine(line)}</div>
                ))}
                {getFilteredLogs(status.scheduler_log.tail).length === 0 && (
                  <p className="text-muted-foreground text-center py-20">No scheduler events printed yet</p>
                )}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
