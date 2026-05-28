"use client";

import { useEffect, useState } from "react";
import { getPortfolioCompanies, PortfolioCompanyListItem } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName } from "@/lib/utils";
import { Search, ChevronLeft, ChevronRight, Loader2, BriefcaseBusiness, Building2, Layers3 } from "lucide-react";
import { InvestorDetailModal } from "@/components/investor-detail-modal";
import { Badge } from "@/components/ui/badge";

export default function PortfolioCompaniesPage() {
  const [q, setQ] = useState("");
  const [companies, setCompanies] = useState<PortfolioCompanyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [selectedInvestorId, setSelectedInvestorId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const limit = 15;

  useEffect(() => {
    async function loadData() {
      setLoading(true);

      try {
        const offset = (page - 1) * limit;
        const res = await getPortfolioCompanies({
          q,
          limit,
          offset,
        });
        setCompanies(res.items);
        setTotal(res.total);
      } catch (err) {
        console.error("Failed to load portfolio companies:", err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [q, page]);

  const totalPages = Math.ceil(total / limit) || 1;

  const handleSearchChange = (value: string) => {
    setQ(value);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Portfolio Intelligence</p>
        <h2 className="mt-1 text-3xl font-extrabold text-foreground glow-accent">Portfolio Companies</h2>
      </div>

      <Card className="glass-card border-border p-6 flex flex-col sm:flex-row items-center gap-4 justify-between">
        <div className="relative w-full max-w-md">
          <Search className="absolute top-3 left-3 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search company, sector, or backing firm..."
            value={q}
            onChange={(e) => handleSearchChange(e.target.value)}
            className={cn(fieldInputClassName, "pl-10 pr-4 py-2.5")}
          />
        </div>
        <p className="text-xs text-muted-foreground shrink-0">
          Browse portfolio companies and jump straight to the backing investor profile.
        </p>
      </Card>

      <Card className="glass-card border-border overflow-hidden">
        <CardHeader className="px-6 py-5 border-b border-border flex flex-row items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-foreground">Portfolio Directory</h3>
            <p className="text-xs text-muted-foreground">Showing {companies.length} of {total} portfolio companies</p>
          </div>
          {loading && <Loader2 className="h-5 w-5 animate-spin text-violet-400" />}
        </CardHeader>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left text-sm">
            <thead className="border-b border-border text-muted-foreground text-xs font-semibold bg-muted/50">
              <tr>
                <th className="px-6 py-3.5">Company</th>
                <th className="px-6 py-3.5">Sector</th>
                <th className="px-6 py-3.5">Backed By</th>
                <th className="px-6 py-3.5">Investor Website</th>
                <th className="px-6 py-3.5 text-right">Investor Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {!loading && companies.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">
                    No matching portfolio companies found.
                  </td>
                </tr>
              ) : (
                companies.map((company) => (
                  <tr key={company.id} className="hover:bg-muted/50 transition duration-150 align-middle">
                    <td className="px-6 py-4">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-violet-500/15 bg-violet-500/10 text-violet-400">
                          <BriefcaseBusiness className="h-4.5 w-4.5" />
                        </div>
                        <div>
                          <p className="font-semibold text-foreground">{company.company_name}</p>
                          <p className="mt-1 text-xs text-muted-foreground">Portfolio record #{company.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {company.sector ? (
                        <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 px-2.5 py-1 text-[10px] font-semibold">
                          <span className="flex items-center gap-1">
                            <Layers3 className="h-3.5 w-3.5" />
                            {company.sector}
                          </span>
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">Not specified</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted/60 text-muted-foreground">
                          <Building2 className="h-4 w-4" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{company.investor_firm || "Unknown investor"}</p>
                          <p className="text-[11px] text-muted-foreground">Investor ID {company.investor_id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {company.investor_website ? (
                        <a
                          href={company.investor_website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center rounded-lg border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:text-foreground hover:bg-muted/60"
                        >
                          Visit site
                        </a>
                      ) : (
                        <span className="text-xs text-muted-foreground">Unavailable</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => {
                          setSelectedInvestorId(company.investor_id);
                          setModalOpen(true);
                        }}
                        className="rounded-lg bg-violet-600/10 px-3.5 py-1.5 text-xs font-bold text-violet-400 hover:bg-violet-600/20 hover:text-violet-300 transition"
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
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page === 1}
                className="rounded-xl border border-input bg-background p-2 text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:hover:text-muted-foreground transition"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page === totalPages}
                className="rounded-xl border border-input bg-background p-2 text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:hover:text-muted-foreground transition"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </Card>

      <InvestorDetailModal
        investorId={selectedInvestorId}
        isOpen={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setSelectedInvestorId(null);
        }}
      />
    </div>
  );
}
