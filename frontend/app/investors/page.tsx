"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getInvestors, Investor } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import {
  Search, SlidersHorizontal, ChevronLeft, ChevronRight,
  Loader2, Globe, Users, Building2
} from "lucide-react";
import { InvestorDetailModal } from "@/components/investor-detail-modal";
import { GEOGRAPHIES } from "@/lib/countries";

const SECTORS = ["Artificial Intelligence", "B2B", "SaaS", "Voice AI"];
const STAGES = ["Pre-Seed", "Seed", "Series A", "Series B", "Growth Stage"];

export default function InvestorsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [stage, setStage] = useState("");
  const [geography, setGeography] = useState("");

  const [investors, setInvestors] = useState<Investor[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const limit = 15;

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const offset = (page - 1) * limit;
        const res = await getInvestors({ q, sector, stage, geography, limit, offset });
        setInvestors(res.items);
        setTotal(res.total);
      } catch (err) {
        console.error("Failed to load investors:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [q, sector, stage, geography, page]);

  const totalPages = Math.ceil(total / limit) || 1;

  const handleFilterChange = (setter: (val: string) => void, val: string) => {
    setter(val);
    setPage(1);
  };

  const goToPartners = (investor: Investor) => {
    router.push(`/partners?investor_id=${investor.id}&firm=${encodeURIComponent(investor.firm_name)}`);
  };

  const goToPortfolio = (investor: Investor) => {
    router.push(`/portfolio-companies?investor_id=${investor.id}&firm=${encodeURIComponent(investor.firm_name)}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Database Search</p>
        <h2 className="mt-1 text-3xl font-extrabold text-foreground glow-accent">Investor Registry</h2>
      </div>

      {/* Filters */}
      <Card className="glass-card border-border p-6 space-y-4">
        <div className="flex items-center gap-2 border-b border-border pb-3">
          <SlidersHorizontal className="h-4 w-4 text-violet-600" />
          <h3 className="text-sm font-semibold text-foreground">Search & Filter Controls</h3>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search className="absolute top-3 left-3 h-4 w-4 text-muted-foreground" />
            <input type="text" placeholder="Search firm name..."
              value={q} onChange={(e) => handleFilterChange(setQ, e.target.value)}
              className={cn(fieldInputClassName, "pl-10 pr-4 py-2.5")} />
          </div>
          <select value={sector} onChange={(e) => handleFilterChange(setSector, e.target.value)} className={cn(fieldInputClassName, "px-3 py-2.5")}>
            <option value="">All Sectors</option>
            {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={stage} onChange={(e) => handleFilterChange(setStage, e.target.value)} className={cn(fieldInputClassName, "px-3 py-2.5")}>
            <option value="">All Stages</option>
            {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={geography} onChange={(e) => handleFilterChange(setGeography, e.target.value)} className={cn(fieldInputClassName, "px-3 py-2.5")}>
            <option value="">All Geographies</option>
            {GEOGRAPHIES.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
      </Card>

      {/* Table */}
      <Card className="glass-card border-border overflow-hidden">
        <CardHeader className="px-6 py-5 border-b border-border flex flex-row items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-foreground">Investor Records</h3>
            <p className="text-xs text-muted-foreground">Showing {investors.length} of {total} firms — click count badges to browse their partners/portfolio</p>
          </div>
          {loading && <Loader2 className="h-5 w-5 animate-spin text-violet-600" />}
        </CardHeader>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] text-left text-sm">
            <thead className="border-b border-border text-muted-foreground text-xs font-semibold bg-muted/50">
              <tr>
                <th className="px-4 py-3.5 w-14 text-center">ID</th>
                <th className="px-4 py-3.5">Firm Name</th>
                <th className="px-4 py-3.5">Website</th>
                <th className="px-4 py-3.5">Focus Sectors</th>
                <th className="px-4 py-3.5">Investment Stage</th>
                <th className="px-4 py-3.5">Geography</th>
                <th className="px-4 py-3.5 text-center">Partners</th>
                <th className="px-4 py-3.5 text-center">Portfolio</th>
                <th className="px-4 py-3.5">Created At</th>
                <th className="px-4 py-3.5">Updated At</th>
                <th className="px-4 py-3.5 text-right">Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!loading && investors.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-6 py-12 text-center text-muted-foreground">
                    No matching investor records found.
                  </td>
                </tr>
              ) : (
                investors.map((investor) => (
                  <tr key={investor.id} className="hover:bg-muted/50 transition duration-150 align-top">
                    {/* id */}
                    <td className="px-4 py-4 text-center text-xs text-muted-foreground font-mono">{investor.id}</td>

                    {/* firm_name */}
                    <td className="px-4 py-4">
                      <p className="font-semibold text-foreground whitespace-nowrap">{investor.firm_name}</p>
                    </td>

                    {/* website */}
                    <td className="px-4 py-4">
                      {investor.website ? (
                        <a href={investor.website} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-violet-600 hover:underline transition whitespace-nowrap">
                          <Globe className="h-3.5 w-3.5 shrink-0" />
                          <span className="max-w-[130px] truncate">{investor.website.replace(/^https?:\/\//, "")}</span>
                        </a>
                      ) : <span className="text-xs text-muted-foreground italic">—</span>}
                    </td>

                    {/* focus_sectors */}
                    <td className="px-4 py-4 max-w-[160px]">
                      <div className="flex flex-wrap gap-1">
                        {investor.focus_sectors.slice(0, 2).map((s) => (
                          <Badge key={s} className="bg-violet-100 text-violet-800 border border-violet-200 px-2 py-0.5 text-[10px]">{s}</Badge>
                        ))}
                        {investor.focus_sectors.length > 2 && (
                          <span className="text-[10px] font-semibold text-muted-foreground mt-1">+{investor.focus_sectors.length - 2}</span>
                        )}
                        {investor.focus_sectors.length === 0 && <span className="text-xs text-muted-foreground italic">—</span>}
                      </div>
                    </td>

                    {/* investment_stage */}
                    <td className="px-4 py-4 max-w-[150px]">
                      <div className="flex flex-wrap gap-1">
                        {investor.investment_stage.slice(0, 2).map((stg) => (
                          <Badge key={stg} className="bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-0.5 text-[10px]">{stg}</Badge>
                        ))}
                        {investor.investment_stage.length > 2 && (
                          <span className="text-[10px] font-semibold text-muted-foreground mt-1">+{investor.investment_stage.length - 2}</span>
                        )}
                        {investor.investment_stage.length === 0 && <span className="text-xs text-muted-foreground italic">—</span>}
                      </div>
                    </td>

                    {/* geography */}
                    <td className="px-4 py-4 text-xs text-muted-foreground max-w-[200px] truncate whitespace-nowrap" title={investor.geography.join(", ")}>
                      {investor.geography.join(", ") || "—"}
                    </td>

                    {/* partners count — clickable */}
                    <td className="px-4 py-4 text-center">
                      <button
                        onClick={() => goToPartners(investor)}
                        title={`View all ${investor.partner_count} partners of ${investor.firm_name}`}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition",
                          investor.partner_count > 0
                            ? "bg-violet-100 text-violet-800 border border-violet-200 hover:bg-violet-200 cursor-pointer"
                            : "bg-muted text-muted-foreground border border-border cursor-default"
                        )}
                      >
                        <Users className="h-3 w-3" />
                        {investor.partner_count}
                      </button>
                    </td>

                    {/* portfolio count — clickable */}
                    <td className="px-4 py-4 text-center">
                      <button
                        onClick={() => goToPortfolio(investor)}
                        title={`View all ${investor.portfolio_count} portfolio companies of ${investor.firm_name}`}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition",
                          investor.portfolio_count > 0
                            ? "bg-amber-100 text-amber-800 border border-amber-200 hover:bg-amber-200 cursor-pointer"
                            : "bg-muted text-muted-foreground border border-border cursor-default"
                        )}
                      >
                        <Building2 className="h-3 w-3" />
                        {investor.portfolio_count}
                      </button>
                    </td>

                    {/* created_at */}
                    <td className="px-4 py-4 text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(investor.created_at)}
                    </td>

                    {/* updated_at */}
                    <td className="px-4 py-4 text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(investor.updated_at)}
                    </td>

                    {/* profile */}
                    <td className="px-4 py-4 text-right">
                      <button
                        onClick={() => { setSelectedId(investor.id); setModalOpen(true); }}
                        className="rounded-lg bg-violet-600/10 px-3.5 py-1.5 text-xs font-bold text-violet-700 hover:bg-violet-600/20 transition"
                      >
                        Profile
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border px-6 py-4">
            <span className="text-xs text-muted-foreground">
              Page <span className="font-semibold text-foreground">{page}</span> of{" "}
              <span className="font-semibold text-foreground">{totalPages}</span>
            </span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={page === 1}
                className="rounded-xl border border-input bg-background p-2 text-muted-foreground hover:text-foreground disabled:opacity-40 transition">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button onClick={() => setPage((p) => Math.min(p + 1, totalPages))} disabled={page === totalPages}
                className="rounded-xl border border-input bg-background p-2 text-muted-foreground hover:text-foreground disabled:opacity-40 transition">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </Card>

      <InvestorDetailModal
        investorId={selectedId}
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); setSelectedId(null); }}
      />
    </div>
  );
}
