"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { Activity, Building2, Search, Settings, Users, Menu, X, Brain, Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ClientIcon } from "@/components/ui/client-icon";

const navItems = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/investors", label: "Investors", icon: Building2 },
  { href: "/partners", label: "Partners", icon: Users },
  { href: "/search", label: "AI Search", icon: Search },
  { href: "/pipeline", label: "Pipeline Control", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("light");

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "dark" | "light" | null;
    const initialTheme = savedTheme === "dark" ? "dark" : "light";
    setTheme(initialTheme);
    document.documentElement.classList.toggle("dark", initialTheme === "dark");
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
  };

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300 relative">
      {/* Background glowing gradients */}
      <div className="pointer-events-none fixed -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-violet-600/10 blur-[150px] dark:bg-violet-600/10 bg-violet-600/5" />
      <div className="pointer-events-none fixed -bottom-40 -right-40 h-[600px] w-[600px] rounded-full bg-blue-600/10 blur-[150px] dark:bg-blue-600/10 bg-blue-600/5" />

      {/* Mobile Top Bar */}
      <header className="flex h-16 items-center justify-between border-b border-border bg-card/85 px-4 backdrop-blur-md lg:hidden">
        <div className="flex items-center gap-2">
          <ClientIcon icon={Brain} className="h-6 w-6 text-violet-500" />
          <span className="font-sans text-lg font-bold tracking-tight text-foreground glow-accent">
            InvestorIntel
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted/10 hover:text-foreground"
            aria-label="Toggle Theme"
          >
            <ClientIcon icon={theme === "dark" ? Sun : Moon} className="h-5 w-5" />
          </button>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted/10 hover:text-foreground"
          >
            {mobileOpen ? <ClientIcon icon={X} className="h-6 w-6" /> : <ClientIcon icon={Menu} className="h-6 w-6" />}
          </button>
        </div>
      </header>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile Menu Drawer */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 transform border-r border-border bg-card px-5 py-6 transition-transform duration-300 ease-in-out lg:hidden flex flex-col justify-between",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div>
          <div className="mb-8 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ClientIcon icon={Brain} className="h-6 w-6 text-violet-500" />
              <span className="font-sans text-xl font-bold text-foreground">InvestorIntel</span>
            </div>
            <button
              onClick={() => setMobileOpen(false)}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted/10 hover:text-foreground"
            >
              <ClientIcon icon={X} className="h-5 w-5" />
            </button>
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href as any}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200",
                    active
                      ? "bg-violet-600/20 text-violet-500 dark:text-violet-400 border border-violet-500/25"
                      : "text-muted-foreground hover:bg-muted/10 hover:text-foreground"
                  )}
                >
                  <ClientIcon icon={Icon} className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Mobile Theme Toggle Footer */}
        <div className="border-t border-border pt-4 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">Theme</span>
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/10 border border-border text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-all duration-200"
            aria-label="Toggle Theme"
          >
            <ClientIcon icon={theme === "dark" ? Sun : Moon} className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* Desktop Sidebar (Fixed) */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-card/75 px-5 py-6 backdrop-blur-xl lg:flex lg:flex-col lg:justify-between">
        <div>
          <div className="mb-10 flex items-center gap-2 px-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-600/20 border border-violet-500/30">
              <ClientIcon icon={Brain} className="h-5 w-5 text-violet-400" />
            </div>
            <div>
              <h1 className="font-sans text-base font-bold tracking-tight text-foreground glow-accent">
                Investor Intel
              </h1>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Research Pipeline
              </p>
            </div>
          </div>
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href as any}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 border border-transparent",
                    active
                      ? "bg-violet-600/15 text-violet-500 dark:text-violet-300 border-violet-500/20 shadow-[0_0_15px_rgba(139,92,246,0.07)]"
                      : "text-muted-foreground hover:bg-muted/10 hover:text-foreground"
                  )}
                >
                  <ClientIcon icon={Icon} className="h-4.5 w-4.5" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer with Theme Toggle */}
        <div className="border-t border-border pt-4 flex items-center justify-between px-2">
          <span className="text-xs font-semibold text-muted-foreground">Theme</span>
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/10 border border-border text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-all duration-200"
            aria-label="Toggle Theme"
          >
            <ClientIcon icon={theme === "dark" ? Sun : Moon} className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="lg:pl-64 min-h-screen">
        <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  );
}
