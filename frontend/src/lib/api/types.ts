/** Types mirroring the backend Pydantic schemas (app/schemas). Keep them in sync. */

export type UUID = string;

export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type AlertStatus = "new" | "acknowledged" | "dismissed";
export type EventKind = "person" | "animal" | "vehicle" | "door";
export type Identity = "resident" | "guest" | "visitor" | "unknown";
export type PersonRole = "resident" | "guest" | "visitor";
export type DoorState = "unknown" | "open" | "closed";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: UUID;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface Camera {
  id: UUID;
  name: string;
  location: string;
  has_door: boolean;
  is_active: boolean;
  door_state: DoorState;
  door_state_changed_at: string | null;
  last_seen_at: string | null;
  created_at: string;
}

export interface CameraInput {
  name: string;
  location: string;
  has_door: boolean;
  is_active?: boolean;
}

export interface Person {
  id: UUID;
  display_name: string;
  role: PersonRole;
  notes: string;
  sightings_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  face_count: number;
  is_recurring: boolean;
  created_at: string;
}

export interface PersonInput {
  display_name: string;
  role: "resident" | "guest";
  notes?: string;
}

export interface PersonUpdate {
  display_name?: string;
  role?: PersonRole;
  notes?: string;
}

export interface FaceEnrollmentResult {
  person_id: UUID;
  embedding_id: UUID;
  face_count: number;
  detection_score: number;
}

export interface SecurityEvent {
  id: UUID;
  camera_id: UUID;
  occurred_at: string;
  kind: EventKind;
  label: string;
  confidence: number;
  track_id: number | null;
  identity: Identity | null;
  person_id: UUID | null;
  match_score: number | null;
  bbox: number[] | null;
}

export interface DailyActivity {
  day: string;
  residents: number;
  guests: number;
  visitors: number;
  unknown: number;
  animals: number;
  vehicles: number;
  door_openings: number;
}

export interface Alert {
  id: UUID;
  source: string;
  rule_code: string;
  severity: Severity;
  status: AlertStatus;
  title: string;
  message: string;
  details: Record<string, unknown>;
  camera_id: UUID | null;
  event_id: UUID | null;
  person_id: UUID | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AlertCounts {
  new: number;
  by_severity: Record<Severity, number>;
}

export interface DailySummary {
  day: string;
  text: string;
  stats: {
    total_events: number;
    residents: string[];
    guests: string[];
    unknown_sightings: number;
    visitor_sightings: number;
    animals: number;
    vehicles: number;
    door_openings: number;
    longest_door_open: { minutes: number; started_at: string } | null;
    first_activity: string | null;
    last_activity: string | null;
    alerts: Record<Severity, number>;
  };
  generated_at: string | null;
  is_final: boolean;
}

export interface PushConfig {
  enabled: boolean;
  vapid_public_key: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}

export type RealtimeMessage =
  | { type: "ready"; data: { user: string } }
  | { type: "alert.created"; data: Alert }
  | { type: "event.created"; data: SecurityEvent }
  | { type: "message"; data: { title: string; body: string; url: string } };
