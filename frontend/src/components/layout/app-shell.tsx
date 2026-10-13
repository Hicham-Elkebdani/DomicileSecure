"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  Camera,
  FileText,
  LayoutDashboard,
  LogOut,
  Settings,
  ShieldCheck,
  Users,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, type ReactNode } from "react";

import { cn } from "@/components/ui/cn";
import { useToast } from "@/components/ui/toast";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { Alert } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth-context";
import { useRealtime, type ConnectionState } from "@/lib/realtime/use-realtime";

const NAV = [
  { href: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/alerts", label: "Alertes", icon: Bell },
  { href: "/events", label: "Activité", icon: Waves },
  { href: "/persons", label: "Personnes", icon: Users },
  { href: "/cameras", label: "Caméras", icon: Camera },
  { href: "/summary", label: "Résumé du jour", icon: FileText },
  { href: "/settings", label: "Paramètres", icon: Settings },
] as const;

const CONNECTION: Record<ConnectionState, { label: string; dot: string }> = {
  online: { label: "Temps réel actif", dot: "bg-good" },
  connecting: { label: "Connexion…", dot: "bg-warning" },
  offline: { label: "Hors ligne", dot: "bg-critical" },
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { notify } = useToast();
  const { data: counts } = useQuery({ queryKey: queryKeys.alertCounts, queryFn: api.alerts.counts });

  const onAlert = useCallback(
    (alert: Alert) => notify({ title: alert.title, description: alert.message, severity: alert.severity }),
    [notify],
  );
  const connection = useRealtime(onAlert);
  const status = CONNECTION[connection];

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="border-b border-border bg-surface-1 lg:sticky lg:top-0 lg:h-screen lg:border-r lg:border-b-0">
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 px-5 py-4">
            <div className="flex size-8 items-center justify-center rounded-lg bg-accent text-accent-ink">
              <ShieldCheck className="size-4" aria-hidden />
            </div>
            <span className="font-semibold text-ink">DomicileSecure</span>
          </div>

          <nav
            aria-label="Navigation principale"
            className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:overflow-visible"
          >
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                  isActive(href)
                    ? "bg-surface-2 font-medium text-ink"
                    : "text-ink-muted hover:bg-surface-2 hover:text-ink",
                )}
              >
                <Icon className="size-4" aria-hidden />
                {label}
                {href === "/alerts" && counts && counts.new > 0 && (
                  <span className="ml-auto rounded-full bg-accent px-1.5 text-xs font-semibold text-accent-ink">
                    {counts.new}
                  </span>
                )}
              </Link>
            ))}
          </nav>

          <div className="hidden border-t border-border px-5 py-4 lg:block">
            <p className="flex items-center gap-2 text-xs text-ink-muted">
              <span className={cn("size-2 rounded-full", status.dot)} aria-hidden />
              {status.label}
            </p>
            <p className="mt-3 truncate text-sm text-ink" title={user?.email}>
              {user?.full_name || user?.email}
            </p>
            <button
              type="button"
              onClick={logout}
              className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink"
            >
              <LogOut className="size-3.5" aria-hidden />
              Se déconnecter
            </button>
          </div>
        </div>
      </aside>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
        <div className="mb-4 flex items-center justify-between lg:hidden">
          <p className="flex items-center gap-2 text-xs text-ink-muted">
            <span className={cn("size-2 rounded-full", status.dot)} aria-hidden />
            {status.label}
          </p>
          <button type="button" onClick={logout} className="text-sm text-ink-muted">
            Se déconnecter
          </button>
        </div>
        {children}
      </main>
    </div>
  );
}
