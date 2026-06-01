"use client";

import { useEffect, useMemo, useState } from "react";
import { approveReviewItem, bulkRejectReviewItems, editReviewItem, getReviewQueue, manualUrlIngestion, rejectReviewItem, ReviewQueueItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { CheckCircle2, ClipboardCheck, Link2, Loader2, Play, RefreshCw, Save, XCircle } from "lucide-react";

const statusOptions = ["pending", "approved", "rejected", "all"];

function prettyPayload(payload: Record<string, any>) {
  return JSON.stringify(payload || {}, null, 2);
}

function hasInsertableEvidence(payload: Record<string, any>) {
  if (!payload || payload.blocked || payload.extraction_failed || payload.extraction_error) {
    return false;
  }

  const firm = String(payload.firm || "").trim();
  const wordCount = firm.match(/[A-Za-z0-9]+/g)?.length || 0;
  const punctuationCount = firm.match(/[^A-Za-z0-9\s&.-]/g)?.length || 0;

  if (!firm || wordCount > 10 || punctuationCount > 2) {
    return false;
  }

  return Boolean(payload.website || payload.source_url);
}

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("");
  const [issue, setIssue] = useState("");
  const [maxConfidence, setMaxConfidence] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [manualUrl, setManualUrl] = useState("");
  const [ingestingUrl, setIngestingUrl] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [payloadDrafts, setPayloadDrafts] = useState<Record<number, string>>({});
  const [reasonDrafts, setReasonDrafts] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  const pendingCount = useMemo(
    () => items.filter((item) => item.status === "pending").length,
    [items]
  );
  const pendingItems = useMemo(
    () => items.filter((item) => item.status === "pending"),
    [items]
  );
  const selectedItems = useMemo(
    () => items.filter((item) => selectedIds.includes(item.id)),
    [items, selectedIds]
  );
  const allVisiblePendingSelected = pendingItems.length > 0 && pendingItems.every((item) => selectedIds.includes(item.id));

  const loadItems = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const result = await getReviewQueue({
        status,
        q,
        domain,
        issue,
        max_confidence: maxConfidence ? Number(maxConfidence) : undefined,
        limit: 100,
      });
      setItems(result.items);
      setSelectedIds([]);
      setPayloadDrafts(
        Object.fromEntries(
          result.items.map((item) => [item.id, prettyPayload(item.extracted_payload)])
        )
      );
      setReasonDrafts(
        Object.fromEntries(
          result.items.map((item) => [item.id, item.human_reason || item.reviewer_notes || ""])
        )
      );
    } catch (error: any) {
      setMessage(error.message || "Failed to load review queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, [status]);

  const applyFilters = () => {
    loadItems();
  };

  const parsePayload = (item: ReviewQueueItem) => {
    try {
      return JSON.parse(payloadDrafts[item.id] || "{}");
    } catch {
      throw new Error("Extracted JSON is invalid. Fix the JSON before saving or approving.");
    }
  };

  const canApprove = (item: ReviewQueueItem) => {
    try {
      return hasInsertableEvidence(parsePayload(item));
    } catch {
      return false;
    }
  };
  const selectedApprovableItems = selectedItems.filter((item) => canApprove(item));

  const toggleSelectAllVisible = () => {
    if (allVisiblePendingSelected) {
      setSelectedIds([]);
      return;
    }

    setSelectedIds(pendingItems.map((item) => item.id));
  };

  const handleSave = async (item: ReviewQueueItem) => {
    setBusyId(item.id);
    setMessage(null);

    try {
      const extractedPayload = parsePayload(item);
      await editReviewItem(item.id, {
        extracted_payload: extractedPayload,
        reviewer_notes: reasonDrafts[item.id] || "",
      });
      setMessage("Review item saved.");
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to save review item.");
    } finally {
      setBusyId(null);
    }
  };

  const handleApprove = async (item: ReviewQueueItem) => {
    setBusyId(item.id);
    setMessage(null);

    try {
      const extractedPayload = parsePayload(item);
      await approveReviewItem(item.id, {
        extracted_payload: extractedPayload,
        human_reason: reasonDrafts[item.id] || "Approved by human review.",
      });
      setMessage("Approved and inserted/updated investor data.");
      setItems((current) => current.filter((row) => row.id !== item.id));
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to approve review item.");
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (item: ReviewQueueItem) => {
    setBusyId(item.id);
    setMessage(null);

    try {
      await rejectReviewItem(item.id, {
        human_reason: reasonDrafts[item.id] || "Rejected by human review.",
      });
      setMessage("Rejected and saved as a learning example.");
      setItems((current) => current.filter((row) => row.id !== item.id));
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to reject review item.");
    } finally {
      setBusyId(null);
    }
  };

  const handleBulkReject = async () => {
    if (selectedIds.length === 0) return;

    const reason = window.prompt(
      `Reject ${selectedIds.length} selected review item(s)?`,
      "Rejected in bulk human review."
    );

    if (reason === null) return;

    setBusyId(-1);
    setMessage(null);

    try {
      const result = await bulkRejectReviewItems(selectedIds, {
        human_reason: reason,
      });
      setMessage(`Bulk rejected ${result.updated} review item(s).`);
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to bulk reject review items.");
    } finally {
      setBusyId(null);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedApprovableItems.length === 0) return;

    const skippedCount = selectedItems.length - selectedApprovableItems.length;

    setBusyId(-2);
    setMessage(null);

    try {
      let approvedCount = 0;

      for (const item of selectedApprovableItems) {
        const extractedPayload = parsePayload(item);
        await approveReviewItem(item.id, {
          extracted_payload: extractedPayload,
          human_reason: reasonDrafts[item.id] || "Approved in bulk human review.",
        });
        approvedCount += 1;
      }

      setMessage(
        skippedCount > 0
          ? `Approved ${approvedCount} selected item(s). Skipped ${skippedCount} item(s) that cannot be approved yet.`
          : `Approved ${approvedCount} selected item(s).`
      );
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to bulk approve selected review items.");
    } finally {
      setBusyId(null);
    }
  };

  const handleManualUrlIngestion = async () => {
    if (manualUrl.trim().length < 8) return;

    setIngestingUrl(true);
    setMessage(null);

    try {
      const item = await manualUrlIngestion(manualUrl.trim());
      setStatus("pending");
      setMessage(
        `Extracted "${item.firm_name || "unknown firm"}" and added it to this review queue. Approve to update investors, reject to remove it from pending.`
      );
      setManualUrl("");
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to extract URL.");
    } finally {
      setIngestingUrl(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Human feedback loop
          </p>
          <h2 className="mt-1 flex items-center gap-2 text-3xl font-extrabold text-foreground glow-accent">
            <ClipboardCheck className="h-7 w-7 text-violet-600" />
            Review Queue
          </h2>
        </div>
        <button
          onClick={loadItems}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-xs font-bold text-muted-foreground transition hover:text-foreground"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      <Card className="glass-card border-border p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-bold text-foreground">Items Needing Human Judgment</h3>
            <p className="text-xs text-muted-foreground">
              Approvals update the investor database. Rejections are saved as examples for future AI classification.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge>{pendingCount} pending shown</Badge>
            {pendingItems.length > 0 && (
              <button
                onClick={toggleSelectAllVisible}
                disabled={busyId !== null}
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold text-muted-foreground transition hover:text-foreground disabled:opacity-50"
              >
                {allVisiblePendingSelected ? "Clear Selection" : "Select All Visible"}
              </button>
            )}
            {selectedIds.length > 0 && (
              <>
                <Badge>{selectedIds.length} selected</Badge>
                <button
                  onClick={handleBulkApprove}
                  disabled={busyId !== null || selectedApprovableItems.length === 0}
                  className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
                  title={
                    selectedApprovableItems.length > 0
                      ? "Approve selected approve-ready items"
                      : "No selected items are approve-ready"
                  }
                >
                  Approve Selected ({selectedApprovableItems.length})
                </button>
                <button
                  onClick={handleBulkReject}
                  disabled={busyId !== null}
                  className="rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-500 disabled:opacity-50"
                >
                  Reject Selected ({selectedIds.length})
                </button>
              </>
            )}
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              className={cn(fieldInputClassName, "w-36 px-3 py-2 text-xs")}
            >
              {statusOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <input
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Search queue"
            className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
          />
          <input
            value={domain}
            onChange={(event) => setDomain(event.target.value)}
            placeholder="Filter domain"
            className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
          />
          <input
            value={maxConfidence}
            onChange={(event) => setMaxConfidence(event.target.value)}
            placeholder="Max confidence, e.g. 0.65"
            className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
          />
          <select
            value={issue}
            onChange={(event) => setIssue(event.target.value)}
            className={cn(fieldInputClassName, "px-3 py-2 text-xs")}
          >
            <option value="">All review types</option>
            <option value="blocked">Blocked / failed</option>
            <option value="enrichment">Enrichment</option>
            <option value="manual">Manual extracts</option>
            <option value="non_investor">Likely non-investor</option>
          </select>
          <button
            onClick={applyFilters}
            className="rounded-xl border border-border bg-muted px-4 py-2 text-xs font-bold text-muted-foreground hover:text-foreground md:col-span-4"
          >
            Apply Filters
          </button>
        </div>
      </Card>

      <Card className="glass-card border-border p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
              <Link2 className="h-4 w-4 text-violet-600" />
              Extract URL to Review
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Paste a firm/team/portfolio URL here, review the parsed JSON below, then approve to update investors.
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
              onClick={handleManualUrlIngestion}
              disabled={ingestingUrl || manualUrl.trim().length < 8}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-50"
            >
              {ingestingUrl ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {ingestingUrl ? "Extracting..." : "Extract"}
            </button>
          </div>
        </div>
      </Card>

      {message && (
        <div className="rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          {message}
        </div>
      )}

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-violet-600" />
        </div>
      ) : items.length === 0 ? (
        <Card className="glass-card border-border p-10 text-center text-sm text-muted-foreground">
          No review items found for this status.
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const itemCanApprove = canApprove(item);

            return (
            <Card key={item.id} className="glass-card border-border overflow-hidden">
              <CardHeader className="border-b border-border px-5 py-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {item.status === "pending" && (
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
                      )}
                      <h3 className="text-base font-bold text-foreground">
                        {item.firm_name || "Unknown firm"}
                      </h3>
                      <Badge>{item.status}</Badge>
                      {typeof item.ai_confidence === "number" && (
                        <Badge>
                          AI {Math.round(item.ai_confidence * 100)}%
                        </Badge>
                      )}
                      {item.extracted_payload?._target_investor_id && (
                        <Badge>
                          Reject deletes record #{item.extracted_payload._target_investor_id}
                        </Badge>
                      )}
                      {(item.extracted_payload?.blocked || item.extracted_payload?.extraction_failed) && (
                        <Badge>
                          Blocked / extraction failed
                        </Badge>
                      )}
                    </div>
                    <a
                      href={item.url || "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 block truncate text-xs text-violet-600 hover:underline"
                    >
                      {item.url || "No URL"}
                    </a>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Created {formatDate(item.created_at)} · {item.ai_decision || "needs_review"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleSave(item)}
                      disabled={busyId === item.id}
                      className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-bold text-muted-foreground transition hover:text-foreground disabled:opacity-50"
                    >
                      <Save className="h-3.5 w-3.5" />
                      Save
                    </button>
                    <button
                      onClick={() => handleApprove(item)}
                      disabled={
                        busyId === item.id ||
                        item.status !== "pending" ||
                        !itemCanApprove
                      }
                      className={cn(
                        "flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold transition",
                        itemCanApprove && item.status === "pending"
                          ? "bg-emerald-600 text-white hover:bg-emerald-500"
                          : "cursor-not-allowed border border-border bg-muted text-muted-foreground"
                      )}
                      title={
                        itemCanApprove
                          ? "Approve and update investor database"
                          : "This item has no insertable investor fields. Reject it or edit the JSON first."
                      }
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {itemCanApprove ? "Approve" : "Cannot approve"}
                    </button>
                    <button
                      onClick={() => handleReject(item)}
                      disabled={busyId === item.id || item.status !== "pending"}
                      className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-red-500 disabled:opacity-50"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 p-5 lg:grid-cols-[1fr_1.2fr]">
                <div className="space-y-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                      AI Reason
                    </p>
                    <p className="mt-1 rounded-xl bg-muted/40 p-3 text-xs text-muted-foreground">
                      {item.extracted_payload?._target_investor_id
                        ? `${item.ai_reason || "No AI reason recorded."} Rejecting this Data Quality re-extraction will delete the original investor record.`
                        : item.ai_reason || "No AI reason recorded."}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                      Source Text
                    </p>
                    <div className="mt-1 max-h-48 overflow-auto rounded-xl bg-muted/40 p-3 text-xs text-muted-foreground">
                      {item.source_text || "No source text stored."}
                    </div>
                  </div>
                  <label className="block space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                      Human Reason / Notes
                    </span>
                    <textarea
                      value={reasonDrafts[item.id] || ""}
                      onChange={(event) =>
                        setReasonDrafts((current) => ({
                          ...current,
                          [item.id]: event.target.value,
                        }))
                      }
                      placeholder="Why approve/reject? This becomes future AI feedback."
                      className={cn(fieldInputClassName, "min-h-24 px-3 py-2 text-xs")}
                    />
                  </label>
                </div>

                <label className="block space-y-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                    Extracted Investor JSON
                  </span>
                  <textarea
                    value={payloadDrafts[item.id] || "{}"}
                    onChange={(event) =>
                      setPayloadDrafts((current) => ({
                        ...current,
                        [item.id]: event.target.value,
                      }))
                    }
                    className="min-h-[360px] w-full rounded-xl border border-border bg-muted/40 px-3 py-2 font-mono text-xs text-foreground outline-none focus:border-violet-500"
                  />
                </label>
              </CardContent>
            </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
