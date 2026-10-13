"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Brain, Check, RotateCcw, ScrollText, ThumbsDown } from "lucide-react";

import { SeverityBadge } from "@/components/alerts/severity-badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { useToast } from "@/components/ui/toast";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { Alert, AlertStatus } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { errorMessage } from "@/components/ui/feedback";

const STATUS_LABEL: Record<AlertStatus, string> = {
  new: "Nouvelle",
  acknowledged: "Traitée",
  dismissed: "Fausse alerte",
};

export function AlertList({ alerts, compact = false }: { alerts: Alert[]; compact?: boolean }) {
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: AlertStatus }) =>
      api.alerts.setStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.alertCounts });
    },
    onError: (error) => notify({ title: "Action impossible", description: errorMessage(error) }),
  });

  return (
    <ul className="divide-y divide-border">
      {alerts.map((alert) => {
        const SourceIcon = alert.source === "lstm" ? Brain : ScrollText;
        const busy = mutation.isPending && mutation.variables?.id === alert.id;
        return (
          <li
            key={alert.id}
            className={cn("flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start", alert.status !== "new" && "opacity-70")}
          >
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={alert.severity} />
                <span className="flex items-center gap-1 text-xs text-ink-faint">
                  <SourceIcon className="size-3.5" aria-hidden />
                  {alert.source === "lstm" ? "Modèle IA" : "Règle"}
                </span>
                {alert.status !== "new" && (
                  <span className="text-xs text-ink-faint">· {STATUS_LABEL[alert.status]}</span>
                )}
              </div>
              <p className="font-medium text-ink">{alert.title}</p>
              {!compact && <p className="text-sm text-ink-muted">{alert.message}</p>}
              <p className="text-xs text-ink-faint">{formatDateTime(alert.created_at)}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              {alert.status === "new" ? (
                <>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={busy}
                    onClick={() => mutation.mutate({ id: alert.id, status: "acknowledged" })}
                  >
                    <Check className="size-3.5" aria-hidden />
                    Traitée
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    title="Signaler une fausse alerte (aide à améliorer les règles et le modèle)"
                    onClick={() => mutation.mutate({ id: alert.id, status: "dismissed" })}
                  >
                    <ThumbsDown className="size-3.5" aria-hidden />
                    Fausse alerte
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  loading={busy}
                  onClick={() => mutation.mutate({ id: alert.id, status: "new" })}
                >
                  <RotateCcw className="size-3.5" aria-hidden />
                  Rouvrir
                </Button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
