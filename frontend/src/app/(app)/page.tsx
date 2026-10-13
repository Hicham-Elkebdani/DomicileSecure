"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell, Camera, DoorOpen, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";

import { AlertList } from "@/components/alerts/alert-list";
import { ActivityChart } from "@/components/dashboard/activity-chart";
import { StatTile } from "@/components/dashboard/stat-tile";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorBox, Spinner } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page-header";
import { api, queryKeys } from "@/lib/api/endpoints";
import { DOOR_LABEL } from "@/lib/format";

const ONLINE_WINDOW_MS = 2 * 60 * 1000;

export default function DashboardPage() {
  const counts = useQuery({ queryKey: queryKeys.alertCounts, queryFn: api.alerts.counts });
  const cameras = useQuery({ queryKey: queryKeys.cameras, queryFn: api.cameras.list, refetchInterval: 30_000 });
  const persons = useQuery({ queryKey: queryKeys.persons(), queryFn: () => api.persons.list() });
  const activity = useQuery({ queryKey: queryKeys.activity(7), queryFn: () => api.events.activity(7) });
  const summary = useQuery({ queryKey: queryKeys.summaryToday, queryFn: api.summaries.today });
  const alertParams = { status: "new" as const, limit: 5 };
  const alerts = useQuery({
    queryKey: queryKeys.alerts(alertParams),
    queryFn: () => api.alerts.list(alertParams),
  });

  // eslint-disable-next-line react-hooks/purity -- a fresh "now" on each render is intended
  const now = Date.now();
  const onlineCameras = (cameras.data ?? []).filter(
    (c) => c.is_active && c.last_seen_at && now - new Date(c.last_seen_at).getTime() < ONLINE_WINDOW_MS,
  ).length;
  const known = (persons.data ?? []).filter((p) => p.role !== "visitor").length;
  const doors = (cameras.data ?? []).filter((c) => c.has_door);
  const openDoors = doors.filter((c) => c.door_state === "open");

  return (
    <>
      <PageHeader title="Tableau de bord" description="Ce qui se passe chez vous, en un coup d'œil." />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          label="Alertes à traiter"
          value={counts.data?.new ?? "–"}
          hint={counts.data ? `${counts.data.by_severity.high + counts.data.by_severity.critical} importantes` : undefined}
          icon={Bell}
          href="/alerts"
        />
        <StatTile
          label="Caméras en ligne"
          value={cameras.data ? `${onlineCameras}/${cameras.data.length}` : "–"}
          hint="Signal reçu il y a moins de 2 min"
          icon={Camera}
          href="/cameras"
        />
        <StatTile
          label="Personnes connues"
          value={persons.data ? known : "–"}
          hint="Membres du foyer et invités"
          icon={Users}
          href="/persons"
        />
        <StatTile
          label="Portes"
          value={
            doors.length === 0
              ? "–"
              : openDoors.length > 0
                ? `${openDoors.length} ouverte${openDoors.length > 1 ? "s" : ""}`
                : doors.length > 1
                  ? "Fermées"
                  : DOOR_LABEL.closed
          }
          hint={doors.length ? `${doors.length} surveillée${doors.length > 1 ? "s" : ""}` : "Aucune porte surveillée"}
          icon={DoorOpen}
          href="/cameras"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="Passages détectés" description="7 derniers jours, par type" />
          <CardBody>
            {activity.isPending && <Spinner />}
            {activity.error && <ErrorBox error={activity.error} />}
            {activity.data && <ActivityChart data={activity.data} />}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title="Résumé du jour"
            action={
              <Link href="/summary" className="text-xs font-medium text-accent hover:underline">
                Détails
              </Link>
            }
          />
          <CardBody>
            {summary.isPending && <Spinner />}
            {summary.error && <ErrorBox error={summary.error} />}
            {summary.data && <p className="text-sm leading-relaxed text-ink">{summary.data.text}</p>}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Alertes récentes"
          action={
            <Link href="/alerts" className="text-xs font-medium text-accent hover:underline">
              Tout voir
            </Link>
          }
        />
        {alerts.isPending && <Spinner />}
        {alerts.error && (
          <CardBody>
            <ErrorBox error={alerts.error} />
          </CardBody>
        )}
        {alerts.data?.items.length === 0 && (
          <EmptyState
            icon={<ShieldCheck className="size-8" />}
            title="Tout est calme"
            description="Aucune alerte à traiter. Les passages habituels ne vous dérangent pas."
          />
        )}
        {alerts.data && alerts.data.items.length > 0 && <AlertList alerts={alerts.data.items} />}
      </Card>
    </>
  );
}
