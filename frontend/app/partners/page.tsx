"use client";

import { useEffect, useState } from "react";
import { getPartners, Partner } from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn, fieldInputClassName, formatDate } from "@/lib/utils";
import { Search, ChevronLeft, ChevronRight, Loader2, Linkedin, Twitter, Link2, ShieldCheck, HelpCircle } from "lucide-react";
import { InvestorDetailModal } from "@/components/investor-detail-modal";

export default function PartnersPage() {
  const [q, setQ] = useState("");
  const [partners, setPartners] = useState<Partner[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const limit = 15;

  const [selectedInvestorId, setSelectedInvestorId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const offset = (page - 1) * limit;
        const res = await getPartners({
          q,
          limit,
          offset
        });
        setPartners(res.items);
        setTotal(res.total);
      } catch (err) {
        console.error("Failed to load partners:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [q, page]);

  const totalPages = Math.ceil(total / limit) || 1;

  const handleSearchChange = (val: string) => {
    setQ(val);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Partner Intelligence</p>
        <h2 className="mt-1 text-3xl font-extrabold text-foreground glow-accent">Venture Partners</h2>
      </div>

      {/* Control bar */}
      <Card className="glass-card border-border p-6 flex flex-col sm:flex-row items-center gap-4 justify-between">
        <div className="relative w-full max-w-md">
          <Search className="absolute top-3 left-3 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search partner name or role..."
            value={q}
            onChange={(e) => handleSearchChange(e.target.value)}
            className={cn(fieldInputClassName, "pl-10 pr-4 py-2.5")}
          />
        </div>
        <p className="text-xs text-muted-foreground shrink-0">
          Tip: Click on a partner's profile to view their venture firm
        </p>
      </Card>

      {/* Partners List */}
      <Card className="glass-card border-border overflow-hidden">
        <CardHeader className="px-6 py-5 border-b border-border flex flex-row items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-foreground">Partner Directory</h3>
            <p className="text-xs text-muted-foreground">Total {total} partner records found</p>
          </div>
          {loading && <Loader2 className="h-5 w-5 animate-spin text-violet-400" />}
        </CardHeader>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-border text-muted-foreground text-xs font-semibold bg-muted/50">
              <tr>
                <th className="px-6 py-3.5">Name</th>
                <th className="px-6 py-3.5">Role / Title</th>
                <th className="px-6 py-3.5">Extraction Confidence</th>
                <th className="px-6 py-3.5">Social URLs</th>
                <th className="px-6 py-3.5">Date Scraped</th>
                <th className="px-6 py-3.5 text-right">Firm Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {!loading && partners.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    No matching partner profiles found.
                  </td>
                </tr>
              ) : (
                partners.map((partner) => (
                  <tr 
                    key={partner.id} 
                    className="hover:bg-muted/50 transition duration-150 align-middle"
                  >
                    <td className="px-6 py-4 font-semibold text-foreground">
                      {partner.name}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-xs font-medium">
                      {partner.role || "Not specified"}
                    </td>
                    <td className="px-6 py-4">
                      {partner.confidence !== null && partner.confidence !== undefined ? (
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 bg-emerald-500/5 border border-emerald-500/10 rounded-lg px-2 py-1 w-fit">
                          <ShieldCheck className="h-3.5 w-3.5" />
                          <span>{Math.round(partner.confidence * 100)}%</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <HelpCircle className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>N/A</span>
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        {partner.linkedin_url ? (
                          <a 
                            href={partner.linkedin_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="rounded-lg bg-muted p-1.5 text-muted-foreground hover:text-[#0077b5] hover:bg-muted/80 transition"
                          >
                            <Linkedin className="h-4 w-4" />
                          </a>
                        ) : null}
                        {partner.twitter_url ? (
                          <a 
                            href={partner.twitter_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="rounded-lg bg-muted p-1.5 text-muted-foreground hover:text-[#1da1f2] hover:bg-muted/80 transition"
                          >
                            <Twitter className="h-4 w-4" />
                          </a>
                        ) : null}
                        {partner.source_url ? (
                          <a 
                            href={partner.source_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="rounded-lg bg-muted p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/80 transition"
                          >
                            <Link2 className="h-4 w-4" />
                          </a>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-xs">
                      {formatDate(partner.updated_at)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => {
                          setSelectedInvestorId(partner.investor_id);
                          setModalOpen(true);
                        }}
                        className="rounded-lg bg-violet-600/10 px-3.5 py-1.5 text-xs font-bold text-violet-400 hover:bg-violet-600/20 hover:text-violet-300 transition"
                      >
                        VC Firm
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
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

      {/* Drawer */}
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
