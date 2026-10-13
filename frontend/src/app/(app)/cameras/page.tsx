"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera as CameraIcon, Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/components/ui/cn";
import { EmptyState, ErrorBox, Spinner } from "@/components/ui/feedback";
import { Checkbox, Field, Input } from "@/components/ui/form";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { Camera } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth-context";
import { DOOR_LABEL, formatRelative } from "@/lib/format";

const ONLINE_WINDOW_MS = 2 * 60 * 1000;

export default function CamerasPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Camera | "new" | null>(null);
  const cameras = useQuery({ queryKey: queryKeys.cameras, queryFn: api.cameras.list, refetchInterval: 30_000 });
  const remove = useMutation({
    mutationFn: (id: string) => api.cameras.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.cameras }),
  });
  const isAdmin = Boolean(user?.is_admin);

  async function copyId(id: string) {
    await navigator.clipboard.writeText(`WORKER_CAMERA_ID=${id}`);
    notify({ title: "Copié", description: "Collez cette ligne dans le fichier .env du worker." });
  }

  return (
    <>
      <PageHeader
        title="Caméras"
        description="Chaque caméra est lue par son propre worker. L'adresse du flux reste dans le .env du worker, jamais en base."
        action={
          isAdmin && (
            <Button onClick={() => setEditing("new")}>
              <Plus className="size-4" aria-hidden /> Ajouter
            </Button>
          )
        }
      />

      {cameras.isPending && <Spinner />}
      {cameras.error && <ErrorBox error={cameras.error} />}
      {cameras.data?.length === 0 && (
        <Card>
          <EmptyState
            icon={<CameraIcon className="size-8" />}
            title="Aucune caméra"
            description="Déclarez une caméra, puis démarrez un worker avec son identifiant."
          />
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {cameras.data?.map((camera) => {
          // eslint-disable-next-line react-hooks/purity -- live status needs the current time
          const online = camera.last_seen_at && Date.now() - new Date(camera.last_seen_at).getTime() < ONLINE_WINDOW_MS;
          return (
            <Card key={camera.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-ink">{camera.name}</p>
                  <p className="text-sm text-ink-muted">{camera.location || "Emplacement non renseigné"}</p>
                </div>
                <span className="flex items-center gap-1.5 text-xs text-ink-muted">
                  <span className={cn("size-2 rounded-full", online ? "bg-good" : "bg-ink-faint")} aria-hidden />
                  {!camera.is_active ? "Désactivée" : online ? "En ligne" : "Hors ligne"}
                </span>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-ink-muted">Dernier signal</dt>
                  <dd className="text-ink">{formatRelative(camera.last_seen_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-muted">Porte</dt>
                  <dd className="text-ink">{camera.has_door ? DOOR_LABEL[camera.door_state] : "Non surveillée"}</dd>
                </div>
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={() => copyId(camera.id)}>
                  <Copy className="size-3.5" aria-hidden /> ID du worker
                </Button>
                {isAdmin && (
                  <>
                    <Button size="sm" variant="ghost" onClick={() => setEditing(camera)}>
                      <Pencil className="size-3.5" aria-hidden /> Modifier
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      aria-label={`Supprimer ${camera.name}`}
                      onClick={() => {
                        if (window.confirm(`Supprimer « ${camera.name} » et tout son historique ?`)) {
                          remove.mutate(camera.id);
                        }
                      }}
                    >
                      <Trash2 className="size-3.5" aria-hidden />
                    </Button>
                  </>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      <Modal
        open={editing !== null}
        title={editing === "new" ? "Nouvelle caméra" : "Modifier la caméra"}
        onClose={() => setEditing(null)}
      >
        {editing !== null && (
          <CameraForm
            camera={editing === "new" ? undefined : editing}
            onDone={() => {
              queryClient.invalidateQueries({ queryKey: queryKeys.cameras });
              setEditing(null);
            }}
          />
        )}
      </Modal>
    </>
  );
}

function CameraForm({ camera, onDone }: { camera?: Camera; onDone: () => void }) {
  const [name, setName] = useState(camera?.name ?? "");
  const [location, setLocation] = useState(camera?.location ?? "");
  const [hasDoor, setHasDoor] = useState(camera?.has_door ?? false);
  const [active, setActive] = useState(camera?.is_active ?? true);
  const save = useMutation({
    mutationFn: () => {
      const data = { name, location, has_door: hasDoor, is_active: active };
      return camera ? api.cameras.update(camera.id, data) : api.cameras.create(data);
    },
    onSuccess: onDone,
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Field label="Nom">
        <Input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Emplacement">
        <Input maxLength={120} value={location} onChange={(e) => setLocation(e.target.value)} />
      </Field>
      <Checkbox
        label="Cette caméra filme une porte (détection ouverte / fermée)"
        checked={hasDoor}
        onChange={(e) => setHasDoor(e.target.checked)}
      />
      <Checkbox label="Caméra active" checked={active} onChange={(e) => setActive(e.target.checked)} />
      {save.error && <ErrorBox error={save.error} />}
      <div className="flex justify-end">
        <Button type="submit" loading={save.isPending}>
          Enregistrer
        </Button>
      </div>
    </form>
  );
}
