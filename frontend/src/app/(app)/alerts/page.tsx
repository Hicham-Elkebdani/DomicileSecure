"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { AlertList } from "@/components/alerts/alert-list";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorBox, Spinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { AlertStatus, Severity } from "@/lib/api/types";

const LIMIT = 20;

export default function AlertsPage() {
  const [status, setStatus] = useState<AlertStatus | "">("new");
  const [minSeverity, setMinSeverity] = useState<Severity | "">("");
  const [offset, setOffset] = useState(0);

  const params = {
    status: status || undefined,
    min_severity: minSeverity || undefined,
    limit: LIMIT,
    offset,
  };
  const alerts = useQuery({
    queryKey: queryKeys.alerts(params),
    queryFn: () => api.alerts.list(params),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title="Alertes"
        description="Signalez les fausses alertes : c'est ce qui permet d'affiner les règles et le modèle."
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <Select
          aria-label="Statut"
          className="w-auto"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as AlertStatus | "");
            setOffset(0);
          }}
        >
          <option value="new">À traiter</option>
          <option value="acknowledged">Traitées</option>
          <option value="dismissed">Fausses alertes</option>
          <option value="">Toutes</option>
        </Select>
        <Select
          aria-label="Gravité minimale"
          className="w-auto"
          value={minSeverity}
          onChange={(e) => {
            setMinSeverity(e.target.value as Severity | "");
            setOffset(0);
          }}
        >
          <option value="">Toutes gravités</option>
          <option value="medium">Moyenne et plus</option>
          <option value="high">Haute et plus</option>
        </Select>
      </div>

      <Card>
        {alerts.isPending && <Spinner />}
        {alerts.error && (
          <div className="p-5">
            <ErrorBox error={alerts.error} />
          </div>
        )}
        {alerts.data?.items.length === 0 && (
          <EmptyState icon={<ShieldCheck className="size-8" />} title="Aucune alerte" />
        )}
        {alerts.data && alerts.data.items.length > 0 && (
          <>
            <AlertList alerts={alerts.data.items} />
            <Pagination total={alerts.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </>
  );
}
