"use client";

import { useEffect, useState } from "react";
import { deleteInvestor, getInvestor, InvestorDetail, updateInvestor } from "@/lib/api";
import { X, Globe, Link2, Linkedin, Twitter, Building, ShieldCheck, Pencil, Save, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface InvestorDetailModalProps {
  investorId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export function InvestorDetailModal({ investorId, isOpen, onClose }: InvestorDetailModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<InvestorDetail | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "team" | "portfolio">("overview");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState({
    firm: "",
    website: "",
    source_url: "",
    focus_sectors: "",
    investment_stage: "",
    geography: "",
    contact_links: "",
  });

  useEffect(() => {
    if (!isOpen || investorId === null) {
      setData(null);
      return;
    }

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const details = await getInvestor(investorId!);
        setData(details);
        setDraft({
          firm: details.firm || "",
          website: details.website || "",
          source_url: details.source_url || "",
          focus_sectors: (details.focus_sectors || []).join(", "),
          investment_stage: (details.investment_stage || []).join(", "),
          geography: (details.geography || []).join(", "),
          contact_links: (details.contact_links || []).join("\n"),
        });
      } catch (err) {
        console.error(err);
        setError("Failed to load investor details.");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [investorId, isOpen]);

  const splitValues = (value: string) =>
    value
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);

  const handleSave = async () => {
    if (!investorId) return;

    setSaving(true);
    setError(null);

    try {
      const next = await updateInvestor(investorId, {
        firm: draft.firm,
        website: draft.website,
        source_url: draft.source_url,
        focus_sectors: splitValues(draft.focus_sectors),
        investment_stage: splitValues(draft.investment_stage),
        geography: splitValues(draft.geography),
        contact_links: splitValues(draft.contact_links),
      });
      setData(next);
      setEditing(false);
    } catch (err: any) {
      setError(err.message || "Failed to save investor.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!investorId || !data) return;

    const reason = window.prompt(
      `Delete ${data.firm}? Add a reason so the AI can learn from this cleanup.`,
      "Not a valid investor record."
    );

    if (reason === null) return;

    setSaving(true);
    setError(null);

    try {
      await deleteInvestor(investorId, reason);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to delete investor.");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-foreground/20 backdrop-blur-sm transition-opacity duration-300"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="relative z-50 h-full w-full max-w-2xl border-l border-border bg-card px-6 py-6 shadow-2xl sm:px-8 md:w-[600px] flex flex-col">
        {/* Header controls */}
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <Building className="h-5 w-5 text-violet-600" />
            <span className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Investor Profile</span>
          </div>
          <div className="flex items-center gap-2">
            {data && (
              <>
                <button
                  onClick={() => setEditing((current) => !current)}
                  disabled={saving}
                  className="rounded-full p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition disabled:opacity-50"
                  title="Edit investor"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={handleDelete}
                  disabled={saving}
                  className="rounded-full p-2 text-red-600 hover:bg-red-50 transition disabled:opacity-50"
                  title="Delete investor"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="rounded-full p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto py-6 space-y-6">
          {loading && (
            <div className="flex h-64 flex-col items-center justify-center space-y-3">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" />
              <p className="text-sm text-muted-foreground">Loading AI intelligence...</p>
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-center text-sm text-red-600 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-400">
              {error}
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Profile Title & Website */}
              <div className="space-y-3">
                {editing ? (
                  <div className="space-y-3 rounded-xl border border-border bg-muted/30 p-4">
                    <input
                      value={draft.firm}
                      onChange={(event) => setDraft((current) => ({ ...current, firm: event.target.value }))}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold outline-none focus:border-violet-500"
                      placeholder="Firm name"
                    />
                    <input
                      value={draft.website}
                      onChange={(event) => setDraft((current) => ({ ...current, website: event.target.value }))}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-violet-500"
                      placeholder="Website"
                    />
                    <input
                      value={draft.source_url}
                      onChange={(event) => setDraft((current) => ({ ...current, source_url: event.target.value }))}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-violet-500"
                      placeholder="Source URL"
                    />
                    <textarea
                      value={draft.focus_sectors}
                      onChange={(event) => setDraft((current) => ({ ...current, focus_sectors: event.target.value }))}
                      className="min-h-16 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-violet-500"
                      placeholder="Focus sectors, comma separated"
                    />
                    <textarea
                      value={draft.investment_stage}
                      onChange={(event) => setDraft((current) => ({ ...current, investment_stage: event.target.value }))}
                      className="min-h-16 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-violet-500"
                      placeholder="Investment stages, comma separated"
                    />
                    <textarea
                      value={draft.geography}
                      onChange={(event) => setDraft((current) => ({ ...current, geography: event.target.value }))}
                      className="min-h-16 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-violet-500"
                      placeholder="Geography, comma separated"
                    />
                    <textarea
                      value={draft.contact_links}
                      onChange={(event) => setDraft((current) => ({ ...current, contact_links: event.target.value }))}
                      className="min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-violet-500"
                      placeholder="Contact links, one per line"
                    />
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-xs font-bold text-white hover:bg-violet-500 disabled:opacity-50"
                    >
                      <Save className="h-3.5 w-3.5" />
                      {saving ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                ) : (
                  <h2 className="text-2xl font-bold text-foreground tracking-tight">{data.firm}</h2>
                )}
                <div className="flex flex-wrap gap-3 text-sm">
                  {data.website && (
                    <a 
                      href={data.website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-violet-600 hover:underline font-medium"
                    >
                      <Globe className="h-4 w-4" />
                      Website
                    </a>
                  )}
                  {data.source_url && (
                    <a 
                      href={data.source_url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition"
                    >
                      <Link2 className="h-4 w-4" />
                      Source URL
                    </a>
                  )}
                </div>
              </div>

              {/* Navigation Tabs */}
              <div className="flex border-b border-border">
                {(["overview", "team", "portfolio"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={cn(
                      "flex-1 pb-3 text-sm font-semibold capitalize border-b-2 transition-all duration-200",
                      activeTab === tab 
                        ? "border-violet-500 text-violet-600" 
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="space-y-6">
                {activeTab === "overview" && (
                  <div className="space-y-6">
                    {/* Sectors */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Focus Sectors</h4>
                      <div className="flex flex-wrap gap-2">
                        {data.focus_sectors.length > 0 ? (
                          data.focus_sectors.map((sector) => (
                            <Badge 
                              key={sector} 
                              className="bg-violet-100 text-violet-800 hover:bg-violet-200 border border-violet-200 px-3 py-1 text-xs dark:bg-violet-600/10 dark:text-violet-300 dark:border-violet-500/20"
                            >
                              {sector}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">No sector keywords extracted</span>
                        )}
                      </div>
                    </div>

                    {/* Investment Stages */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Target Stages</h4>
                      <div className="flex flex-wrap gap-2">
                        {data.investment_stage.length > 0 ? (
                          data.investment_stage.map((stage) => (
                            <Badge 
                              key={stage} 
                              className="bg-emerald-100 text-emerald-800 hover:bg-emerald-200 border border-emerald-200 px-3 py-1 text-xs dark:bg-emerald-600/10 dark:text-emerald-300 dark:border-emerald-500/20"
                            >
                              {stage}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">No stage limits extracted</span>
                        )}
                      </div>
                    </div>

                    {/* Geography */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Geographic Target</h4>
                      <div className="flex flex-wrap gap-2">
                        {data.geography.length > 0 ? (
                          data.geography.map((geo) => (
                            <Badge 
                              key={geo} 
                              className="bg-blue-100 text-blue-800 hover:bg-blue-200 border border-blue-200 px-3 py-1 text-xs dark:bg-blue-600/10 dark:text-blue-300 dark:border-blue-500/20"
                            >
                              {geo}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">No geographic focus extracted</span>
                        )}
                      </div>
                    </div>

                    {/* Contact Links */}
                    {data.contact_links && data.contact_links.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Outbound Links / Contact Paths</h4>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {data.contact_links.map((link, idx) => (
                            <a
                              key={idx}
                              href={link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 rounded-xl bg-muted p-3 text-xs text-foreground border border-border hover:border-violet-300 hover:bg-muted/80 transition"
                            >
                              <Link2 className="h-4 w-4 shrink-0 text-violet-600" />
                              <span className="truncate">{link}</span>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "team" && (
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Investment Partners</h4>
                    {data.partners && data.partners.length > 0 ? (
                      <div className="grid gap-3">
                        {data.partners.map((partner) => (
                          <div 
                            key={partner.id} 
                            className="flex items-center justify-between rounded-xl bg-muted p-4 border border-border hover:border-border transition"
                          >
                            <div className="space-y-1">
                              <p className="font-semibold text-foreground text-sm">{partner.name}</p>
                              {partner.role && (
                                <p className="text-xs text-muted-foreground">{partner.role}</p>
                              )}
                              {partner.confidence !== null && partner.confidence !== undefined && (
                                <div className="flex items-center gap-1 text-[10px] font-semibold text-emerald-600">
                                  <ShieldCheck className="h-3 w-3" />
                                  <span>{Math.round(partner.confidence * 100)}% Extraction confidence</span>
                                </div>
                              )}
                            </div>
                            <div className="flex gap-2">
                              {partner.linkedin_url && (
                                <a 
                                  href={partner.linkedin_url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="rounded-full bg-muted p-2 text-muted-foreground hover:text-[#0077b5] hover:bg-muted/80 transition"
                                >
                                  <Linkedin className="h-4 w-4" />
                                </a>
                              )}
                              {partner.twitter_url && (
                                <a 
                                  href={partner.twitter_url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="rounded-full bg-muted p-2 text-muted-foreground hover:text-[#1da1f2] hover:bg-muted/80 transition"
                                >
                                  <Twitter className="h-4 w-4" />
                                </a>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                        No team members extracted yet
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "portfolio" && (
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Extracted Portfolio Companies</h4>
                    {data.portfolio_companies && data.portfolio_companies.length > 0 ? (
                      <div className="grid gap-2 sm:grid-cols-2">
                        {data.portfolio_companies.map((company) => (
                          <div 
                            key={company.id} 
                            className="flex items-center gap-2 rounded-xl bg-muted p-3 border border-border hover:bg-muted/80 transition"
                          >
                            <div className="h-2 w-2 rounded-full bg-violet-500" />
                            <span className="text-sm font-medium text-foreground">{company.company_name}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                        No portfolio companies identified
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
