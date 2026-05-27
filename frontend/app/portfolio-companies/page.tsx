"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getPortfolioCompanies, PortfolioCompany } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, fieldInputClassName } from "@/lib/utils";
import { Search, ChevronLeft, ChevronRight, Loader2, Building, Building2, X } from "lucide-react";
import { InvestorDetailModal } from "@/components/investor-detail-modal";

function PortfolioCompaniesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const urlInvestorId = searchParams.get("investor_id") ? Number(searchParams.get("investor_id")) : undefined;
  const urlFirm = searchParams.get("firm") || "";

  const [q, setQ] = useState("");
  const [firm, setFirm] = useState(urlFirm);
  const [investorId] = useState<number | undefined>(urlInvestorId);

  const [companies, setCompanies] = useState<PortfolioCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const limit = 15;

  const [selectedInvestorId, setSelectedInvestorId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const isFiltered = !!investorId || !!firm;

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const offset = (page - 1) * limit;
        const res = await getPortfolioCompanies({ q, investor_id: investorId, firm, limit, offset });
        setCompanies(res.items);
        setTotal(res.total);
      } catch (err) {
        console.error("Failed to load portfolio companies:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [q, investorId, firm, page]);

  const totalPages = Math.ceil(total / limit) || 1;

  const clearFirmFilter = () => {
    setFirm("");
    setPage(1);
    router.push("/portfolio-companies");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Market Ecosystem</p>
        <h2 className="mt-1 text-3xl font-extrabold text-foreground glow-accent">Portfolio Companies</h2>
      </div>

      {/* Active investor filter banner */}
      {isFiltered && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-700 px-4 py-3">
          <Building2 className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-800 dark:text-amber-300 font-medium">
            Filtered by firm: <span className="font-bold">{urlFirm || `Investor #${investorId}`}</span>
          </p>
          <button
            onClick={clearFirmFilter}
            className="ml-auto flex items-center gap-1 rounded-lg bg-amber-200 dark:bg-amber-800 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:text-amber-200 hover:bg-amber-300 transition"
          >
            <X className="h-3 w-3" /> Clear filter
          </button>
        </div>
      )}

      {/* Search */}
      <Card className="glass-card border-border p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Company name search */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">Company Name</label>
            <div className="relative">
              <Search className="absolute top-3 left-3 h-4 w-4 text-muted-foreground" />
              <input type="text" placeholder="Search company name..."
                value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }}
                className={cn(fieldInputClassName, "pl-10 pr-4 py-2.5")} />
            </div>
          </div>
          {/* Firm name filter */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">Filter by Firm</label>
            <div className="relative">
              <Building2 className="absolute top-3 left-3 h-4 w-4 text-muted-foreground" />
              <input type="text" placeholder="Search investor firm name..."
                value={firm} onChange={(e) => { setFirm(e.target.value); setPage(1); }}
                className={cn(fieldInputClassName, "pl-10 pr-4 py-2.5")} />
              {firm && (
                <button onClick={() => { setFirm(""); setPage(1); }}
                  className="absolute top-2.5 right-2.5 rounded p-0.5 text-muted-foreground hover:text-foreground transition">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card className="glass-card border-border overflow-hidden">
        <CardHeader className="px-6 py-5 border-b border-border flex flex-row items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-foreground">Ecosystem Directory</h3>
            <p className="text-xs text-muted-foreground">
              {isFiltered
                ? `${total} compan${total !== 1 ? "ies" : "y"} from ${urlFirm || `investor #${investorId}`}`
                : `Total ${total} portfolio companies tracked`}
            </p>
          </div>
          {loading && <Loader2 className="h-5 w-5 animate-spin text-violet-400" />}
        </CardHeader>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead className="border-b border-border text-muted-foreground text-xs font-semibold bg-muted/50">
              <tr>
                <th className="px-4 py-3.5 w-14 text-center">ID</th>
                <th className="px-4 py-3.5 w-28 text-center">Investor ID</th>
                <th className="px-4 py-3.5">Company Name</th>
                <th className="px-4 py-3.5">Sector</th>
                <th className="px-4 py-3.5 text-right">VC Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!loading && companies.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">
                    No matching portfolio companies found.
                  </td>
                </tr>
              ) : (
                companies.map((company) => (
                  <tr key={company.id} className="hover:bg-muted/50 transition duration-150 align-middle">
                    <td className="px-4 py-4 text-center text-xs text-muted-foreground font-mono">{company.id}</td>
                    <td className="px-4 py-4 text-center">
                      <span className="inline-block rounded bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground">
                        {company.investor_id}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-violet-500 shrink-0" />
                        <div>
                          <p className="font-semibold text-foreground">{company.company_name}</p>
                          {company.firm_name && (
                            <button
                              onClick={() => { setSelectedInvestorId(company.investor_id); setModalOpen(true); }}
                              className="flex items-center gap-1 mt-0.5 text-[11px] text-muted-foreground hover:text-violet-600 transition"
                            >
                              <Building className="h-3 w-3" />
                              <span>{company.firm_name}</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      {company.sector ? (
                        <Badge className="bg-amber-100 text-amber-800 border border-amber-200 px-2.5 py-0.5 text-[11px]">
                          {company.sector}
                        </Badge>
                      ) : <span className="text-xs text-muted-foreground italic">—</span>}
                    </td>
                    <td className="px-4 py-4 text-right">
                      {company.investor_id ? (
                        <button
                          onClick={() => { setSelectedInvestorId(company.investor_id); setModalOpen(true); }}
                          className="rounded-lg bg-violet-600/10 px-3.5 py-1.5 text-xs font-bold text-violet-700 hover:bg-violet-600/20 transition"
                        >
                          VC Profile
                        </button>
                      ) : <span className="text-xs text-muted-foreground italic">—</span>}
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
        investorId={selectedInvestorId}
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); setSelectedInvestorId(null); }}
      />
    </div>
  );
}

export default function PortfolioCompaniesPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-violet-600" /></div>}>
      <PortfolioCompaniesContent />
    </Suspense>
  );
}
