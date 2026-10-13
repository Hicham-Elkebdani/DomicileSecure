import type { DoorState, EventKind, Identity, PersonRole, Severity } from "@/lib/api/types";

const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" });
const timeOnly = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const dayLabel = new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric" });
const longDay = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" });
const relative = new Intl.RelativeTimeFormat("fr-FR", { numeric: "auto" });

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));
export const formatTime = (iso: string) => timeOnly.format(new Date(iso));
export const formatDayShort = (isoDate: string) => dayLabel.format(new Date(`${isoDate}T12:00:00`));
export const formatDayLong = (isoDate: string) => longDay.format(new Date(`${isoDate}T12:00:00`));

export function formatRelative(iso: string | null): string {
  if (!iso) return "jamais";
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(seconds);
  if (abs < 60) return relative.format(Math.round(seconds), "second");
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), "hour");
  return relative.format(Math.round(seconds / 86400), "day");
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critique",
  high: "Haute",
  medium: "Moyenne",
  low: "Faible",
  info: "Info",
};

export const ROLE_LABEL: Record<PersonRole, string> = {
  resident: "Membre du foyer",
  guest: "Invité",
  visitor: "Visiteur (non confirmé)",
};

export const IDENTITY_LABEL: Record<Identity, string> = {
  resident: "Membre du foyer",
  guest: "Invité",
  visitor: "Visiteur",
  unknown: "Inconnu",
};

export const KIND_LABEL: Record<EventKind, string> = {
  person: "Personne",
  animal: "Animal",
  vehicle: "Véhicule",
  door: "Porte",
};

export const DOOR_LABEL: Record<DoorState, string> = {
  open: "Ouverte",
  closed: "Fermée",
  unknown: "Inconnu",
};

export function describeEvent(label: string, kind: EventKind, identity: Identity | null): string {
  if (kind === "door") return label === "door_open" ? "Porte ouverte" : "Porte fermée";
  if (kind === "person") return identity ? IDENTITY_LABEL[identity] : "Personne";
  const names: Record<string, string> = {
    cat: "Chat",
    dog: "Chien",
    bird: "Oiseau",
    car: "Voiture",
    truck: "Camion",
    motorcycle: "Moto",
    bicycle: "Vélo",
    bus: "Bus",
  };
  return names[label] ?? KIND_LABEL[kind];
}
