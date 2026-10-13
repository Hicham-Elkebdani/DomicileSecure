"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Waves } from "lucide-react";
import { useMemo, useState } from "react";

import { Card } from "@/components/ui/card";
import { EmptyState, ErrorBox, Spinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { EventKind, Identity } from "@/lib/api/types";
import { describeEvent, formatDateTime } from "@/lib/format";

const LIMIT = 50;

export default function EventsPage() {
  const [kind, setKind] = useState<EventKind | "">("");
  const [identity, setIdentity] = useState<Identity | "">("");
  const [offset, setOffset] = useState(0);

  const params = { kind: kind || undefined, identity: identity || undefined, limit: LIMIT, offset };
  const events = useQuery({
    queryKey: queryKeys.events(params),
    queryFn: () => api.events.list(params),
    placeholderData: keepPreviousData,
  });
  const cameras = useQuery({ queryKey: queryKeys.cameras, queryFn: api.cameras.list });
  const persons = useQuery({ queryKey: queryKeys.persons(), queryFn: () => api.persons.list() });

  const cameraNames = useMemo(
    () => new Map((cameras.data ?? []).map((c) => [c.id, c.name])),
    [cameras.data],
  );
  const personNames = useMemo(
    () => new Map((persons.data ?? []).map((p) => [p.id, p.display_name])),
    [persons.data],
  );

  return (
    <>
      <PageHeader
        title="Activité"
        description="Chaque ligne est un passage suivi par la caméra, pas une image : pas de doublons."
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <Select
          aria-label="Type"
          className="w-auto"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value as EventKind | "");
            setOffset(0);
          }}
        >
          <option value="">Tous les types</option>
          <option value="person">Personnes</option>
          <option value="animal">Animaux</option>
          <option value="vehicle">Véhicules</option>
          <option value="door">Porte</option>
        </Select>
        <Select
          aria-label="Identité"
          className="w-auto"
          value={identity}
          onChange={(e) => {
            setIdentity(e.target.value as Identity | "");
            setOffset(0);
          }}
        >
          <option value="">Toutes identités</option>
          <option value="resident">Membres du foyer</option>
          <option value="guest">Invités</option>
          <option value="visitor">Visiteurs</option>
          <option value="unknown">Inconnus</option>
        </Select>
      </div>

      <Card>
        {events.isPending && <Spinner />}
        {events.error && (
          <div className="p-5">
            <ErrorBox error={events.error} />
          </div>
        )}
        {events.data?.items.length === 0 && (
          <EmptyState
            icon={<Waves className="size-8" />}
            title="Aucune activité"
            description="Démarrez le worker d'une caméra pour voir les passages apparaître ici en temps réel."
          />
        )}
        {events.data && events.data.items.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-ink-muted">
                    <th className="px-5 py-3 font-medium">Date</th>
                    <th className="px-5 py-3 font-medium">Détection</th>
                    <th className="px-5 py-3 font-medium">Personne</th>
                    <th className="px-5 py-3 font-medium">Caméra</th>
                    <th className="px-5 py-3 text-right font-medium">Confiance</th>
                  </tr>
                </thead>
                <tbody>
                  {events.data.items.map((event) => (
                    <tr key={event.id} className="border-b border-border last:border-0">
                      <td className="px-5 py-3 whitespace-nowrap text-ink-muted">
                        {formatDateTime(event.occurred_at)}
                      </td>
                      <td className="px-5 py-3 text-ink">
                        {describeEvent(event.label, event.kind, event.identity)}
                      </td>
                      <td className="px-5 py-3 text-ink-muted">
                        {event.person_id ? (personNames.get(event.person_id) ?? "—") : "—"}
                        {event.match_score !== null && (
                          <span className="ml-1 text-xs text-ink-faint">
                            ({Math.round(event.match_score * 100)} %)
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-ink-muted">
                        {cameraNames.get(event.camera_id) ?? "—"}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-ink-muted">
                        {Math.round(event.confidence * 100)} %
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination total={events.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </>
  );
}
