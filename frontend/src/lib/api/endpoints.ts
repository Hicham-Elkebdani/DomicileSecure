import { apiFetch } from "@/lib/api/client";
import type {
  Alert,
  AlertCounts,
  AlertStatus,
  Camera,
  CameraInput,
  DailyActivity,
  DailySummary,
  EventKind,
  FaceEnrollmentResult,
  Identity,
  Page,
  Person,
  PersonInput,
  PersonRole,
  PersonUpdate,
  PushConfig,
  SecurityEvent,
  Severity,
  Token,
  User,
  UUID,
} from "@/lib/api/types";

/** One function per backend endpoint: the only place where URLs are written. */
export const api = {
  auth: {
    login(email: string, password: string): Promise<Token> {
      const body = new URLSearchParams({ username: email, password });
      return apiFetch<Token>("/auth/login", { method: "POST", body });
    },
    me: () => apiFetch<User>("/auth/me"),
  },

  cameras: {
    list: () => apiFetch<Camera[]>("/cameras"),
    create: (data: CameraInput) => apiFetch<Camera>("/cameras", { method: "POST", json: data }),
    update: (id: UUID, data: Partial<CameraInput>) =>
      apiFetch<Camera>(`/cameras/${id}`, { method: "PATCH", json: data }),
    remove: (id: UUID) => apiFetch<void>(`/cameras/${id}`, { method: "DELETE" }),
  },

  persons: {
    list: (role?: PersonRole) => apiFetch<Person[]>("/persons", { query: { role } }),
    create: (data: PersonInput) => apiFetch<Person>("/persons", { method: "POST", json: data }),
    update: (id: UUID, data: PersonUpdate) =>
      apiFetch<Person>(`/persons/${id}`, { method: "PATCH", json: data }),
    remove: (id: UUID) => apiFetch<void>(`/persons/${id}`, { method: "DELETE" }),
    enrollFace(id: UUID, photo: File): Promise<FaceEnrollmentResult> {
      const form = new FormData();
      form.append("photo", photo);
      return apiFetch<FaceEnrollmentResult>(`/persons/${id}/faces`, { method: "POST", body: form });
    },
    deleteFaces: (id: UUID) => apiFetch<void>(`/persons/${id}/faces`, { method: "DELETE" }),
  },

  events: {
    list: (params: {
      kind?: EventKind;
      identity?: Identity;
      camera_id?: UUID;
      limit?: number;
      offset?: number;
    }) => apiFetch<Page<SecurityEvent>>("/events", { query: params }),
    activity: (days = 7) => apiFetch<DailyActivity[]>("/events/activity", { query: { days } }),
  },

  alerts: {
    list: (params: { status?: AlertStatus; min_severity?: Severity; limit?: number; offset?: number }) =>
      apiFetch<Page<Alert>>("/alerts", { query: params }),
    counts: () => apiFetch<AlertCounts>("/alerts/counts"),
    setStatus: (id: UUID, status: AlertStatus) =>
      apiFetch<Alert>(`/alerts/${id}`, { method: "PATCH", json: { status } }),
  },

  summaries: {
    today: () => apiFetch<DailySummary>("/summaries/today"),
    recent: (limit = 14) => apiFetch<DailySummary[]>("/summaries", { query: { limit } }),
  },

  notifications: {
    config: () => apiFetch<PushConfig>("/notifications/config"),
    subscribe: (subscription: PushSubscriptionJSON) =>
      apiFetch<{ message: string }>("/notifications/subscriptions", {
        method: "POST",
        json: subscription,
      }),
    unsubscribe: (endpoint: string) =>
      apiFetch<void>("/notifications/subscriptions", { method: "DELETE", json: { endpoint } }),
    test: () => apiFetch<{ message: string }>("/notifications/test", { method: "POST" }),
  },
};

export const queryKeys = {
  me: ["me"] as const,
  cameras: ["cameras"] as const,
  persons: (role?: PersonRole) => ["persons", role ?? "all"] as const,
  events: (params: object) => ["events", params] as const,
  activity: (days: number) => ["activity", days] as const,
  alerts: (params: object) => ["alerts", params] as const,
  alertCounts: ["alert-counts"] as const,
  summaryToday: ["summary", "today"] as const,
  summaries: ["summaries"] as const,
  pushConfig: ["push-config"] as const,
};
