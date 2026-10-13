import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api/client";

export function Spinner({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <div className="text-ink-faint">{icon}</div>
      <p className="font-medium text-ink">{title}</p>
      {description && <p className="max-w-sm text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Une erreur inattendue est survenue";
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-ink"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-critical" aria-hidden />
      <span>{errorMessage(error)}</span>
    </div>
  );
}
