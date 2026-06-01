"use client";

import { useEffect, useMemo, useState } from "react";
import { DatabaseZap, Loader2, Play, RefreshCw, Sparkles } from "lucide-react";
import {
  buildEnrichmentBacklog,
  EnrichmentFileState,
  EnrichmentHistoryItem,
  getEnrichmentAudit,
  getEnrichmentBacklog,
  getEnrichmentHistory,
  runEnrichmentAudit,
  runEnrichmentBatch,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";

type BusyAction = "audit" | "backlog" | "run" | "refresh" | null;

function SummaryCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <Card className="glass-card border-border p-5">
      <p className="text-xs font-bold uppercase text-muted-foreground">{label}</p>
      <p className="mt-2 text-3xl font-extrabold text-foreground">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </Card>
  );
}

function JsonSummary({ summary }: { summary: Record<string, any> }) {
  const entries = Object.entries(summary || {}).filter(([, value]) => {
    return typeof value !== "object" || value === null;
  });

  if (entries.length === 0) {
    return <p className="text-xs text-muted-foreground">No summary available yet.</p>;
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {entries.slice(0, 8).map(([key, value]) => (
        <div key={key} className="rounded-xl border border-border bg-muted/30 p-3">
          <p className="text-[11px] font-bold uppercase text-muted-foreground">
            {key.replaceAll("_", " ")}
          </p>
          <p className="mt-1 text-sm font-semibold text-foreground">{String(value)}</p>
        </div>
      ))}
    </div>
  );
}

export default function EnrichmentPage() {
  const [audit, setAudit] = useState<EnrichmentFileState | null>(null);
  const [backlog, setBacklog] = useState<EnrichmentFileState | null>(null);
  const [history, setHistory] = useState<EnrichmentHistoryItem[]>([]);
  const [lastRun, setLastRun] = useState<EnrichmentFileState | null>(null);
  const [busy, setBusy] = useState<BusyAction>("refresh");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [minScore, setMinScore] = useState(6);
  const [backlogLimit, setBacklogLimit] = useState("");
  const [batchLimit, setBatchLimit] = useState(10);

  const loadData = async () => {
    setBusy("refresh");
    setError(null);

    try {
      const [auditResult, backlogResult, historyResult] = await Promise.all([
        getEnrichmentAudit(),
        getEnrichmentBacklog(),
        getEnrichmentHistory(),
      ]);
      setAudit(auditResult);
      setBacklog(backlogResult);
      setHistory(historyResult.items);
    } catch (err: any) {
      setError(err.message || "Failed to load enrichment data.");
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const statusBreakdown = useMemo(() => {
    return audit?.summary?.status_breakdown || backlog?.summary?.status_breakdown || {};
  }, [audit, backlog]);

  const runAudit = async () => {
    setBusy("audit");
    setMessage(null);
    setError(null);

    try {
      const result = await runEnrichmentAudit();
      setAudit(result);
      setMessage(`Audit complete: ${result.summary?.total_investors || 0} investor record(s) checked.`);
    } catch (err: any) {
      setError(err.message || "Audit failed.");
    } finally {
      setBusy(null);
    }
  };

  const buildBacklog = async () => {
    setBusy("backlog");
    setMessage(null);
    setError(null);

    try {
      const result = await buildEnrichmentBacklog({
        min_score: minScore,
        limit: backlogLimit ? Number(backlogLimit) : "",
      });
      setBacklog(result);
      setMessage(`Backlog built: ${result.summary?.selected_records || 0} record(s) selected.`);
    } catch (err: any) {
      setError(err.message || "Backlog build failed.");
    } finally {
      setBusy(null);
    }
  };

  const runBatch = async () => {
    setBusy("run");
    setMessage(null);
    setError(null);

    try {
      const result = await runEnrichmentBatch(batchLimit);
      setLastRun(result);
      const historyResult = await getEnrichmentHistory();
      setHistory(historyResult.items);
      if (result.summary?.started) {
        setMessage(
          `Batch started in the background with PID ${result.summary.pid}. Refresh history or Review Queue after it finishes.`
        );
      } else {
        setMessage(
          `Batch complete: ${result.summary?.processed || 0} touched, ${result.summary?.queued_review || 0} queued for review.`
        );
      }
    } catch (err: any) {
      setError(err.message || "Enrichment batch failed.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Audit, backlog, and enrichment runs
          </p>
          <h2 className="mt-1 flex items-center gap-2 text-3xl font-extrabold text-foreground glow-accent">
            <Sparkles className="h-7 w-7 text-violet-600" />
            Enrichment
          </h2>
        </div>
        <button
          onClick={loadData}
          disabled={Boolean(busy)}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-50"
        >
          {busy === "refresh" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Refresh
        </button>
      </div>

      {error && <Card className="glass-card border-border p-4 text-sm text-red-600">{error}</Card>}
      {message && <Card className="glass-card border-border p-4 text-sm text-emerald-600">{message}</Card>}

      <div className="grid gap-4 md:grid-cols-4">
        <SummaryCard
          label="Audited Investors"
          value={audit?.summary?.total_investors ?? "N/A"}
          detail={audit?.last_modified ? `Updated ${formatDate(audit.last_modified)}` : "Run audit to create this file"}
        />
        <SummaryCard
          label="Average Score"
          value={audit?.summary?.average_score ?? "N/A"}
          detail="Coverage score out of 7"
        />
        <SummaryCard
          label="Backlog Records"
          value={backlog?.summary?.selected_records ?? "N/A"}
          detail={backlog?.last_modified ? `Updated ${formatDate(backlog.last_modified)}` : "Build backlog after audit"}
        />
        <SummaryCard
          label="Recent Runs"
          value={history.length}
          detail="Saved enrichment result files"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="glass-card border-border p-5">
          <CardHeader className="p-0 pb-3">
            <h3 className="text-base font-bold text-foreground">1. Audit Coverage</h3>
            <p className="text-xs text-muted-foreground">
              Recalculate completeness for every investor record.
            </p>
          </CardHeader>
          <JsonSummary summary={audit?.summary || {}} />
          <button
            onClick={runAudit}
            disabled={Boolean(busy)}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {busy === "audit" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Run Audit
          </button>
        </Card>

        <Card className="glass-card border-border p-5">
          <CardHeader className="p-0 pb-3">
            <h3 className="text-base font-bold text-foreground">2. Build Backlog</h3>
            <p className="text-xs text-muted-foreground">
              Select low-coverage records and generate target URLs/queries.
            </p>
          </CardHeader>
          <div className="grid gap-3">
            <label className="space-y-1">
              <span className="text-xs font-bold text-muted-foreground">Include records below score</span>
              <input
                type="number"
                min={1}
                max={7}
                value={minScore}
                onChange={(event) => setMinScore(Number(event.target.value))}
                className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs font-bold text-muted-foreground">Backlog limit</span>
              <input
                value={backlogLimit}
                onChange={(event) => setBacklogLimit(event.target.value)}
                placeholder="Optional"
                className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
              />
            </label>
          </div>
          <button
            onClick={buildBacklog}
            disabled={Boolean(busy)}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {busy === "backlog" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <DatabaseZap className="h-3.5 w-3.5" />}
            Build Backlog
          </button>
        </Card>

        <Card className="glass-card border-border p-5">
          <CardHeader className="p-0 pb-3">
            <h3 className="text-base font-bold text-foreground">3. Run Enrichment</h3>
            <p className="text-xs text-muted-foreground">
              Process a small batch and send touched records to Review Queue.
            </p>
          </CardHeader>
          <label className="space-y-1">
            <span className="text-xs font-bold text-muted-foreground">Batch size</span>
            <input
              type="number"
              min={1}
              max={50}
              value={batchLimit}
              onChange={(event) => setBatchLimit(Number(event.target.value))}
              className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
            />
          </label>
          <button
            onClick={runBatch}
            disabled={Boolean(busy) || !backlog?.exists}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:opacity-50"
          >
            {busy === "run" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Run Batch
          </button>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="glass-card border-border p-5">
          <CardHeader className="p-0 pb-4">
            <h3 className="text-base font-bold text-foreground">Coverage Breakdown</h3>
            <p className="text-xs text-muted-foreground">Status counts from the latest audit/backlog.</p>
          </CardHeader>
          <div className="flex flex-wrap gap-2">
            {Object.entries(statusBreakdown).length > 0 ? (
              Object.entries(statusBreakdown).map(([status, count]) => (
                <Badge key={status} className="capitalize">
                  {status}: {String(count)}
                </Badge>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">No breakdown available yet.</p>
            )}
          </div>
        </Card>

        <Card className="glass-card border-border p-5">
          <CardHeader className="p-0 pb-4">
            <h3 className="text-base font-bold text-foreground">Latest Batch Result</h3>
            <p className="text-xs text-muted-foreground">The newest run result from this page.</p>
          </CardHeader>
          {lastRun ? (
            <JsonSummary summary={lastRun.summary} />
          ) : (
            <p className="text-xs text-muted-foreground">Run a batch to see the result here.</p>
          )}
        </Card>
      </div>

      <Card className="glass-card border-border overflow-hidden">
        <CardHeader className="border-b border-border px-6 py-5">
          <h3 className="text-base font-bold text-foreground">Backlog Preview</h3>
          <p className="text-xs text-muted-foreground">First 100 records selected for enrichment.</p>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs font-semibold text-muted-foreground">
              <tr>
                <th className="px-6 py-3">Firm</th>
                <th className="px-6 py-3">Score</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Missing</th>
                <th className="px-6 py-3">Targets</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(backlog?.items || []).slice(0, 30).map((item) => (
                <tr key={`${item.investor_id}-${item.firm}`} className="hover:bg-muted/40">
                  <td className="px-6 py-4">
                    <p className="font-semibold text-foreground">{item.firm}</p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{item.website || item.source_url || "No URL"}</p>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground">{item.score}/7</td>
                  <td className="px-6 py-4"><Badge>{item.status}</Badge></td>
                  <td className="px-6 py-4 text-xs text-muted-foreground">
                    {(item.missing_fields || []).join(", ") || "None"}
                  </td>
                  <td className="px-6 py-4 text-xs text-muted-foreground">
                    {(item.page_targets || []).length} URLs · {(item.queries || []).length} queries
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="glass-card border-border p-5">
        <CardHeader className="p-0 pb-4">
          <h3 className="text-base font-bold text-foreground">Run History</h3>
          <p className="text-xs text-muted-foreground">Recent enrichment result exports.</p>
        </CardHeader>
        <div className="grid gap-3 md:grid-cols-2">
          {history.length > 0 ? (
            history.map((run) => (
              <div key={run.file} className="rounded-xl border border-border bg-muted/30 p-3">
                <p className="text-xs font-bold text-foreground">{run.file}</p>
                <p className="text-[11px] text-muted-foreground">{formatDate(run.modified_at)}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  processed {run.summary?.processed ?? 0} · queued {run.summary?.queued_review ?? 0} · no content {run.summary?.queued_no_content_review ?? 0}
                </p>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground">No enrichment runs found yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
