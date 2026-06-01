"use client";

import { useEffect, useState } from "react";
import { Ban, Loader2, RefreshCw, Search, Unlock } from "lucide-react";
import { BlocklistItem, getBlocklist, unblockHost } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export default function BlocklistPage() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<BlocklistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyHost, setBusyHost] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const result = await getBlocklist({ q });
      setItems(result.items);
    } catch (error: any) {
      setMessage(error.message || "Failed to load blocklist.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUnblock = async (host: string) => {
    if (!window.confirm(`Unblock ${host}? Future pipeline runs may discover this site again.`)) return;

    setBusyHost(host);
    try {
      const result = await unblockHost(host);
      setMessage(`Unblocked ${result.host}; updated ${result.updated} blocked URL record(s).`);
      await loadData();
    } catch (error: any) {
      setMessage(error.message || "Failed to unblock host.");
    } finally {
      setBusyHost(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Permanent exclusions</p>
          <h2 className="mt-1 flex items-center gap-2 text-3xl font-extrabold text-foreground glow-accent">
            <Ban className="h-7 w-7 text-violet-600" />
            Blocklist Manager
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

      <Card className="glass-card border-border p-5">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <input
            value={q}
            onChange={(event) => setQ(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && loadData()}
            placeholder="Search blocked domain"
            className={cn(fieldInputClassName, "px-3 py-2 pl-10 text-xs")}
          />
        </div>
      </Card>

      {message && <Card className="glass-card border-border p-4 text-sm text-muted-foreground">{message}</Card>}

      <Card className="glass-card border-border overflow-hidden">
        <CardHeader className="border-b border-border px-6 py-5">
          <h3 className="text-base font-bold text-foreground">Blocked Domains</h3>
          <p className="text-xs text-muted-foreground">Rejected sites are skipped by future pipeline runs.</p>
        </CardHeader>
        {loading ? (
          <div className="flex h-56 items-center justify-center">
            <Loader2 className="h-7 w-7 animate-spin text-violet-600" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-border bg-muted/50 text-xs font-semibold text-muted-foreground">
                <tr>
                  <th className="px-6 py-3">Domain</th>
                  <th className="px-6 py-3">Blocked URLs</th>
                  <th className="px-6 py-3">Latest Attempt</th>
                  <th className="px-6 py-3">Sample URLs</th>
                  <th className="px-6 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <tr key={item.host} className="hover:bg-muted/40">
                    <td className="px-6 py-4 font-semibold text-foreground">{item.host}</td>
                    <td className="px-6 py-4"><Badge>{item.count}</Badge></td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">{formatDate(item.latest_attempt)}</td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {item.sample_urls.slice(0, 2).map((url) => (
                        <div key={url} className="max-w-[360px] truncate">{url}</div>
                      ))}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleUnblock(item.host)}
                        disabled={busyHost === item.host}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-50"
                      >
                        {busyHost === item.host ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unlock className="h-3.5 w-3.5" />}
                        Unblock
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
