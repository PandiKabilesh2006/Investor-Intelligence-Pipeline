"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Eye, Link2, Loader2, Play, RefreshCw } from "lucide-react";
import { bulkDeleteQualityRecords, EnrichmentHistoryItem, getEnrichmentHistory, getQualityCoverage, manualUrlIngestion, QualityCoverage, rebuildEnrichmentBacklog } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { InvestorDetailModal } from "@/components/investor-detail-modal";

const COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#64748b"];

export default function QualityPage() {
  const [data, setData] = useState<QualityCoverage | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyUrl, setBusyUrl] = useState<string | null>(null);
  const [manualUrl, setManualUrl] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedInvestorId, setSelectedInvestorId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<EnrichmentHistoryItem[]>([]);
  const [rebuilding, setRebuilding] = useState(false);
  const qualityItems = data?.items || [];
  const selectedItems = useMemo(
    () => qualityItems.filter((item) => selectedIds.includes(item.id)),
    [qualityItems, selectedIds]
  );
  const selectedExtractableItems = useMemo(
    () => selectedItems.filter((item) => Boolean(item.website)),
    [selectedItems]
  );
  const allVisibleSelected = qualityItems.length > 0 && qualityItems.every((item) => selectedIds.includes(item.id));

  const loadData = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      setData(await getQualityCoverage());
      getEnrichmentHistory().then((result) => setHistory(result.items)).catch(() => setHistory([]));
      setSelectedIds([]);
    } catch (err: any) {
      setError(err.message || "Failed to load quality coverage.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const extractToReview = async (url?: string | null, investorId?: number) => {
    const targetUrl = (url || manualUrl).trim();

    if (targetUrl.length < 8) return;

    setBusyUrl(targetUrl);
    setError(null);
    setMessage(null);

    try {
      const item = await manualUrlIngestion(targetUrl, investorId);
      setManualUrl("");
      setMessage(
        investorId
          ? `Extracted "${item.firm_name || "unknown firm"}" and sent it to Review Queue. Approve to update investors, or reject to delete this source record.`
          : `Extracted "${item.firm_name || "unknown firm"}" and sent it to Review Queue. Approve there to update investors.`
      );
    } catch (err: any) {
      setMessage(err.message || "Failed to extract URL. Try an alternate source or review manually.");
    } finally {
      setBusyUrl(null);
    }
  };

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      setSelectedIds([]);
      return;
    }

    setSelectedIds(qualityItems.map((item) => item.id));
  };

  const bulkExtractToReview = async () => {
    if (selectedExtractableItems.length === 0) return;

    setBusyUrl("__bulk__");
    setError(null);
    setMessage(null);

    let extractedCount = 0;
    let failedCount = 0;

    for (const item of selectedExtractableItems) {
      try {
        await manualUrlIngestion(item.website as string, item.id);
        extractedCount += 1;
      } catch {
        failedCount += 1;
      }
    }

    const skippedCount = selectedItems.length - selectedExtractableItems.length;
    setBusyUrl(null);
    setSelectedIds([]);
    setMessage(
      [
        `Sent ${extractedCount} record(s) to Review Queue.`,
        failedCount ? `${failedCount} failed.` : "",
        skippedCount ? `${skippedCount} skipped because no website was available.` : "",
      ]
        .filter(Boolean)
        .join(" ")
    );
  };

  const bulkDeleteSelected = async () => {
    if (selectedIds.length === 0) return;
    const reason = window.prompt(`Delete ${selectedIds.length} selected investor record(s)?`, "Deleted from Data Quality bulk cleanup.");
    if (reason === null) return;

    setBusyUrl("__delete__");
    try {
      const result = await bulkDeleteQualityRecords(selectedIds, reason);
      setMessage(`Deleted ${result.deleted} investor record(s).`);
      await loadData();
    } catch (error: any) {
      setMessage(error.message || "Failed to bulk delete selected records.");
    } finally {
      setBusyUrl(null);
    }
  };

  const rebuildBacklog = async () => {
    setRebuilding(true);
    setMessage(null);
    try {
      const summary = await rebuildEnrichmentBacklog();
      setMessage(`Backlog rebuilt: ${summary.selected_records || 0} selected record(s).`);
      await loadData();
    } catch (error: any) {
      setMessage(error.message || "Failed to rebuild enrichment backlog.");
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Coverage and completeness</p>
          <h2 className="mt-1 flex items-center gap-2 text-3xl font-extrabold text-foreground glow-accent">
            <BarChart3 className="h-7 w-7 text-violet-600" />
            Data Quality
          </h2>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-xs font-bold text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-violet-600" />
        </div>
      ) : error ? (
        <Card className="glass-card border-border p-8 text-sm text-red-600">{error}</Card>
      ) : data ? (
        <>
          {message && (
            <Card className="glass-card border-border p-4 text-sm text-emerald-600">
              {message}
            </Card>
          )}

          <Card className="glass-card border-border p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
                  <Link2 className="h-4 w-4 text-violet-600" />
                  Enrich a Record Without Leaving This Page
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Paste an alternate source URL, or use the Extract button beside a low-coverage record.
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row lg:min-w-[520px]">
                <input
                  value={manualUrl}
                  onChange={(event) => setManualUrl(event.target.value)}
                  placeholder="https://example.vc/team"
                  className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
                />
                <button
                  onClick={() => extractToReview()}
                  disabled={Boolean(busyUrl) || manualUrl.trim().length < 8}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50"
                >
                  {busyUrl === manualUrl.trim() ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  Extract
                </button>
              </div>
            </div>
          </Card>

          <div className="grid gap-4 md:grid-cols-4">
            <Card className="glass-card border-border p-5">
              <p className="text-xs font-bold uppercase text-muted-foreground">Total Investors</p>
              <p className="mt-2 text-3xl font-extrabold">{data.total}</p>
            </Card>
            {Object.entries(data.status_counts).map(([status, value]) => (
              <Card key={status} className="glass-card border-border p-5">
                <p className="text-xs font-bold uppercase text-muted-foreground">{status}</p>
                <p className="mt-2 text-3xl font-extrabold">{value}</p>
              </Card>
            ))}
          </div>

          <Card className="glass-card border-border p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="text-sm font-bold text-foreground">Enrichment Operations</h3>
                <p className="text-xs text-muted-foreground">Rebuild audit/backlog and inspect recent enrichment batches.</p>
              </div>
              <button
                onClick={rebuildBacklog}
                disabled={rebuilding}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50"
              >
                {rebuilding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                Rebuild Backlog
              </button>
            </div>
            {history.length > 0 && (
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {history.slice(0, 4).map((run) => (
                  <div key={run.file} className="rounded-xl border border-border bg-muted/30 p-3">
                    <p className="text-xs font-bold text-foreground">{run.file}</p>
                    <p className="text-[11px] text-muted-foreground">{formatDate(run.modified_at)}</p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      processed {run.summary?.processed ?? 0} · queued {run.summary?.queued_review ?? 0} · failed {(run.summary?.queued_no_content_review ?? 0) + (run.summary?.queued_validation_failed_review ?? 0)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="glass-card border-border p-6">
            <CardHeader className="p-0 pb-4">
              <h3 className="text-base font-bold text-foreground">Missing Field Coverage</h3>
              <p className="text-xs text-muted-foreground">How many investor records are missing each field</p>
            </CardHeader>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.missing_counts} layout="vertical" margin={{ left: 20, right: 20, top: 10, bottom: 10 }}>
                  <XAxis type="number" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                  <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={10} width={145} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                    {data.missing_counts.map((entry, index) => (
                      <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="glass-card border-border overflow-hidden">
            <CardHeader className="border-b border-border px-6 py-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h3 className="text-base font-bold text-foreground">Lowest Coverage Records</h3>
                  <p className="text-xs text-muted-foreground">First 100 records sorted by missing data</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{selectedIds.length} selected</Badge>
                  <button
                    onClick={toggleSelectAllVisible}
                    disabled={Boolean(busyUrl)}
                    className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold text-muted-foreground transition hover:text-foreground disabled:opacity-50"
                  >
                    {allVisibleSelected ? "Clear Selection" : "Select All Visible"}
                  </button>
                  {selectedIds.length > 0 && (
                    <>
                      <button
                        onClick={bulkExtractToReview}
                        disabled={Boolean(busyUrl) || selectedExtractableItems.length === 0}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2 text-xs font-bold text-white hover:bg-violet-500 disabled:opacity-50"
                      >
                        {busyUrl === "__bulk__" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                        Extract Selected ({selectedExtractableItems.length})
                      </button>
                      <button
                        onClick={bulkDeleteSelected}
                        disabled={Boolean(busyUrl)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-500 disabled:opacity-50"
                      >
                        Delete Selected ({selectedIds.length})
                      </button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead className="border-b border-border bg-muted/50 text-xs font-semibold text-muted-foreground">
                  <tr>
                    <th className="px-6 py-3">Select</th>
                    <th className="px-6 py-3">Firm</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Score</th>
                    <th className="px-6 py-3">Missing Fields</th>
                    <th className="px-6 py-3">Updated</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.items.map((item) => (
                    <tr key={item.id} className="hover:bg-muted/40">
                      <td className="px-6 py-4">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.id)}
                          onChange={(event) =>
                            setSelectedIds((current) =>
                              event.target.checked
                                ? [...current, item.id]
                                : current.filter((id) => id !== item.id)
                            )
                          }
                          className="h-4 w-4 rounded border-border"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => setSelectedInvestorId(item.id)}
                          className="text-left font-semibold text-foreground hover:text-violet-600 hover:underline"
                        >
                          {item.firm}
                        </button>
                        {item.website && (
                          <a
                            href={item.website}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 block truncate text-xs text-muted-foreground hover:text-violet-600"
                          >
                            {item.website}
                          </a>
                        )}
                      </td>
                      <td className="px-6 py-4"><Badge>{item.status}</Badge></td>
                      <td className="px-6 py-4 text-muted-foreground">{item.score}/{item.max_score}</td>
                      <td className="px-6 py-4 text-xs text-muted-foreground">{item.missing_fields.join(", ") || "None"}</td>
                      <td className="px-6 py-4 text-xs text-muted-foreground">{formatDate(item.updated_at)}</td>
                      <td className="px-6 py-4">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => setSelectedInvestorId(item.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-bold text-muted-foreground hover:text-foreground"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            Profile
                          </button>
                          <button
                            onClick={() => extractToReview(item.website, item.id)}
                            disabled={!item.website || Boolean(busyUrl)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2 text-xs font-bold text-white hover:bg-violet-500 disabled:opacity-50"
                          >
                            {busyUrl === item.website ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                            Extract
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <InvestorDetailModal
            investorId={selectedInvestorId}
            isOpen={selectedInvestorId !== null}
            onClose={() => {
              setSelectedInvestorId(null);
              loadData();
            }}
          />
        </>
      ) : null}
    </div>
  );
}
