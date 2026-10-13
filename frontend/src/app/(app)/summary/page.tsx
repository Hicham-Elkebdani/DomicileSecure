"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ErrorBox, Spinner } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page-header";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { DailySummary } from "@/lib/api/types";
import { formatDayLong } from "@/lib/format";

function Stats({ summary }: { summary: DailySummary }) {
  const s = summary.stats;
  const alerts = Object.values(s.alerts).reduce((a, b) => a + b, 0);
  const items = [
    { label: "Membres du foyer vus", value: s.residents.length },
    { label: "Invités", value: s.guests.length },
    { label: "Passages non reconnus", value: s.unknown_sightings + s.visitor_sightings },
    { label: "Ouvertures de porte", value: s.door_openings },
    { label: "Passages d'animaux", value: s.animals },
    { label: "Alertes", value: alerts },
  ];
  return (
    <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-lg bg-surface-2 px-4 py-3">
          <dt className="text-xs text-ink-muted">{item.label}</dt>
          <dd className="text-xl font-semibold tabular-nums text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function SummaryPage() {
  const today = useQuery({ queryKey: queryKeys.summaryToday, queryFn: api.summaries.today });
  const history = useQuery({ queryKey: queryKeys.summaries, queryFn: () => api.summaries.recent(14) });

  return (
    <>
      <PageHeader
        title="Résumé du jour"
        description="Quelques lignes au lieu de centaines de notifications. Archivé chaque soir automatiquement."
      />

      <Card>
        <CardHeader
          title={today.data ? `Aujourd'hui, ${formatDayLong(today.data.day)}` : "Aujourd'hui"}
          description="Mis à jour en temps réel"
        />
        <CardBody>
          {today.isPending && <Spinner />}
          {today.error && <ErrorBox error={today.error} />}
          {today.data && (
            <>
              <p className="leading-relaxed text-ink">{today.data.text}</p>
              <Stats summary={today.data} />
            </>
          )}
        </CardBody>
      </Card>

      <h2 className="mt-8 mb-3 text-sm font-semibold text-ink">Jours précédents</h2>
      {history.isPending && <Spinner />}
      {history.error && <ErrorBox error={history.error} />}
      {history.data?.length === 0 && (
        <p className="text-sm text-ink-muted">Aucun résumé archivé pour l&apos;instant.</p>
      )}
      <div className="space-y-3">
        {history.data?.map((summary) => (
          <Card key={summary.day} className="px-5 py-4">
            <p className="text-xs font-medium text-ink-muted first-letter:uppercase">{formatDayLong(summary.day)}</p>
            <p className="mt-1 text-sm leading-relaxed text-ink">{summary.text}</p>
          </Card>
        ))}
      </div>
    </>
  );
}
