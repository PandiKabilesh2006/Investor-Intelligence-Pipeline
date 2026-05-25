"use client";

import { useEffect, useState } from "react";
import { semanticSearch, SearchResult } from "@/lib/api";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, SlidersHorizontal, Loader2, Sparkles, ShieldCheck, ChevronRight, Compass, Shield } from "lucide-react";
import { InvestorDetailModal } from "@/components/investor-detail-modal";
import { cn, fieldInputClassName } from "@/lib/utils";

const SECTORS = [
  "Artificial Intelligence",
  "Enterprise AI",
  "B2B SaaS",
  "Voice AI",
  "Fintech",
  "Healthcare",
  "Deeptech",
  "Web3",
  "Proptech"
];

const STAGES = [
  "Pre-Seed",
  "Seed",
  "Series A",
  "Series B",
  "Growth Stage"
];

const GEOGRAPHIES = [
  "India",
  "United States",
  "Europe",
  "Southeast Asia",
  "Middle East",
  "Global"
];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [stage, setStage] = useState("");
  const [geography, setGeography] = useState("");

  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return;

    setLoading(true);
    setSearched(true);
    try {
      const res = await semanticSearch({
        q: q.trim(),
        sector: sector || undefined,
        stage: stage || undefined,
        geography: geography || undefined,
        limit: 15
      });
      setResults(res.items);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setLoading(false);
    }
  };

  // Generate a dynamic, friendly explanation text based on boosts and scores
  const getMatchExplanation = (investor: SearchResult) => {
    const reasons: string[] = [];
    if (investor.sector_boost > 0) reasons.push("Focus Sector");
    if (investor.stage_boost > 0) reasons.push("Investment Stage");
    if (investor.geography_boost > 0) reasons.push("Target Geography");

    const baseText = `Matches based on semantic text similarity (${Math.round(investor.semantic_score * 100)}% match).`;
    if (reasons.length > 0) {
      return `${baseText} Boosted for alignment with: ${reasons.join(", ")}.`;
    }
    return baseText;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">AI semantic engine</p>
        <h2 className="mt-1 text-3xl font-extrabold text-foreground glow-accent flex items-center gap-2">
          <Sparkles className="h-7 w-7 text-violet-600 fill-current" />
          Semantic Search
        </h2>
      </div>

      {/* Query Card */}
      <Card className="glass-card border-border p-6">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex flex-col gap-3 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute top-3.5 left-3.5 h-4.5 w-4.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Describe your startup thesis... (e.g. Early stage climate tech startup raises Series A in Europe)"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className={cn(fieldInputClassName, "pl-11 pr-4 py-3")}
              />
            </div>
            <button
              type="submit"
              disabled={q.trim().length < 2 || loading}
              className="rounded-xl bg-violet-600 px-6 py-3 text-sm font-bold text-white hover:bg-violet-500 disabled:bg-violet-800/40 disabled:text-muted-foreground transition flex items-center justify-center gap-1.5 shrink-0"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4.5 w-4.5 animate-spin" />
                  Analyzing
                </>
              ) : (
                <>
                  <Sparkles className="h-4.5 w-4.5" />
                  Semantic Match
                </>
              )}
            </button>
          </div>

          {/* Search filters drawer */}
          <div className="border-t border-border pt-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
              <SlidersHorizontal className="h-3.5 w-3.5 text-violet-400" />
              <span>Apply Filters to Constrain Retuned Results:</span>
            </div>
            
            <div className="grid gap-3 sm:grid-cols-3">
              {/* Sector */}
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className={cn(fieldInputClassName, "px-3 py-2.5 text-xs")}
              >
                <option value="">Any Sector focus</option>
                {SECTORS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              {/* Stage */}
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                className={cn(fieldInputClassName, "px-3 py-2.5 text-xs")}
              >
                <option value="">Any Funding Stage</option>
                {STAGES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              {/* Geography */}
              <select
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                className={cn(fieldInputClassName, "px-3 py-2.5 text-xs")}
              >
                <option value="">Any Geography</option>
                {GEOGRAPHIES.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
          </div>
        </form>
      </Card>

      {/* Loading state */}
      {loading && (
        <div className="flex flex-col h-64 items-center justify-center space-y-3">
          <Loader2 className="h-10 w-10 animate-spin text-violet-400" />
          <p className="text-sm text-muted-foreground font-medium">Computing pgvector hybrid similarity ranking...</p>
        </div>
      )}

      {/* Results */}
      {!loading && searched && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground font-semibold px-1">
            <span>FOUND {results.length} SEMANTIC MATCHES</span>
            <span>SORTED BY HYBRID RETRIEVAL RELEVANCE</span>
          </div>

          {results.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-12 text-center text-muted-foreground text-sm">
              No matching VCs found for your startup parameters. Try adjusting filters or expanding search query.
            </div>
          ) : (
            <div className="grid gap-4">
              {results.map((investor) => {
                const totalScore = Math.round(investor.hybrid_score * 100);
                return (
                  <Card 
                    key={investor.id} 
                    className="glass-card glass-card-hover border-border overflow-hidden flex flex-col md:flex-row md:items-stretch"
                  >
                    {/* Glowing Score Bar */}
                    <div className="w-full md:w-3.5 bg-gradient-to-b from-violet-600 via-pink-500 to-blue-500" />

                    {/* Card Content */}
                    <CardContent className="p-6 flex-1 flex flex-col justify-between space-y-4 md:space-y-0 md:flex-row md:items-start md:gap-6">
                      <div className="space-y-3 flex-1">
                        <div className="flex flex-wrap items-center gap-3">
                          <h3 className="text-lg font-bold text-foreground tracking-tight">{investor.firm_name}</h3>
                          {investor.website && (
                            <a 
                              href={investor.website} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-xs font-semibold text-muted-foreground underline hover:text-violet-600 transition"
                            >
                              website
                            </a>
                          )}
                        </div>

                        {/* Match Explanation */}
                        <div className="flex gap-2 bg-muted/50 rounded-xl p-3 border border-border text-xs text-muted-foreground">
                          <Compass className="h-4 w-4 shrink-0 text-violet-400 mt-0.5" />
                          <span>{getMatchExplanation(investor)}</span>
                        </div>

                        {/* Badges */}
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {investor.focus_sectors.slice(0, 4).map((s) => (
                            <Badge key={s} className="bg-violet-100 text-violet-800 border-violet-200 text-[10px]">{s}</Badge>
                          ))}
                          {investor.investment_stage.slice(0, 2).map((s) => (
                            <Badge key={s} className="bg-emerald-100 text-emerald-800 border-emerald-200 text-[10px]">{s}</Badge>
                          ))}
                          {investor.geography.slice(0, 2).map((s) => (
                            <Badge key={s} className="bg-blue-100 text-blue-800 border-blue-200 text-[10px]">{s}</Badge>
                          ))}
                        </div>
                      </div>

                      {/* Match parameters column */}
                      <div className="flex flex-row md:flex-col items-center justify-between md:justify-start md:items-end gap-4 shrink-0 border-t border-border pt-4 md:border-t-0 md:pt-0">
                        {/* Circular Match rating widget */}
                        <div className="flex items-center gap-2">
                          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-violet-600/15 border-2 border-violet-500/40">
                            <span className="font-extrabold text-sm text-violet-700">{totalScore}%</span>
                          </div>
                          <div className="text-left md:text-right">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Hybrid Match</p>
                            <p className="text-[9px] text-muted-foreground font-semibold mt-0.5">Semantic + Boosts</p>
                          </div>
                        </div>

                        <button 
                          onClick={() => {
                            setSelectedId(investor.id);
                            setModalOpen(true);
                          }}
                          className="rounded-lg bg-violet-600 px-4 py-2 text-xs font-bold text-white hover:bg-violet-500 transition flex items-center gap-1 shadow-lg shadow-violet-900/15"
                        >
                          View Profile
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Detail drawer modal */}
      <InvestorDetailModal 
        investorId={selectedId}
        isOpen={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setSelectedId(null);
        }}
      />
    </div>
  );
}
