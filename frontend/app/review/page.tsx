"use client";

import { useEffect, useMemo, useState } from "react";
import { approveReviewItem, editReviewItem, getReviewQueue, rejectReviewItem, ReviewQueueItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { CheckCircle2, ClipboardCheck, Loader2, RefreshCw, Save, XCircle } from "lucide-react";

const statusOptions = ["pending", "approved", "rejected", "all"];

function prettyPayload(payload: Record<string, any>) {
  return JSON.stringify(payload || {}, null, 2);
}

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [status, setStatus] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [payloadDrafts, setPayloadDrafts] = useState<Record<number, string>>({});
  const [reasonDrafts, setReasonDrafts] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  const pendingCount = useMemo(
    () => items.filter((item) => item.status === "pending").length,
    [items]
  );

  const loadItems = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const result = await getReviewQueue({ status, limit: 100 });
      setItems(result.items);
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

  const parsePayload = (item: ReviewQueueItem) => {
    try {
      return JSON.parse(payloadDrafts[item.id] || "{}");
    } catch {
      throw new Error("Extracted JSON is invalid. Fix the JSON before saving or approving.");
    }
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
      await loadItems();
    } catch (error: any) {
      setMessage(error.message || "Failed to reject review item.");
    } finally {
      setBusyId(null);
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
          <div className="flex items-center gap-3">
            <Badge>{pendingCount} pending shown</Badge>
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
          {items.map((item) => (
            <Card key={item.id} className="glass-card border-border overflow-hidden">
              <CardHeader className="border-b border-border px-5 py-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-bold text-foreground">
                        {item.firm_name || "Unknown firm"}
                      </h3>
                      <Badge>{item.status}</Badge>
                      {typeof item.ai_confidence === "number" && (
                        <Badge>
                          AI {Math.round(item.ai_confidence * 100)}%
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
                      disabled={busyId === item.id || item.status !== "pending"}
                      className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-emerald-500 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Approve
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
                      {item.ai_reason || "No AI reason recorded."}
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
          ))}
        </div>
      )}
    </div>
  );
}
