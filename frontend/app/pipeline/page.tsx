"use client";

import { useEffect, useState } from "react";
import { clearPendingQueue, getPipelineStatus, getPipelineQueueSummary, triggerPipelineRun, getActivePipelineJobs, previewQueries, PipelineStatus, QueueSummary, ConfigOptions, getConfigOptions, manualUrlIngestion } from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { Play, RefreshCw, Loader2, AlertCircle, CheckCircle2, Terminal, Info, Wand2, MapPin, Layers, Target, X, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GEOGRAPHY_OPTIONS } from "@/lib/filter-options";

const QUERY_HISTORY_STORAGE_KEY = "investor-pipeline-query-history";

const splitManualQueries = (value: string) =>
  value
    .split("\n")
    .map((query) => query.trim())
    .filter(Boolean);

const dedupeQueries = (queries: string[]) => {
  const seen = new Set<string>();

  return queries.filter((query) => {
    const key = query.trim().toLowerCase();

    if (!key || seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });
};

export default function PipelinePage() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [queue, setQueue] = useState<QueueSummary | null>(null);
  const [activeJobs, setActiveJobs] = useState({ active: false, jobs: [] as { pid: number }[] });
  const [hasMounted, setHasMounted] = useState(false);
  const [configOptions, setConfigOptions] = useState<ConfigOptions>({
    sectors: [],
    stages: [],
    geographies: [],
    themes: [],
  });
  
  const [sector, setSector] = useState("");
  const [stage, setStage] = useState("");
  const [geography, setGeography] = useState("");
  const [theme, setTheme] = useState("");
  const [manualQueries, setManualQueries] = useState("");
  const [generatedQueries, setGeneratedQueries] = useState<string[]>([]);
  const [manualUrl, setManualUrl] = useState("");
  const [ingestingUrl, setIngestingUrl] = useState(false);
  const [queryHistory, setQueryHistory] = useState<string[]>([]);
  const [generatingQueries, setGeneratingQueries] = useState(false);
  const [runningQuery, setRunningQuery] = useState<string | null>(null);
  const [clearingQueue, setClearingQueue] = useState(false);
  const [triggerMessage, setTriggerMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<number>(5); // Refresh logs every 5 seconds
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [logFilter, setLogFilter] = useState<"all" | "info" | "error" | "warning">("all");

  const loadData = async () => {
    const [statusRes, queueRes, jobsRes, optionsRes] = await Promise.allSettled([
      getPipelineStatus(),
      getPipelineQueueSummary(),
      getActivePipelineJobs(),
      getConfigOptions()
    ]);

    if (statusRes.status === "fulfilled") {
      setStatus(statusRes.value);
    }

    if (queueRes.status === "fulfilled") {
      setQueue(queueRes.value);
    }

    if (jobsRes.status === "fulfilled") {
      setActiveJobs(jobsRes.value);
    }

    if (optionsRes.status === "fulfilled") {
      setConfigOptions(optionsRes.value);
      setSector((current) => current || optionsRes.value.sectors[0] || "");
      setStage((current) => current || optionsRes.value.stages[0] || "");
    }

    setLoading(false);
  };

  // Initial load
  useEffect(() => {
    setHasMounted(true);
    loadData();
  }, []);

  useEffect(() => {
    if (!hasMounted) {
      return;
    }

    try {
      const saved = window.localStorage.getItem(QUERY_HISTORY_STORAGE_KEY);
      setQueryHistory(saved ? JSON.parse(saved) : []);
    } catch {
      setQueryHistory([]);
    }
  }, [hasMounted]);

  useEffect(() => {
    if (!hasMounted) {
      return;
    }

    window.localStorage.setItem(
      QUERY_HISTORY_STORAGE_KEY,
      JSON.stringify(queryHistory.slice(0, 30))
    );
  }, [hasMounted, queryHistory]);

  // Auto-refresh logs loop
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadData();
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  const handleGenerateQueries = async () => {
    setGeneratingQueries(true);
    setTriggerMessage(null);

    try {
      const result = await previewQueries({
        sector,
        stage,
        geography,
        theme,
        manual_queries: splitManualQueries(manualQueries),
        use_expansion: false,
      });
      const nextQueries = dedupeQueries(result.queries);

      setGeneratedQueries(nextQueries);
      setQueryHistory((current) => dedupeQueries([...nextQueries, ...current]).slice(0, 30));
      setTriggerMessage({
        type: "success",
        text: `Generated ${nextQueries.length} deduplicated quer${nextQueries.length === 1 ? "y" : "ies"}. Pick one and run it when ready.`
      });
    } catch (err: any) {
      setTriggerMessage({
        type: "error",
        text: err.message || "Failed to generate discovery queries."
      });
    } finally {
      setGeneratingQueries(false);
    }
  };

  const handleRunQuery = async (query: string) => {
    if (query.trim().length < 2) return;

    setRunningQuery(query);
    setTriggerMessage(null);

    try {
      const res = await triggerPipelineRun(query.trim());
      setTriggerMessage({
        type: "success",
        text: `Pipeline ingestion job triggered for "${query}" (Run ID: ${res.pid}). Duplicate URLs will be skipped by the backend.`
      });
      setQueryHistory((current) => dedupeQueries([query, ...current]).slice(0, 30));
      await loadData();
    } catch (err: any) {
      setTriggerMessage({
        type: "error",
        text: err.message || "Failed to trigger pipeline ingestion run."
      });
    } finally {
      setRunningQuery(null);
    }
  };

  const handleManualUrlIngestion = async () => {
    if (manualUrl.trim().length < 8) return;

    setIngestingUrl(true);
    setTriggerMessage(null);

    try {
      const item = await manualUrlIngestion(manualUrl.trim());
      setTriggerMessage({
        type: "success",
        text: `URL extracted and sent to review queue as "${item.firm_name || "unknown firm"}". Review it before approving insert.`
      });
      setManualUrl("");
      await loadData();
    } catch (err: any) {
      setTriggerMessage({
        type: "error",
        text: err.message || "Failed to ingest manual URL."
      });
    } finally {
      setIngestingUrl(false);
    }
  };

  const handleClearPendingQueue = async () => {
    setClearingQueue(true);
    setTriggerMessage(null);

    try {
      const result = await clearPendingQueue();
      setTriggerMessage({
        type: "success",
        text: `Marked ${result.updated} pending queue URL${result.updated === 1 ? "" : "s"} as skipped.`
      });
      await loadData();
    } catch (err: any) {
      setTriggerMessage({
        type: "error",
        text: err.message || "Failed to clear pending queue."
      });
    } finally {
      setClearingQueue(false);
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

      <Card className="glass-card border-border p-6 space-y-4">
        <div className="flex items-center gap-2 border-b border-border pb-3">
          <Sparkles className="h-4.5 w-4.5 text-violet-400" />
          <h3 className="text-sm font-bold text-foreground">Manual URL Ingestion</h3>
        </div>
        <p className="text-xs text-muted-foreground">
          Paste one investor/source URL. The backend extracts and parses it, then sends the result to the review queue before inserting.
        </p>
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            value={manualUrl}
            onChange={(event) => setManualUrl(event.target.value)}
            placeholder="https://example.vc/team"
            className={cn(fieldInputClassName, "px-3 py-2.5")}
          />
          <button
            onClick={handleManualUrlIngestion}
            disabled={ingestingUrl || manualUrl.trim().length < 8}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-5 py-2.5 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {ingestingUrl ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {ingestingUrl ? "Extracting..." : "Extract to Review"}
          </button>
        </div>
      </Card>

      {/* Control room grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Scraper Trigger console */}
        <Card className="glass-card border-border p-6 space-y-4 lg:col-span-2">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Play className="h-4.5 w-4.5 text-violet-400" />
            <h3 className="text-sm font-bold text-foreground">Manual Ingestion Trigger</h3>
          </div>
          
          <p className="text-xs text-muted-foreground">
            Build focused investor search queries, preview them first, then run only the exact query you want. Duplicate URLs are skipped when the backend queues results.
          </p>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1.5">
              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                <Target className="h-3.5 w-3.5" />
                Sector
              </span>
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className={cn(fieldInputClassName, "px-3 py-2.5")}
              >
                {configOptions.sectors.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                <Layers className="h-3.5 w-3.5" />
                Stage
              </span>
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                className={cn(fieldInputClassName, "px-3 py-2.5")}
              >
                {configOptions.stages.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                <MapPin className="h-3.5 w-3.5" />
                Geography
              </span>
              <input
                list="pipeline-geography-options"
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                placeholder="Select geography"
                className={cn(fieldInputClassName, "px-3 py-2.5")}
              />
              <datalist id="pipeline-geography-options">
                {Array.from(new Set([...configOptions.geographies, ...GEOGRAPHY_OPTIONS])).map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
              <p className="text-[10px] text-muted-foreground">
                Countries are grouped into practical investor markets when queries are generated.
              </p>
            </label>

            <label className="space-y-1.5">
              <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                Investment Theme
              </span>
              <input
                type="text"
                list="pipeline-theme-options"
                placeholder="e.g., infrastructure, workflow automation, compliance"
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                className={cn(fieldInputClassName, "px-3 py-2.5")}
              />
              <datalist id="pipeline-theme-options">
                {configOptions.themes.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            </label>
          </div>

          <label className="space-y-1.5 block">
            <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
              Manual Queries
            </span>
            <textarea
              rows={3}
              placeholder={"Optional: one custom query per line\nExample: AI compliance seed investors in India"}
              value={manualQueries}
              onChange={(e) => setManualQueries(e.target.value)}
              className={cn(fieldInputClassName, "px-3 py-2.5 resize-none")}
            />
          </label>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleGenerateQueries}
              disabled={generatingQueries}
              className="rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-violet-500 disabled:bg-violet-800/40 disabled:text-muted-foreground transition flex items-center gap-1.5"
            >
              {generatingQueries ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" />
                  Generate Queries
                </>
              )}
            </button>
            <p className="text-[10px] text-muted-foreground">
              Running a query starts the real crawler, parser, and database insert flow.
            </p>
          </div>

          {(generatedQueries.length > 0 || (hasMounted && queryHistory.length > 0)) && (
            <div className="space-y-3 rounded-xl border border-border bg-muted/30 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-bold text-foreground">
                  Query List
                </p>
                {generatedQueries.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setGeneratedQueries([])}
                    className="flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <X className="h-3 w-3" />
                    Clear preview
                  </button>
                )}
              </div>

              <div className="space-y-2">
                {(generatedQueries.length > 0 ? generatedQueries : queryHistory).map((query) => (
                  <div key={query} className="flex flex-col gap-2 rounded-lg border border-border bg-background/70 p-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs font-medium text-foreground">{query}</p>
                    <button
                      type="button"
                      onClick={() => handleRunQuery(query)}
                      disabled={activeJobs.active || runningQuery !== null}
                      className="flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:bg-emerald-800/30 disabled:text-muted-foreground"
                    >
                      {runningQuery === query ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Starting
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 fill-current" />
                          Run Query
                        </>
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

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

          {status?.latest_run && (
            <div className={`rounded-xl border p-4 text-xs ${
              status.latest_run.status === "success"
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-500"
                : status.latest_run.status === "failed"
                  ? "border-red-500/25 bg-red-500/10 text-red-500"
                  : "border-violet-500/25 bg-violet-500/10 text-violet-500"
            }`}>
              <div className="flex items-center justify-between gap-3">
                <p className="font-bold uppercase tracking-wide">
                  Latest run #{status.latest_run.id}: {status.latest_run.status}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {formatDate(status.latest_run.ended_at || status.latest_run.started_at)}
                </p>
              </div>
              {status.latest_run.error_message && (
                <pre className="mt-3 max-h-28 overflow-y-auto whitespace-pre-wrap rounded-lg bg-background/70 p-3 font-mono text-[10px] text-red-500">
                  {status.latest_run.error_message}
                </pre>
              )}
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
                {queue.queue.pending > 0 && (
                  <div className="space-y-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2">
                    <div className="space-y-1">
                      {(queue.pending_urls || []).map((item) => (
                        <p key={item.id} className="truncate text-[10px] text-muted-foreground" title={item.url}>
                          {item.url}
                        </p>
                      ))}
                    </div>
                    <button
                      onClick={handleClearPendingQueue}
                      disabled={clearingQueue}
                      className="w-full rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs font-bold text-amber-600 transition hover:bg-amber-500/15 disabled:opacity-50 dark:text-amber-400"
                    >
                      {clearingQueue ? "Clearing pending queue..." : "Mark pending as skipped"}
                    </button>
                  </div>
                )}
                <div className="flex justify-between text-xs py-1 border-b border-border">
                  <span className="text-muted-foreground font-medium">Successfully Synced:</span>
                  <span className="text-emerald-400 font-bold">{queue.crawled_urls} URLs</span>
                </div>
                <div className="flex justify-between text-xs py-1 border-b border-border">
                  <span className="text-muted-foreground font-medium">Failed Extraction Jobs:</span>
                  <span className="text-red-400 font-bold">{queue.queue.failed} URLs</span>
                </div>
                <div className="flex justify-between text-xs py-1 border-b border-border">
                  <span className="text-muted-foreground font-medium">Blocked by Site Protection:</span>
                  <span className="text-amber-500 font-bold">{queue.blocked_urls || 0} URLs</span>
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
