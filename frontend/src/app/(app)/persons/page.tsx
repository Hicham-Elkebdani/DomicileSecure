"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Pencil, Plus, Sparkles, Trash2, UserPlus, Users } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorBox, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { api, queryKeys } from "@/lib/api/endpoints";
import type { Person, PersonRole } from "@/lib/api/types";
import { formatRelative, ROLE_LABEL } from "@/lib/format";

type Dialog =
  | { type: "create" }
  | { type: "edit"; person: Person }
  | { type: "enroll"; person: Person }
  | null;

const GROUPS: { role: PersonRole; title: string; description: string }[] = [
  { role: "resident", title: "Membres du foyer", description: "Jamais d'alerte à leur passage." },
  { role: "guest", title: "Invités", description: "Personnes de confiance, simplement journalisées." },
  {
    role: "visitor",
    title: "Visiteurs détectés",
    description: "Créés automatiquement à partir des visages inconnus. Nommez-les ou supprimez-les.",
  },
];

export default function PersonsPage() {
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const [dialog, setDialog] = useState<Dialog>(null);
  const persons = useQuery({ queryKey: queryKeys.persons(), queryFn: () => api.persons.list() });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["persons"] });
  const remove = useMutation({
    mutationFn: (id: string) => api.persons.remove(id),
    onSuccess: () => {
      refresh();
      notify({ title: "Personne et signatures faciales supprimées" });
    },
  });

  return (
    <>
      <PageHeader
        title="Personnes"
        description="Les photos ne sont jamais conservées : seule une signature numérique du visage est enregistrée."
        action={
          <Button onClick={() => setDialog({ type: "create" })}>
            <UserPlus className="size-4" aria-hidden />
            Ajouter
          </Button>
        }
      />

      {persons.isPending && <Spinner />}
      {persons.error && <ErrorBox error={persons.error} />}
      {persons.data && (
        <div className="space-y-6">
          {GROUPS.map((group) => {
            const members = persons.data.filter((p) => p.role === group.role);
            if (group.role === "visitor" && members.length === 0) return null;
            return (
              <Card key={group.role}>
                <CardHeader title={group.title} description={group.description} />
                {members.length === 0 ? (
                  <EmptyState
                    icon={<Users className="size-8" />}
                    title="Personne pour l'instant"
                    action={
                      <Button variant="secondary" size="sm" onClick={() => setDialog({ type: "create" })}>
                        <Plus className="size-3.5" aria-hidden /> Ajouter
                      </Button>
                    }
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {members.map((person) => (
                      <li key={person.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center gap-2 font-medium text-ink">
                            {person.display_name}
                            {person.is_recurring && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-xs font-normal text-ink-muted">
                                <Sparkles className="size-3" aria-hidden /> Récurrent
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-ink-muted">
                            {person.face_count} signature{person.face_count > 1 ? "s" : ""} faciale
                            {person.face_count > 1 ? "s" : ""} · {person.sightings_count} passage
                            {person.sightings_count > 1 ? "s" : ""} · vu {formatRelative(person.last_seen_at)}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="secondary" onClick={() => setDialog({ type: "enroll", person })}>
                            <Camera className="size-3.5" aria-hidden /> Photo
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setDialog({ type: "edit", person })}>
                            <Pencil className="size-3.5" aria-hidden />
                            {person.role === "visitor" ? "Identifier" : "Modifier"}
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            aria-label={`Supprimer ${person.display_name}`}
                            loading={remove.isPending && remove.variables === person.id}
                            onClick={() => {
                              if (window.confirm(`Supprimer ${person.display_name} et ses signatures faciales ?`)) {
                                remove.mutate(person.id);
                              }
                            }}
                          >
                            <Trash2 className="size-3.5" aria-hidden />
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        open={dialog?.type === "create" || dialog?.type === "edit"}
        title={dialog?.type === "edit" ? "Modifier la personne" : "Ajouter une personne"}
        onClose={() => setDialog(null)}
      >
        <PersonForm
          person={dialog?.type === "edit" ? dialog.person : undefined}
          onDone={(created) => {
            refresh();
            setDialog(created ? { type: "enroll", person: created } : null);
          }}
        />
      </Modal>

      <Modal
        open={dialog?.type === "enroll"}
        title={dialog?.type === "enroll" ? `Photo de ${dialog.person.display_name}` : ""}
        onClose={() => setDialog(null)}
      >
        {dialog?.type === "enroll" && (
          <EnrollForm
            person={dialog.person}
            onDone={() => {
              refresh();
            }}
          />
        )}
      </Modal>
    </>
  );
}

function PersonForm({ person, onDone }: { person?: Person; onDone: (created?: Person) => void }) {
  const [name, setName] = useState(person?.display_name ?? "");
  const [role, setRole] = useState<PersonRole>(person?.role === "visitor" ? "guest" : (person?.role ?? "resident"));
  const [notes, setNotes] = useState(person?.notes ?? "");
  const save = useMutation({
    mutationFn: () =>
      person
        ? api.persons.update(person.id, { display_name: name, role, notes })
        : api.persons.create({ display_name: name, role: role as "resident" | "guest", notes }),
    onSuccess: (saved) => onDone(person ? undefined : saved),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Field label="Nom affiché">
        <Input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Rôle">
        <Select value={role} onChange={(e) => setRole(e.target.value as PersonRole)}>
          <option value="resident">{ROLE_LABEL.resident}</option>
          <option value="guest">{ROLE_LABEL.guest}</option>
        </Select>
      </Field>
      <Field label="Notes (facultatif)">
        <Textarea maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      {save.error && <ErrorBox error={save.error} />}
      <div className="flex justify-end">
        <Button type="submit" loading={save.isPending}>
          {person ? "Enregistrer" : "Continuer"}
        </Button>
      </div>
    </form>
  );
}

function EnrollForm({ person, onDone }: { person: Person; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [count, setCount] = useState(person.face_count);
  const enroll = useMutation({
    mutationFn: (photo: File) => api.persons.enrollFace(person.id, photo),
    onSuccess: (result) => {
      setCount(result.face_count);
      setFile(null);
      onDone();
    },
  });

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-muted">
        Ajoutez 5 à 10 photos avec <strong className="text-ink">un seul visage</strong> bien visible : de face,
        de profil, avec et sans lunettes, sous différents éclairages. Uniquement avec l&apos;accord de la personne.
      </p>
      <Input
        key={count}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="py-2"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      {enroll.error && <ErrorBox error={enroll.error} />}
      <div className="flex items-center justify-between">
        <span className="text-sm text-ink-muted">
          {count} signature{count > 1 ? "s" : ""} enregistrée{count > 1 ? "s" : ""}
        </span>
        <Button disabled={!file} loading={enroll.isPending} onClick={() => file && enroll.mutate(file)}>
          Enregistrer le visage
        </Button>
      </div>
    </div>
  );
}
